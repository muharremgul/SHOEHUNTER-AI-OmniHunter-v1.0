import logging
from datetime import datetime, timedelta, timezone

from product_identity import canonicalize_product_url, identity_from_title
from secret_store import migrate_legacy_telegram_secret

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


async def ensure_database(db):
    await _normalize_listing_urls(db)
    await _deduplicate_listing_urls(db)
    await _migrate_product_identity(db)
    await _deduplicate_products(db)
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
        (db.store_health_events, [("store_slug", 1), ("created_at", -1)], {"name": "ix_store_health_events"}),
        (
            db.store_health_events,
            [("created_at", 1)],
            {"expireAfterSeconds": 604800, "name": "ttl_store_health_events"},
        ),
        (db.auth_sessions, [("token_hash", 1)], {"unique": True, "name": "uq_auth_session"}),
        (db.auth_sessions, [("expires_at", 1)], {"expireAfterSeconds": 0, "name": "ttl_auth_session"}),
        (db.admin_users, [("id", 1)], {"unique": True, "name": "uq_admin_user"}),
    ]
    for collection, fields, options in indexes:
        try:
            await collection.create_index(fields, **options)
        except Exception as exc:
            logger.warning("Index olusturulamadi (%s): %s", options.get("name"), exc)


async def purge_expired_ai_history(db, retention_days):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=max(1, int(retention_days)))).isoformat()
    result = await db.ai_messages.delete_many({"created_at": {"$lt": cutoff}})
    return result.deleted_count
