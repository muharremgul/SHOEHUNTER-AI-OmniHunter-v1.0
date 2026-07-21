from datetime import datetime, timedelta, timezone

FAILURE_STATES = {"error", "blocked", "timeout", "parser_failure"}


def utcnow():
    return datetime.now(timezone.utc)


def as_utc(value):
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


async def store_circuit_open(db, store_slug):
    health = await db.store_health.find_one({"store_slug": store_slug}, {"_id": 0})
    if not health or health.get("circuit_state") != "open":
        return False
    until = as_utc(health.get("circuit_open_until"))
    if until and until > utcnow():
        return True
    await db.store_health.update_one(
        {"store_slug": store_slug},
        {"$set": {"circuit_state": "half_open"}},
    )
    return False


async def record_store_result(db, store_slug, status, latency_ms=None, price_ok=None, stock_ok=None, parser_version="1"):
    now = utcnow()
    success = status == "ok"
    update = {
        "$set": {
            "store_slug": store_slug,
            "last_status": status,
            "last_checked_at": now,
            "parser_version": parser_version,
        },
        "$inc": {
            "total_checks": 1,
            "total_success": 1 if success else 0,
            "total_failures": 0 if success else 1,
            "blocked_count": 1 if status == "blocked" else 0,
        },
    }
    if success:
        update["$set"].update(
            {
                "last_success_at": now,
                "consecutive_failures": 0,
                "circuit_state": "closed",
                "sample_price_success": bool(price_ok),
                "sample_stock_success": bool(stock_ok),
            }
        )
    else:
        update["$set"]["last_failure_at"] = now
        update["$inc"]["consecutive_failures"] = 1
    if latency_ms is not None:
        update["$set"]["last_latency_ms"] = round(float(latency_ms), 2)
        update["$inc"]["latency_total_ms"] = float(latency_ms)
        update["$inc"]["latency_samples"] = 1
    await db.store_health.update_one({"store_slug": store_slug}, update, upsert=True)
    await db.store_health_events.insert_one(
        {
            "store_slug": store_slug,
            "status": status,
            "success": success,
            "blocked": status == "blocked",
            "latency_ms": round(float(latency_ms), 2) if latency_ms is not None else None,
            "price_ok": price_ok,
            "stock_ok": stock_ok,
            "created_at": now,
        }
    )

    health = await db.store_health.find_one({"store_slug": store_slug}, {"_id": 0})
    if not success and int(health.get("consecutive_failures") or 0) >= 5:
        wait_minutes = min(360, 15 * (2 ** min(4, int(health["consecutive_failures"]) - 5)))
        await db.store_health.update_one(
            {"store_slug": store_slug},
            {
                "$set": {
                    "circuit_state": "open",
                    "circuit_open_until": now + timedelta(minutes=wait_minutes),
                }
            },
        )


async def health_snapshot(db):
    docs = await db.store_health.find({}, {"_id": 0}).sort("store_slug", 1).to_list(200)
    cutoff = utcnow() - timedelta(hours=24)
    recent = await db.store_health_events.aggregate(
        [
            {"$match": {"created_at": {"$gte": cutoff}}},
            {
                "$group": {
                    "_id": "$store_slug",
                    "checks": {"$sum": 1},
                    "successes": {"$sum": {"$cond": ["$success", 1, 0]}},
                    "blocked": {"$sum": {"$cond": ["$blocked", 1, 0]}},
                    "average_latency_ms": {"$avg": "$latency_ms"},
                }
            },
        ]
    ).to_list(200)
    recent_by_store = {row["_id"]: row for row in recent}
    for doc in docs:
        total = max(1, int(doc.get("total_checks") or 0))
        success = int(doc.get("total_success") or 0)
        blocked = int(doc.get("blocked_count") or 0)
        doc["success_rate"] = round(success / total, 4)
        doc["blocked_rate"] = round(blocked / total, 4)
        window = recent_by_store.get(doc["store_slug"], {})
        checks_24h = int(window.get("checks") or 0)
        doc["checks_24h"] = checks_24h
        doc["success_rate_24h"] = round(int(window.get("successes") or 0) / checks_24h, 4) if checks_24h else None
        doc["blocked_rate_24h"] = round(int(window.get("blocked") or 0) / checks_24h, 4) if checks_24h else None
        doc["average_latency_ms"] = round(float(window["average_latency_ms"]), 2) if window.get("average_latency_ms") is not None else None
    return docs
