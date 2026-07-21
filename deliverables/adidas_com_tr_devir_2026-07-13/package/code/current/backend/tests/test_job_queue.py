import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from job_queue import acquire_lock, claim_job, enqueue_job, fail_job, release_lock


async def temporary_database():
    client = AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"), serverSelectionTimeoutMS=2000)
    try:
        await client.admin.command("ping")
    except Exception:
        client.close()
        pytest.skip("MongoDB integration test icin kullanilabilir degil")
    name = f"shoehunter_queue_test_{uuid.uuid4().hex}"
    db = client[name]
    await db.jobs.create_index("idempotency_key", unique=True)
    return client, db, name


@pytest.mark.asyncio
async def test_job_idempotency():
    client, db, name = await temporary_database()
    try:
        first = await enqueue_job(db, "batch_check", idempotency_key="same-job")
        second = await enqueue_job(db, "batch_check", idempotency_key="same-job")
        assert first["id"] == second["id"]
        assert await db.jobs.count_documents({}) == 1
    finally:
        await client.drop_database(name)
        client.close()


@pytest.mark.asyncio
async def test_worker_retry_and_dead_letter():
    client, db, name = await temporary_database()
    try:
        await enqueue_job(db, "test", idempotency_key="retry-job", max_attempts=2)
        claimed = await claim_job(db, "worker-1")
        assert claimed["attempts"] == 1
        assert await fail_job(db, claimed, RuntimeError("temporary")) == "retry"
        await db.jobs.update_one(
            {"id": claimed["id"]},
            {"$set": {"run_at": datetime.now(timezone.utc)}},
        )
        claimed_again = await claim_job(db, "worker-1")
        assert claimed_again["attempts"] == 2
        assert await fail_job(db, claimed_again, RuntimeError("permanent")) == "dead"
        assert await db.dead_letter_jobs.count_documents({"id": claimed["id"]}) == 1
    finally:
        await client.drop_database(name)
        client.close()


@pytest.mark.asyncio
async def test_dead_idempotent_job_is_requeued():
    client, db, name = await temporary_database()
    try:
        await enqueue_job(db, "discover_watch", idempotency_key="dead-retry", max_attempts=1)
        claimed = await claim_job(db, "worker-1")
        assert await fail_job(db, claimed, RuntimeError("first attempt failed")) == "dead"

        retried = await enqueue_job(db, "discover_watch", idempotency_key="dead-retry", max_attempts=1)
        assert retried["id"] == claimed["id"]
        assert retried["status"] == "pending"
        assert retried["attempts"] == 0
        assert "last_error" not in retried
        assert await db.dead_letter_jobs.count_documents({"id": claimed["id"]}) == 0
    finally:
        await client.drop_database(name)
        client.close()


@pytest.mark.asyncio
async def test_workers_only_claim_their_queue():
    client, db, name = await temporary_database()
    try:
        await enqueue_job(db, "backup", idempotency_key="default-job")
        await enqueue_job(db, "discover_watch", idempotency_key="browser-job", queue="browser")
        browser_job = await claim_job(db, "browser-worker", queue="browser")
        default_job = await claim_job(db, "default-worker", queue="default")
        assert browser_job["job_type"] == "discover_watch"
        assert default_job["job_type"] == "backup"
    finally:
        await client.drop_database(name)
        client.close()


@pytest.mark.asyncio
async def test_distributed_lock_has_single_owner():
    client, db, name = await temporary_database()
    try:
        await db.distributed_locks.create_index("key", unique=True)
        assert await acquire_lock(db, "scheduler", "owner-a") is True
        assert await acquire_lock(db, "scheduler", "owner-b") is False
        await release_lock(db, "scheduler", "owner-a")
        assert await acquire_lock(db, "scheduler", "owner-b") is True
    finally:
        await client.drop_database(name)
        client.close()
