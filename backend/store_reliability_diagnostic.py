"""Print an evidence-focused snapshot of Radar store reliability.

This command is read-only.  It reports persisted discovery coverage, circuit
state, and recent per-store events without probing stores or bypassing access
controls.
"""

import argparse
import asyncio
import json
import os
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from store_health import as_utc


def _serializable(value):
    if isinstance(value, datetime):
        return as_utc(value).isoformat()
    raise TypeError(f"Unsupported JSON value: {type(value).__name__}")


async def build_snapshot(db, *, run_limit=8, watch_id=None, event_hours=24):
    run_filter = {"watch_id": watch_id} if watch_id else {}
    projection = {
        "_id": 0,
        "id": 1,
        "watch_id": 1,
        "query": 1,
        "started_at": 1,
        "finished_at": 1,
        "status": 1,
        "selected_store_count": 1,
        "searched_store_count": 1,
        "successful_store_count": 1,
        "deferred_store_count": 1,
        "failed_store_count": 1,
        "coverage_percent": 1,
        "retry_scheduled_for": 1,
        "stores": 1,
    }
    runs = (
        await db.discovery_runs.find(run_filter, projection)
        .sort("started_at", -1)
        .limit(max(1, run_limit))
        .to_list(max(1, run_limit))
    )

    now = datetime.now(UTC)
    health = await db.store_health.find(
        {},
        {
            "_id": 0,
            "store_slug": 1,
            "last_status": 1,
            "last_error": 1,
            "last_source": 1,
            "consecutive_failures": 1,
            "circuit_state": 1,
            "circuit_open_until": 1,
            "last_checked_at": 1,
            "last_success_at": 1,
            "circuit_policy_version": 1,
        },
    ).sort("store_slug", 1).to_list(200)
    for item in health:
        # Global v3 circuit fields are retained only as historical evidence.
        item["legacy_circuit_state"] = item.get("circuit_state")

    lane_docs = await db.store_circuit_health.find(
        {}, {"_id": 0}
    ).sort([("store_slug", 1), ("operation", 1)]).to_list(1000)
    for item in lane_docs:
        until = as_utc(item.get("circuit_open_until"))
        item["circuit_actively_open"] = bool(
            item.get("circuit_state") == "open" and until and until > now
        )

    cutoff = now - timedelta(hours=max(1, event_hours))
    events = await db.store_health_events.find(
        {"created_at": {"$gte": cutoff}},
        {
            "_id": 0,
            "store_slug": 1,
            "status": 1,
            "source": 1,
            "error": 1,
            "created_at": 1,
        },
    ).sort("created_at", -1).to_list(5000)
    event_counts = Counter((row.get("store_slug"), row.get("status")) for row in events)

    return {
        "generated_at": now,
        "event_window_hours": max(1, event_hours),
        "run_count": len(runs),
        "runs": runs,
        "active_open_circuit_count": sum(
            bool(row["circuit_actively_open"]) for row in lane_docs
        ),
        "health": health,
        "circuit_lanes": lane_docs,
        "recent_event_counts": [
            {"store_slug": store, "status": status, "count": count}
            for (store, status), count in sorted(event_counts.items())
        ],
    }


async def main(arguments):
    client = AsyncIOMotorClient(
        os.environ.get("MONGO_URL", "mongodb://localhost:27017"), tz_aware=True
    )
    db = client[os.environ.get("DB_NAME", "shoehunter_ai")]
    try:
        snapshot = await build_snapshot(
            db,
            run_limit=arguments.run_limit,
            watch_id=arguments.watch_id,
            event_hours=arguments.event_hours,
        )
        if arguments.compact:
            for run in snapshot["runs"]:
                run["stores"] = [
                    {
                        "slug": item.get("slug"),
                        "status": item.get("status"),
                        "direct_status": item.get("direct_status"),
                        "count": item.get("count"),
                        "fallback": item.get("fallback"),
                        "retry_at": item.get("retry_at"),
                        "error": item.get("error"),
                    }
                    for item in run.get("stores") or []
                ]
        print(json.dumps(snapshot, ensure_ascii=False, default=_serializable, indent=2))
    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-limit", type=int, default=8)
    parser.add_argument("--watch-id")
    parser.add_argument("--event-hours", type=int, default=24)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    load_dotenv(Path(__file__).with_name(".env"))
    asyncio.run(main(args))
