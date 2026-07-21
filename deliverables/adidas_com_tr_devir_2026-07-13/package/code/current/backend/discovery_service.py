import asyncio
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus

from alerting import create_alert
from browser_search import rendered_search_batch
from discovery_sources import layered_url_discovery
from engines import ENGINES
from product_identity import (
    ProductIdentity,
    canonicalize_product_url,
    identity_from_title,
    match_identities,
    normalize_size,
)
from store_health import record_store_result, store_circuit_open

from services import evaluate_product_rules, new_id, notify_alert, now_iso, stock_status_from_values

DARK_COLORS = {"siyah", "lacivert", "gri", "kahverengi", "black", "navy", "grey", "gray", "brown"}


def utcnow():
    return datetime.now(timezone.utc)


def make_watch_document(payload, analysis=None):
    raw_query = str(payload.get("raw_query") or payload.get("query") or "").strip()
    normalized_query = str((analysis or {}).get("normalized_query") or raw_query).strip()
    brand = payload.get("brand") or (analysis or {}).get("brand")
    identity = identity_from_title(normalized_query, brand=brand, category=payload.get("category"))
    frequency = max(6, min(168, int(payload.get("discovery_frequency_hours") or 12)))
    refresh = max(30, min(1440, int(payload.get("refresh_frequency_minutes") or 360)))
    desired_sizes = sorted({normalize_size(item) for item in payload.get("desired_sizes") or [] if item})
    now = utcnow()
    return {
        "id": new_id(),
        "user_id": "main",
        "raw_query": raw_query,
        "canonical_query": identity.canonical_key or identity.normalized_title,
        "brand": brand or identity.brand,
        "model": payload.get("model") or " ".join(identity.model_tokens),
        "generation": payload.get("generation") or identity.generation,
        "gender": payload.get("gender") or identity.gender,
        "category": payload.get("category"),
        "desired_sizes": desired_sizes,
        "color_policy": payload.get("color_policy") or "any",
        "allowed_colors": payload.get("allowed_colors") or [],
        "excluded_colors": payload.get("excluded_colors") or [],
        "target_price": payload.get("target_price"),
        "minimum_drop_percent": float(payload.get("minimum_drop_percent") or 0),
        "minimum_drop_amount": float(payload.get("minimum_drop_amount") or 0),
        "store_scope": payload.get("store_scope") or [],
        "required_tokens": payload.get("required_tokens") or [],
        "excluded_tokens": payload.get("excluded_tokens") or [],
        "known_model_codes": identity.model_codes,
        "identity": identity.to_dict(),
        "discovery_frequency_hours": frequency,
        "refresh_frequency_minutes": refresh,
        "last_discovery_at": None,
        "next_discovery_at": now,
        "active": True,
        "created_at": now,
        "updated_at": now,
    }


def _color_allowed(watch, candidate_identity):
    policy = watch.get("color_policy") or "any"
    colors = set(candidate_identity.color_tokens)
    excluded = set(identity_from_title(" ".join(watch.get("excluded_colors") or [])).color_tokens)
    allowed = set(identity_from_title(" ".join(watch.get("allowed_colors") or [])).color_tokens)
    if excluded & colors:
        return False
    if policy == "dark":
        return bool(colors & DARK_COLORS)
    if policy == "specific":
        return bool(allowed & colors)
    return True


def _watch_identity(watch):
    raw = watch.get("identity")
    if isinstance(raw, dict):
        try:
            return ProductIdentity(**raw)
        except TypeError:
            pass
    return identity_from_title(watch.get("raw_query"), brand=watch.get("brand"), category=watch.get("category"))


async def _search_engine(engine, query):
    if engine.js_search and engine.search_path:
        url = engine.search_path.format(q=quote_plus(query))
        result = (await rendered_search_batch([(engine, url, query)]))[0]
        return result
    try:
        results = await asyncio.wait_for(engine.search(query), timeout=35)
        return {"store": engine.name, "status": "ok", "results": results, "engine": "static"}
    except asyncio.TimeoutError:
        return {"store": engine.name, "status": "timeout", "results": [], "error": "Zaman asimi", "engine": "static"}
    except Exception as exc:
        message = str(exc)[:180]
        lowered = message.lower()
        status = "blocked" if "403" in lowered or "429" in lowered else "error"
        return {"store": engine.name, "status": status, "results": [], "error": message, "engine": "static"}


