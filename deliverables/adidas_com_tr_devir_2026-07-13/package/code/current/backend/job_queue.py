import hashlib
from datetime import datetime, timedelta, timezone

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError


def utcnow():
    return datetime.now(timezone.utc)


async def enqueue_job(
    db,
    job_type,
    payload=None,
    idempotency_key=None,
    max_attempts=4,
    run_at=None,
    queue="default",
):
    payload = payload or {}
    queue = str(queue or "default").strip().lower()
    if not idempotency_key:
        raw = f"{queue}|{job_type}|{payload}"
        idempotency_key = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    doc = {
        "id": hashlib.sha256(f"{idempotency_key}|{utcnow().isoformat()}".encode()).hexdigest()[:32],
        "job_type": job_type,
        "queue": queue,
        "payload": payload,
        "idempotency_key": idempotency_key,
        "status": "pending",
        "attempts": 0,
        "max_attempts": max(1, int(max_attempts)),
        "run_at": run_at or utcnow(),
        "created_at": utcnow(),
        "updated_at": utcnow(),
    }
    try:
        await db.jobs.insert_one(dict(doc))
    except DuplicateKeyError:
        existing = await db.jobs.find_one({"idempotency_key": idempotency_key}, {"_id": 0})
        if existing and existing.get("status") == "dead":
            await db.jobs.update_one(
                {"id": existing["id"]},
                {
                    "$set": {
                        "status": "pending",
                        "attempts": 0,
                        "run_at": run_at or utcnow(),
                        "updated_at": utcnow(),
                    },
                    "$unset": {
                        "last_error": "",
                        "failed_at": "",
                        "finished_at": "",
                        "lease_until": "",
                        "worker_id": "",
                    },
                },
            )
            await db.dead_letter_jobs.delete_one({"id": existing["id"]})
            return await db.jobs.find_one({"id": existing["id"]}, {"_id": 0})
        return existing
    doc.pop("_id", None)
    return doc


async def claim_job(db, worker_id, lease_minutes=10, queue=None):
    now = utcnow()
    filters = [
        {"status": "pending"},
        {"run_at": {"$lte": now}},
        {"$or": [{"lease_until": {"$exists": False}}, {"lease_until": {"$lte": now}}]},
    ]
    if queue == "default":
        filters.append({"$or": [{"queue": "default"}, {"queue": {"$exists": False}}]})
    elif queue:
        filters.append({"queue": queue})
    return await db.jobs.find_one_and_update(
        {"$and": filters},
        {
            "$set": {
                "status": "running",
                "worker_id": worker_id,
                "lease_until": now + timedelta(minutes=lease_minutes),
                "started_at": now,
                "updated_at": now,
            },
            "$inc": {"attempts": 1},
        },
        sort=[("run_at", 1), ("created_at", 1)],
        return_document=ReturnDocument.AFTER,
        projection={"_id": 0},
    )


async def complete_job(db, job_id, result=None):
    await db.jobs.update_one(
        {"id": job_id},
        {
            "$set": {
                "status": "completed",
                "result": result,
                "finished_at": utcnow(),
                "updated_at": utcnow(),
            },
            "$unset": {"lease_until": "", "worker_id": ""},
        },
    )


async def fail_job(db, job, error):
    attempts = int(job.get("attempts") or 1)
    max_attempts = int(job.get("max_attempts") or 4)
    message = str(error)[:1000]
    if attempts < max_attempts:
        delay = min(3600, 30 * (2 ** (attempts - 1)))
        await db.jobs.update_one(
            {"id": job["id"]},
            {
                "$set": {
                    "status": "pending",
                    "last_error": message,
                    "run_at": utcnow() + timedelta(seconds=delay),
                    "updated_at": utcnow(),
                },
                "$unset": {"lease_until": "", "worker_id": ""},
            },
        )
        return "retry"
    dead = {**job, "status": "dead", "last_error": message, "failed_at": utcnow()}
    dead.pop("_id", None)
    await db.dead_letter_jobs.update_one({"id": job["id"]}, {"$set": dead}, upsert=True)
    await db.jobs.update_one(
        {"id": job["id"]},
        {"$set": {"status": "dead", "last_error": message, "finished_at": utcnow()}},
    )
    return "dead"


async def acquire_lock(db, key, owner, lease_seconds=90):
    now = utcnow()
    try:
        result = await db.distributed_locks.find_one_and_update(
            {"key": key, "$or": [{"expires_at": {"$lte": now}}, {"owner": owner}]},
            {"$set": {"owner": owner, "expires_at": now + timedelta(seconds=lease_seconds), "updated_at": now}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
            projection={"_id": 0},
        )
        return bool(result and result.get("owner") == owner)
    except DuplicateKeyError:
        return False


async def release_lock(db, key, owner):
    await db.distributed_locks.delete_one({"key": key, "owner": owner})
