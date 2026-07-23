import logging
from datetime import UTC, datetime, timedelta

from product_identity import canonicalize_product_url, identity_from_title
from secret_store import migrate_legacy_telegram_secret
from store_health import CIRCUIT_POLICY_VERSION

logger = logging.getLogger("shoehunter.database")


async def _deduplicate_listing_urls(db):
    groups = await db.listings.aggregate(
        [
            {"$match": {"url": {"$type": "string", "$ne": ""}}},
            {
                "$group": {
                    "_id": "$url",
                    "rows": {"$push": {"id": "$id", "product_id": "$product_id"}},
                    "count": {"$sum": 1},
                }
            },
            {"$match": {"count": {"$gt": 1}}},
        ]
    ).to_list(None)
    for group in groups:
        keeper = group["rows"][0]
        linked_products = {item.get("product_id") for item in group["rows"] if item.get("product_id")}
        for duplicate in group["rows"][1:]:
            duplicate_id = duplicate["id"]
            await db.price_history.update_many({"listing_id": duplicate_id}, {"$set": {"listing_id": keeper["id"]}})
            await db.alerts.update_many({"listing_id": duplicate_id}, {"$set": {"listing_id": keeper["id"]}})
            await db.candidate_listings.update_many(
                {"listing_id": duplicate_id}, {"$set": {"listing_id": keeper["id"]}}
            )
            await db.listings.delete_one({"id": duplicate_id})
        await db.listings.update_one(
            {"id": keeper["id"]},
            {"$set": {"linked_product_ids": sorted(linked_products)}},
        )


async def _normalize_listing_urls(db):
    async for listing in db.listings.find({}, {"_id": 0, "id": 1, "url": 1}):
        canonical = canonicalize_product_url(listing.get("url"))
        if canonical and canonical != listing.get("url"):
            conflict = await db.listings.find_one({"url": canonical, "id": {"$ne": listing["id"]}}, {"_id": 0, "id": 1})
            if not conflict:
                await db.listings.update_one(
                    {"id": listing["id"]},
                    {"$set": {"url": canonical, "canonical_url": canonical}},
                )


async def _migrate_product_identity(db):
    async for product in db.products.find(
        {"$or": [{"identity_version": {"$ne": 2}}, {"canonical_key": {"$exists": False}}]},
        {"_id": 0},
    ):
        identity = identity_from_title(product.get("name"), brand=product.get("brand"))
        await db.products.update_one(
            {"id": product["id"]},
            {
                "$set": {
                    "identity": identity.to_dict(),
                    "identity_version": 2,
                    "canonical_key": identity.canonical_key or None,
                    "family_key": identity.family_key or product.get("family_key"),
                }
            },
        )


async def _deduplicate_products(db):
    groups = await db.products.aggregate(
        [
            {"$match": {"canonical_key": {"$type": "string", "$ne": ""}}},
            {"$sort": {"created_at": 1}},
            {"$group": {"_id": "$canonical_key", "ids": {"$push": "$id"}, "count": {"$sum": 1}}},
            {"$match": {"count": {"$gt": 1}}},
        ]
    ).to_list(None)
    for group in groups:
        keeper_id, *duplicate_ids = group["ids"]
        if not duplicate_ids:
            continue
        await db.listings.update_many({"product_id": {"$in": duplicate_ids}}, {"$set": {"product_id": keeper_id}})
        await db.rules.update_many({"product_id": {"$in": duplicate_ids}}, {"$set": {"product_id": keeper_id}})
        await db.alerts.update_many({"product_id": {"$in": duplicate_ids}}, {"$set": {"product_id": keeper_id}})
        await db.price_history.update_many({"product_id": {"$in": duplicate_ids}}, {"$set": {"product_id": keeper_id}})
        await db.watch_queries.update_many({"product_id": {"$in": duplicate_ids}}, {"$set": {"product_id": keeper_id}})
        await db.products.delete_many({"id": {"$in": duplicate_ids}})


async def _upgrade_six_hour_radar_defaults(db):
    await db.watch_queries.update_many(
        {
            "$or": [
                {"discovery_frequency_hours": {"$exists": False}},
                {"discovery_frequency_hours": None},
                {"discovery_frequency_hours": 12},
            ]
        },
        {"$set": {"discovery_frequency_hours": 6}},
    )
    await db.settings.update_many(
        {
            "$or": [
                {"scheduler.discovery_interval_hours": {"$exists": False}},
                {"scheduler.discovery_interval_hours": None},
                {"scheduler.discovery_interval_hours": 12},
            ]
        },
        {"$set": {"scheduler.discovery_interval_hours": 6}},
    )