async def _layered_fallback(engine, query):
    candidates = await layered_url_discovery(engine, query, limit=20)
    return [
        {
            "title": item.get("title") or "",
            "url": item["url"],
            "score": 0,
            "image": None,
            "price": None,
            "store": engine.name,
            "discovery_source": item.get("source"),
        }
        for item in candidates
    ]


async def ensure_watch_product(db, watch):
    product_id = watch.get("product_id")
    if product_id:
        product = await db.products.find_one({"id": product_id}, {"_id": 0})
        if product:
            return product
    identity = _watch_identity(watch)
    product = await db.products.find_one({"canonical_key": identity.canonical_key}, {"_id": 0})
    if not product:
        product = {
            "id": new_id(),
            "name": watch["raw_query"],
            "brand": watch.get("brand"),
            "model": watch.get("model"),
            "image": None,
            "notes": "Urun Radari tarafindan olusturuldu",
            "canonical_key": identity.canonical_key,
            "family_key": identity.family_key,
            "identity": identity.to_dict(),
            "identity_version": 2,
            "active": True,
            "created_at": utcnow(),
        }
        await db.products.insert_one(dict(product))
        product.pop("_id", None)
    await db.watch_queries.update_one({"id": watch["id"]}, {"$set": {"product_id": product["id"]}})

    target = watch.get("target_price")
    if target is not None:
        await db.rules.update_one(
            {"watch_id": watch["id"]},
            {
                "$setOnInsert": {
                    "id": new_id(),
                    "watch_id": watch["id"],
                    "product_id": product["id"],
                    "target_price": float(target),
                    "hard_target_price": float(target),
                    "desired_sizes": watch.get("desired_sizes") or [],
                    "size": (watch.get("desired_sizes") or [None])[0],
                    "spectrum_mode": True,
                    "near_target_enabled": False,
                    "near_target_percent": 0,
                    "cooldown_hours": 24,
                    "enabled": True,
                    "created_at": utcnow(),
                }
            },
            upsert=True,
        )
    return product


