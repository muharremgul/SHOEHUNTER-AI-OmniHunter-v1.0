import asyncio
import os
import socket

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

from backup_service import create_json_backup
from discovery_service import run_due_discoveries, run_watch_discovery
from job_queue import claim_job, complete_job, fail_job
from services import batch_check, check_listing, send_alert_digest
from variant_service import discover_product_variants

load_dotenv()


async def handle_job(db, job):
    job_type = job["job_type"]
    payload = job.get("payload") or {}
    if job_type == "batch_check":
        run, alerts = await batch_check(
            db,
            trigger=payload.get("trigger") or "worker",
            force=bool(payload.get("force")),
        )
        return {"run_id": run["id"], "alerts": len(alerts)}
    if job_type == "discover_due":
        runs = await run_due_discoveries(db)
        return {"runs": len(runs)}
    if job_type == "discover_watch":
        watch = await db.watch_queries.find_one({"id": payload["watch_id"]}, {"_id": 0})
        if not watch:
            raise ValueError("WatchQuery bulunamadi")
        run = await run_watch_discovery(db, watch)
        return {"run_id": run["id"]}
    if job_type == "refresh_listing":
        listing = await db.listings.find_one({"id": payload["listing_id"]}, {"_id": 0})
        if not listing:
            raise ValueError("Listing bulunamadi")
        result = await check_listing(db, listing)
        from services import evaluate_product_rules

        alerts = await evaluate_product_rules(db, listing["product_id"])
        return {"check": result, "alerts": len(alerts)}
    if job_type == "discover_variants":
        return await discover_product_variants(db, payload["product_id"], payload.get("urls") or [])
    if job_type == "backup":
        return await create_json_backup(db)
    if job_type == "alert_digest":
        return await send_alert_digest(db)
    raise ValueError(f"Bilinmeyen job turu: {job_type}")


async def main():
    client = AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    db = client[os.environ.get("DB_NAME", "shoehunter_ai")]
    queue = os.environ.get("WORKER_QUEUE", "default").strip().lower() or "default"
    worker_id = f"{socket.gethostname()}-{os.getpid()}-{queue}"
    try:
        while True:
            job = await claim_job(db, worker_id, queue=queue)
            if not job:
                await asyncio.sleep(2)
                continue
            try:
                result = await handle_job(db, job)
                await complete_job(db, job["id"], result)
            except Exception as exc:
                await fail_job(db, job, exc)
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())