async def _upgrade_store_circuit_policy(db):
    """Retire legacy global circuits before operation-isolated policy v4.

    Version 3 stored one circuit per store.  A blocked historical product page
    could therefore suppress Radar discovery for the entire shop.  Version 4
    keeps independent circuit documents in ``store_circuit_health`` and starts
    those lanes clean; aggregate metrics are preserved here.
    """
    now = datetime.now(UTC)
    async for health in db.store_health.find(
        {"circuit_policy_version": {"$ne": CIRCUIT_POLICY_VERSION}},
        {"_id": 0},
    ):
        status = str(health.get("last_status") or "unknown")
        error_text = str(health.get("last_error") or "").lower()
        environment_failure = any(
            marker in error_text
            for marker in ("winerror 5", "all connection attempts failed", "127.0.0.1:9")
        )
        update = {
            "$set": {
                "circuit_policy_version": CIRCUIT_POLICY_VERSION,
                "circuit_state": "closed",
                "consecutive_failures": 0,
                "legacy_circuit_retired_at": now,
                "legacy_circuit_environment_failure": environment_failure,
                "legacy_circuit_last_status": status,
            },
            "$unset": {"circuit_open_until": "", "circuit_reason": ""},
        }
        await db.store_health.update_one({"store_slug": health.get("store_slug")}, update)


async def ensure_database(db):
    await _normalize_listing_urls(db)
    await _deduplicate_listing_urls(db)
    await _migrate_product_identity(db)
    await _deduplicate_products(db)
    await _upgrade_six_hour_radar_defaults(db)
    await _upgrade_store_circuit_policy(db)
    await migrate_legacy_telegram_secret(db)
    await db.products.update_many({"canonical_key": None}, {"$unset": {"canonical_key": ""}})
    try:
        await db.products.drop_index("ix_products_canonical_key")
    except Exception:
        pass

    indexes = [
        (db.listings, [("url", 1)], {"unique": True, "name": "uq_listings_url"}),
        (
            db.products,
            [("canonical_key", 1)],
            {
                "unique": True,
                "name": "uq_products_canonical_key",
                "partialFilterExpression": {"canonical_key": {"$type": "string"}},
            },
        ),
        (db.watch_queries, [("user_id", 1), ("canonical_query", 1)], {"unique": True, "name": "uq_watch_query"}),
        (db.price_history, [("listing_id", 1), ("checked_at", 1)], {"name": "ix_history_listing_time"}),
        (db.alerts, [("deduplication_key", 1)], {"unique": True, "name": "uq_alert_dedupe", "sparse": True}),
        (db.jobs, [("idempotency_key", 1)], {"unique": True, "name": "uq_job_idempotency"}),
        (db.jobs, [("queue", 1), ("status", 1), ("run_at", 1)], {"name": "ix_jobs_claim"}),
        (db.jobs, [("finished_at", 1)], {"expireAfterSeconds": 2592000, "name": "ttl_completed_jobs", "sparse": True}),
        (db.distributed_locks, [("key", 1)], {"unique": True, "name": "uq_distributed_lock"}),
        (db.candidate_listings, [("watch_id", 1), ("url", 1)], {"unique": True, "name": "uq_watch_candidate"}),
        (db.discovery_runs, [("watch_id", 1), ("started_at", -1)], {"name": "ix_discovery_run"}),
        (db.store_health, [("store_slug", 1)], {"unique": True, "name": "uq_store_health"}),
        (
            db.store_circuit_health,
            [("store_slug", 1), ("operation", 1)],
            {"unique": True, "name": "uq_store_circuit_operation"},
        ),
        (db.store_health_events, [("store_slug", 1), ("created_at", -1)], {"name": "ix_store_health_events"}),
        (
            db.store_health_events,
            [("created_at", 1)],
            {"expireAfterSeconds": 604800, "name": "ttl_store_health_events"},
        ),
        (db.auth_sessions, [("token_hash", 1)], {"unique": True, "name": "uq_auth_session"}),
        (db.auth_sessions, [("expires_at", 1)], {"expireAfterSeconds": 0, "name": "ttl_auth_session"}),
        (db.mobile_devices, [("device_id", 1)], {"unique": True, "name": "uq_mobile_device_id"}),
        (db.mobile_devices, [("token_hash", 1)], {"unique": True, "name": "uq_mobile_device_auth_token"}),
        (
            db.mobile_devices,
            [("fcm_fid_hash", 1)],
            {
                "unique": True,
                "name": "uq_mobile_device_fcm_fid",
                "partialFilterExpression": {"fcm_fid_hash": {"$type": "string"}},
            },
        ),
        (db.admin_users, [("id", 1)], {"unique": True, "name": "uq_admin_user"}),
        (db.user_profile, [("id", 1)], {"unique": True, "name": "uq_user_profile"}),
    ]
    for collection, fields, options in indexes:
        try:
            await collection.create_index(fields, **options)
        except Exception as exc:
            logger.warning("Index olusturulamadi (%s): %s", options.get("name"), exc)


async def purge_expired_ai_history(db, retention_days):
    cutoff = (datetime.now(UTC) - timedelta(days=max(1, int(retention_days)))).isoformat()
    result = await db.ai_messages.delete_many({"created_at": {"$lt": cutoff}})
    return result.deleted_count
