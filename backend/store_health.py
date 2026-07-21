from datetime import UTC, datetime, timedelta

FAILURE_STATES = {"error", "blocked", "timeout", "parser_failure"}
NEUTRAL_STATES = {
    "capacity_timeout",
    "deferred",
    "network_error",
    "not_found",
    "out_of_stock",
    "runtime_error",
    "unknown",
}
CIRCUIT_THRESHOLD = 5
CIRCUIT_POLICY_VERSION = 4


def operation_from_source(source):
    """Map callers to independent circuit lanes.

    A blocked product-detail page must not disable product discovery, and a
    busy browser search must not pause price/stock refreshes.  Metrics remain
    aggregated per store, while circuit state is isolated by operation.
    """

    value = str(source or "").strip().casefold()
    if value.startswith("discovery") or value == "circuit_safe_fallback":
        return "discovery"
    if value.startswith("ai_search") or value == "store_search":
        return "search"
    return "product_detail"


def retry_delay(status):
    """Return a bounded retry delay for a transient result."""

    return {
        "capacity_timeout": timedelta(minutes=2),
        "runtime_error": timedelta(minutes=2),
        "network_error": timedelta(minutes=5),
        "timeout": timedelta(minutes=5),
        "error": timedelta(minutes=10),
        "parser_failure": timedelta(minutes=10),
        "blocked": timedelta(minutes=15),
    }.get(status)


def utcnow():
    return datetime.now(UTC)


def as_utc(value):
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _circuit_collection(db):
    return getattr(db, "store_circuit_health", None)


async def store_circuit_status(db, store_slug, operation="product_detail"):
    collection = _circuit_collection(db)
    query = {"store_slug": store_slug, "operation": operation}
    if collection is None:
        # Lightweight unit-test fakes and pre-v4 compatibility use the legacy
        # aggregate document. Production databases always have the lane
        # collection through Motor's attribute access.
        collection = db.store_health
        query = {"store_slug": store_slug}
    health = await collection.find_one(query, {"_id": 0})
    if not health or health.get("circuit_state") != "open":
        return {
            "open": False,
            "operation": operation,
            "state": (health or {}).get("circuit_state") or "closed",
            "retry_at": None,
            "retry_after_seconds": 0,
            "last_status": (health or {}).get("last_status"),
            "last_error": (health or {}).get("last_error"),
        }
    until = as_utc(health.get("circuit_open_until"))
    if until and until > utcnow():
        return {
            "open": True,
            "operation": operation,
            "state": "open",
            "retry_at": until,
            "retry_after_seconds": max(1, int((until - utcnow()).total_seconds())),
            "last_status": health.get("last_status"),
            "last_error": health.get("last_error"),
        }
    await collection.update_one(
        query,
        {"$set": {"circuit_state": "half_open"}},
    )
    return {
        "open": False,
        "operation": operation,
        "state": "half_open",
        "retry_at": None,
        "retry_after_seconds": 0,
        "last_status": health.get("last_status"),
        "last_error": health.get("last_error"),
    }


async def store_circuit_open(db, store_slug, operation="product_detail"):
    return bool((await store_circuit_status(db, store_slug, operation=operation))["open"])


