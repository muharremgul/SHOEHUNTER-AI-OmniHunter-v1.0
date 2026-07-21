import asyncio
import os
import socket
from datetime import datetime, timezone

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

from job_queue import acquire_lock, enqueue_job, release_lock
from services import get_settings

load_dotenv()


def time_bucket(minutes):
    now = datetime.now(timezone.utc)
    return int(now.timestamp() // (minutes * 60))


async def schedule_once(db, owner):
    if not await acquire_lock(db, "scheduler_tick", owner, lease_seconds=55):
        return
    try:
        settings = await get_settings(db)
        scheduler = settings.get("scheduler") or {}
        if scheduler.get("enabled"):
            minutes = max(1, int(scheduler.get("interval_minutes") or 30))
            await enqueue_job(
                db,
                "batch_check",
                idempotency_key=f"batch:{time_bucket(minutes)}",
                queue="browser",
            )
        await enqueue_job(
            db,
            "discover_due",
            idempotency_key=f"discovery:{time_bucket(60)}",
            queue="browser",
        )
        if os.environ.get("NOTIFICATION_MODE", "immediate").strip().lower() == "digest":
            await enqueue_job(
                db,
                "alert_digest",
                idempotency_key=f"digest:{time_bucket(60)}",
            )
        if datetime.now(timezone.utc).hour == 2:
            await enqueue_job(
                db,
                "backup",
                idempotency_key=datetime.now(timezone.utc).strftime("backup:%Y-%m-%d"),
            )
    finally:
        await release_lock(db, "scheduler_tick", owner)


async def main():
    client = AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    db = client[os.environ.get("DB_NAME", "shoehunter_ai")]
    owner = f"{socket.gethostname()}-{os.getpid()}"
    try:
        while True:
            await schedule_once(db, owner)
            await asyncio.sleep(60)
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())