async def attach_candidate(db, watch, candidate, match, force=False):
    url = canonicalize_product_url(candidate.get("url"))
    existing = await db.listings.find_one({"url": url}, {"_id": 0})
    if existing:
        await db.candidate_listings.update_one(
            {"watch_id": watch["id"], "url": url},
            {"$set": {"listing_id": existing["id"], "status": "attached", "updated_at": utcnow()}},
            upsert=True,
        )
        return existing, False
    product = await ensure_watch_product(db, watch)
    engine = next(item for item in ENGINES if item.supports_url(url))
    data = None
    detail_error = None
    try:
        data = await asyncio.wait_for(engine.get_product_data(url), timeout=35)
    except Exception as exc:
        detail_error = str(exc)[:240]
        if not force and match.get("confidence", 0) < 0.97:
            return None, False
    data = data or {}
    stock_status = stock_status_from_values(
        stock_status=data.get("stock_status"),
        in_stock=data.get("in_stock"),
        sizes=data.get("sizes"),
        error=detail_error,
        price=data.get("current_price") or candidate.get("price"),
    )
    listing = {
        "id": new_id(),
        "product_id": product["id"],
        "watch_ids": [watch["id"]],
        "url": url,
        "canonical_url": url,
        "store": engine.name,
        "store_slug": engine.slug,
        "title": data.get("title") or candidate.get("title"),
        "image": data.get("image") or candidate.get("image"),
        "model_code": data.get("model_code"),
        "seller": data.get("seller"),
        "active": True,
        "last_price": data.get("current_price") or candidate.get("price"),
        "last_old_price": data.get("old_price"),
        "last_cart_price": data.get("cart_price"),
        "last_price_source": data.get("price_source") or candidate.get("discovery_source"),
        "last_confidence": data.get("confidence") or match.get("confidence"),
        "last_stock_count": data.get("stock_count") or 0,
        "last_in_stock": stock_status == "in_stock",
        "last_stock_status": stock_status,
        "last_sizes": data.get("sizes") or [],
        "last_raw": data.get("debug"),
        "last_error": detail_error,
        "match_confidence": match.get("confidence"),
        "match_evidence": match.get("evidence") or [],
        "discovery_source": candidate.get("discovery_source") or "store_search",
        "last_checked_at": now_iso(),
        "created_at": utcnow(),
    }
    try:
        await db.listings.insert_one(dict(listing))
    except Exception:
        existing = await db.listings.find_one({"url": url}, {"_id": 0})
        return existing, False
    listing.pop("_id", None)
    if listing.get("last_price") is not None:
        await db.price_history.insert_one(
            {
                "id": new_id(),
                "listing_id": listing["id"],
                "product_id": product["id"],
                "store": engine.name,
                "price": listing["last_price"],
                "old_price": listing.get("last_old_price"),
                "cart_price": listing.get("last_cart_price"),
                "price_source": listing.get("last_price_source"),
                "confidence": listing.get("last_confidence"),
                "stock_count": listing.get("last_stock_count"),
                "stock_status": stock_status,
                "checked_at": now_iso(),
            }
        )
    if listing.get("image") and not product.get("image"):
        await db.products.update_one({"id": product["id"]}, {"$set": {"image": listing["image"]}})
    await db.candidate_listings.update_one(
        {"watch_id": watch["id"], "url": url},
        {"$set": {"listing_id": listing["id"], "status": "attached", "updated_at": utcnow()}},
        upsert=True,
    )
    alert = await create_alert(
        db,
        alert_type="new_listing",
        title="Yeni magazada urun bulundu",
        product_id=product["id"],
        listing_id=listing["id"],
        watch_id=watch["id"],
        product_name=product["name"],
        store=engine.name,
        url=url,
        price=listing.get("last_price"),
        confidence=match.get("confidence") or 0,
        evidence=match.get("evidence") or [],
    )
    await notify_alert(db, alert)
    await evaluate_product_rules(db, product["id"])
    return listing, True