async def record_store_result(
    db,
    store_slug,
    status,
    latency_ms=None,
    price_ok=None,
    stock_ok=None,
    parser_version="1",
    error=None,
    source=None,
    operation=None,
    circuit_status=None,
    affects_circuit=True,
):
    now = utcnow()
    operation = operation or operation_from_source(source)
    success = status == "ok"
    failure = status in FAILURE_STATES
    neutral = not success and not failure
    update = {
        "$set": {
            "store_slug": store_slug,
            "last_status": status,
            "last_checked_at": now,
            "parser_version": parser_version,
            "circuit_policy_version": CIRCUIT_POLICY_VERSION,
        },
        "$inc": {
            "total_checks": 1,
            "total_success": 1 if success else 0,
            "total_failures": 1 if failure else 0,
            "total_neutral": 1 if neutral else 0,
            "blocked_count": 1 if status == "blocked" else 0,
        },
    }
    if error and not success:
        update["$set"]["last_error"] = str(error)[:500]
    if source:
        update["$set"]["last_source"] = str(source)[:80]
    lane_collection = _circuit_collection(db)
    legacy_circuit = lane_collection is None
    if success:
        update["$set"].update(
            {
                "last_success_at": now,
                "sample_price_success": bool(price_ok),
                "sample_stock_success": bool(stock_ok),
            }
        )
        update["$unset"] = {"last_error": ""}
        if legacy_circuit:
            update["$set"].update({"consecutive_failures": 0, "circuit_state": "closed"})
            update["$unset"]["circuit_open_until"] = ""
    elif failure:
        update["$set"]["last_failure_at"] = now
        if legacy_circuit:
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
            "failure": failure,
            "neutral": neutral,
            "blocked": status == "blocked",
            "error": str(error)[:500] if error else None,
            "source": str(source)[:80] if source else None,
            "operation": operation,
            "circuit_status": circuit_status or status,
            "affects_circuit": bool(affects_circuit),
            "latency_ms": round(float(latency_ms), 2) if latency_ms is not None else None,
            "price_ok": price_ok,
            "stock_ok": stock_ok,
            "created_at": now,
        }
    )

    lane_status = circuit_status or status
    lane_success = lane_status == "ok"
    lane_failure = lane_status in FAILURE_STATES
    health = None
    if affects_circuit and not legacy_circuit:
        lane_update = {
            "$set": {
                "store_slug": store_slug,
                "operation": operation,
                "last_status": lane_status,
                "last_checked_at": now,
                "last_source": str(source)[:80] if source else None,
                "circuit_policy_version": CIRCUIT_POLICY_VERSION,
            },
            "$inc": {"total_checks": 1},
        }
        if error and not lane_success:
            lane_update["$set"]["last_error"] = str(error)[:500]
        if lane_success:
            lane_update["$set"].update(
                {"consecutive_failures": 0, "circuit_state": "closed", "last_success_at": now}
            )
            lane_update["$unset"] = {"circuit_open_until": "", "circuit_reason": "", "last_error": ""}
        elif lane_failure:
            lane_update["$inc"]["consecutive_failures"] = 1
            lane_update["$set"]["last_failure_at"] = now
        await lane_collection.update_one(
            {"store_slug": store_slug, "operation": operation}, lane_update, upsert=True
        )
        health = await lane_collection.find_one(
            {"store_slug": store_slug, "operation": operation}, {"_id": 0}
        )
    elif legacy_circuit:
        health = await db.store_health.find_one({"store_slug": store_slug}, {"_id": 0})

    if affects_circuit and lane_failure and int((health or {}).get("consecutive_failures") or 0) >= CIRCUIT_THRESHOLD:
        failures = int(health["consecutive_failures"])
        base_minutes = 15 if lane_status == "blocked" else 5
        maximum_minutes = 120 if lane_status == "blocked" else 30
        wait_minutes = min(maximum_minutes, base_minutes * (2 ** min(3, failures - CIRCUIT_THRESHOLD)))
        circuit_collection = lane_collection if not legacy_circuit else db.store_health
        circuit_filter = (
            {"store_slug": store_slug, "operation": operation}
            if not legacy_circuit
            else {"store_slug": store_slug}
        )
        await circuit_collection.update_one(
            circuit_filter,
            {
                "$set": {
                    "circuit_state": "open",
                    "circuit_open_until": now + timedelta(minutes=wait_minutes),
                    "circuit_reason": lane_status,
                }
            },
        )
        return {
            "operation": operation,
            "circuit_open": True,
            "retry_at": now + timedelta(minutes=wait_minutes),
        }

    # Local capacity/runtime/network states are deliberately neutral for the
    # circuit counter, but still need a prompt automatic retry rather than the
    # regular six-hour Radar interval.
    delay = retry_delay(lane_status) if affects_circuit and not lane_success else None
    return {
        "operation": operation,
        "circuit_open": False,
        "retry_at": now + delay if delay else None,
    }


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
                    "failures": {"$sum": {"$cond": [{"$in": ["$status", sorted(FAILURE_STATES)]}, 1, 0]}},
                    "neutral": {"$sum": {"$cond": [{"$in": ["$status", sorted(NEUTRAL_STATES)]}, 1, 0]}},
                    "blocked": {"$sum": {"$cond": ["$blocked", 1, 0]}},
                    "average_latency_ms": {"$avg": "$latency_ms"},
                }
            },
        ]
    ).to_list(200)
    recent_by_store = {row["_id"]: row for row in recent}
    lane_collection = _circuit_collection(db)
    lane_docs = []
    if lane_collection is not None:
        lane_docs = await lane_collection.find({}, {"_id": 0}).sort(
            [("store_slug", 1), ("operation", 1)]
        ).to_list(1000)
    lanes_by_store = {}
    for lane in lane_docs:
        until = as_utc(lane.get("circuit_open_until"))
        lane["circuit_open"] = bool(
            lane.get("circuit_state") == "open" and until and until > utcnow()
        )
        lanes_by_store.setdefault(lane.get("store_slug"), {})[lane.get("operation")] = lane

    for doc in docs:
        total = max(1, int(doc.get("total_checks") or 0))
        success = int(doc.get("total_success") or 0)
        blocked = int(doc.get("blocked_count") or 0)
        doc["success_rate"] = round(success / total, 4)
        doc["blocked_rate"] = round(blocked / total, 4)
        window = recent_by_store.get(doc["store_slug"], {})
        checks_24h = int(window.get("checks") or 0)
        successes_24h = int(window.get("successes") or 0)
        failures_24h = int(window.get("failures") or 0)
        neutral_24h = int(window.get("neutral") or 0)
        blocked_24h = int(window.get("blocked") or 0)
        doc["checks_24h"] = checks_24h
        doc["success_count_24h"] = successes_24h
        doc["failure_count_24h"] = failures_24h
        doc["neutral_count_24h"] = neutral_24h
        doc["blocked_count_24h"] = blocked_24h
        doc["success_rate_24h"] = round(successes_24h / checks_24h, 4) if checks_24h else None
        doc["blocked_rate_24h"] = round(blocked_24h / checks_24h, 4) if checks_24h else None
        doc["average_latency_ms"] = round(float(window["average_latency_ms"]), 2) if window.get("average_latency_ms") is not None else None
        circuits = lanes_by_store.get(doc["store_slug"], {})
        doc["circuits"] = circuits
        if circuits:
            doc["circuit_open"] = any(item.get("circuit_open") for item in circuits.values())
            doc["circuit_state"] = "open" if doc["circuit_open"] else "closed"
        else:
            circuit_until = as_utc(doc.get("circuit_open_until"))
            doc["circuit_open"] = bool(
                doc.get("circuit_state") == "open" and circuit_until and circuit_until > utcnow()
            )
    return docs