async def _run_watch_discovery(db, watch):
    started = utcnow()
    run = {
        "id": new_id(),
        "watch_id": watch["id"],
        "query": watch["raw_query"],
        "started_at": started,
        "status": "running",
        "stores": [],
    }
    await db.discovery_runs.insert_one(dict(run))
    expected = _watch_identity(watch)
    scope = set(watch.get("store_scope") or [])
    engines = [engine for engine in ENGINES if not scope or engine.slug in scope]
    semaphore = asyncio.Semaphore(4)

    async def search_one(engine):
        if await store_circuit_open(db, engine.slug):
            return engine, {"store": engine.name, "status": "deferred", "results": []}
        async with semaphore:
            result = await _search_engine(engine, watch["raw_query"])
            if not result.get("results"):
                fallback = await _layered_fallback(engine, watch["raw_query"])
                if fallback:
                    result["results"] = fallback
                    result["status"] = "ok"
                    result["fallback"] = True
            await record_store_result(
                db,
                engine.slug,
                result.get("status") or "error",
                price_ok=any(item.get("price") is not None for item in result.get("results") or []),
                stock_ok=False,
                parser_version=getattr(engine, "parser_version", "1"),
            )
            return engine, result

    search_results = await asyncio.gather(*[search_one(engine) for engine in engines])
    auto_count = review_count = rejected_count = attached_count = 0
    store_summaries = []
    for engine, store_result in search_results:
        store_summaries.append(
            {
                "store": engine.name,
                "slug": engine.slug,
                "status": store_result.get("status"),
                "count": len(store_result.get("results") or []),
                "fallback": bool(store_result.get("fallback")),
            }
        )
        for candidate in store_result.get("results") or []:
            url = canonicalize_product_url(candidate.get("url"))
            if not url:
                continue
            identity = identity_from_title(candidate.get("title"), brand=watch.get("brand"), url=url)
            match = match_identities(
                expected,
                identity,
                required_tokens=watch.get("required_tokens"),
                excluded_tokens=watch.get("excluded_tokens"),
            )
            if not _color_allowed(watch, identity):
                match = {"confidence": 0.0, "decision": "rejected", "evidence": ["color_policy_mismatch"]}
            decision = match["decision"]
            candidate_doc = {
                "watch_id": watch["id"],
                "url": url,
                "store": engine.name,
                "store_slug": engine.slug,
                "title": candidate.get("title"),
                "image": candidate.get("image"),
                "price": candidate.get("price"),
                "source": candidate.get("discovery_source") or "store_search",
                "identity": identity.to_dict(),
                "confidence": match["confidence"],
                "evidence": match["evidence"],
                "status": decision,
                "first_seen_at": utcnow(),
                "updated_at": utcnow(),
            }
            await db.candidate_listings.update_one(
                {"watch_id": watch["id"], "url": url},
                {
                    "$set": candidate_doc,
                    "$setOnInsert": {"id": new_id(), "created_at": utcnow()},
                },
                upsert=True,
            )
            if decision == "auto":
                auto_count += 1
                _, created = await attach_candidate(db, watch, candidate, match)
                attached_count += int(created)
            elif decision == "review":
                review_count += 1
            else:
                rejected_count += 1

    next_run = utcnow() + timedelta(hours=int(watch.get("discovery_frequency_hours") or 12))
    summary = {
        "status": "completed",
        "finished_at": utcnow(),
        "stores": store_summaries,
        "auto_matches": auto_count,
        "review_matches": review_count,
        "rejected_matches": rejected_count,
        "new_listings": attached_count,
    }
    await db.discovery_runs.update_one({"id": run["id"]}, {"$set": summary})
    await db.watch_queries.update_one(
        {"id": watch["id"]},
        {"$set": {"last_discovery_at": utcnow(), "next_discovery_at": next_run, "last_run_summary": summary}},
    )
    return {**run, **summary}


async def run_watch_discovery(db, watch):
    attempt_started = utcnow()
    try:
        return await _run_watch_discovery(db, watch)
    except Exception as exc:
        await db.discovery_runs.update_many(
            {
                "watch_id": watch["id"],
                "status": "running",
                "started_at": {"$gte": attempt_started - timedelta(seconds=1)},
            },
            {
                "$set": {
                    "status": "failed",
                    "finished_at": utcnow(),
                    "error": str(exc)[:300],
                }
            },
        )
        raise


async def run_due_discoveries(db, limit=20):
    due = (
        await db.watch_queries.find({"active": True, "next_discovery_at": {"$lte": utcnow()}}, {"_id": 0})
        .sort("next_discovery_at", 1)
        .to_list(limit)
    )
    output = []
    for watch in due:
        output.append(await run_watch_discovery(db, watch))
    return output


async def review_candidate(db, candidate_id, decision):
    candidate = await db.candidate_listings.find_one({"id": candidate_id}, {"_id": 0})
    if not candidate:
        return None
    if decision == "reject":
        await db.candidate_listings.update_one(
            {"id": candidate_id}, {"$set": {"status": "user_rejected", "reviewed_at": utcnow()}}
        )
        return {**candidate, "status": "user_rejected"}
    if decision == "same_family":
        await db.candidate_listings.update_one(
            {"id": candidate_id},
            {"$set": {"status": "family_only", "reviewed_at": utcnow(), "review_decision": decision}},
        )
        return {**candidate, "status": "family_only"}
    watch = await db.watch_queries.find_one({"id": candidate["watch_id"]}, {"_id": 0})
    evidence_label = "user_variant" if decision == "variant" else "user_approved"
    match = {
        "confidence": candidate.get("confidence") or 0.75,
        "evidence": (candidate.get("evidence") or []) + [evidence_label],
    }
    listing, _ = await attach_candidate(db, watch, candidate, match, force=True)
    await db.candidate_listings.update_one(
        {"id": candidate_id},
        {"$set": {"status": "attached", "reviewed_at": utcnow(), "review_decision": decision}},
    )
    return listing
