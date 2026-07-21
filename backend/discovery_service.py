import asyncio
import os
import time
from datetime import UTC, datetime, timedelta
from urllib.parse import quote_plus

from alerting import create_alert
from browser_runtime import GLOBAL_BROWSER_CONCURRENCY
from browser_search import rendered_search_batch
from discovery_sources import layered_url_discovery
from engines import ENGINES
from job_queue import acquire_lock, release_lock
from product_identity import (
    ProductIdentity,
    canonicalize_product_url,
    identity_from_title,
    match_identities,
    normalize_size,
)
from search_query_plan import SearchQuery, build_search_plan, plan_as_dicts
from size_profiles import (
    available_size_labels,
    matching_size_labels,
    size_label_for_category,
    watch_audience_for_sizes,
)
from store_health import record_store_result, store_circuit_status

from services import evaluate_product_rules, new_id, notify_alert, now_iso, stock_status_from_values

DARK_COLORS = {"siyah", "lacivert", "gri", "kahverengi", "black", "navy", "grey", "gray", "brown"}
DISCOVERY_STORE_BUDGET_SECONDS = max(
    45, int(os.environ.get("DISCOVERY_STORE_BUDGET_SECONDS", "180"))
)
DISCOVERY_FALLBACK_BUDGET_SECONDS = max(
    15, int(os.environ.get("DISCOVERY_FALLBACK_BUDGET_SECONDS", "45"))
)
DISCOVERY_FALLBACK_CONCURRENCY = max(
    1, int(os.environ.get("DISCOVERY_FALLBACK_CONCURRENCY", "6"))
)
DISCOVERY_LOCK_SECONDS = max(300, int(os.environ.get("DISCOVERY_LOCK_SECONDS", "1200")))
_fallback_semaphore = asyncio.Semaphore(DISCOVERY_FALLBACK_CONCURRENCY)

DIRECT_TERMINAL_STATES = {
    "blocked",
    "capacity_timeout",
    "network_error",
    "runtime_error",
    "timeout",
}
DEFERRED_STATES = {"capacity_timeout", "deferred", "network_error", "runtime_error"}
FAILED_STATES = {"blocked", "error", "parser_failure", "timeout"}


def utcnow():
    return datetime.now(UTC)


def make_watch_document(payload, analysis=None):
    raw_query = str(payload.get("raw_query") or payload.get("query") or "").strip()
    normalized_query = str((analysis or {}).get("normalized_query") or raw_query).strip()
    brand = payload.get("brand") or (analysis or {}).get("brand")
    identity = identity_from_title(normalized_query, brand=brand, category=payload.get("category"))
    frequency = max(6, min(168, int(payload.get("discovery_frequency_hours") or 6)))
    refresh = max(30, min(1440, int(payload.get("refresh_frequency_minutes") or 360)))
    desired_sizes = sorted({normalize_size(item) for item in payload.get("desired_sizes") or [] if item})
    manual_source = payload.get("manual_desired_sizes", payload.get("desired_sizes") or [])
    manual_desired_sizes = sorted({normalize_size(item) for item in manual_source if item})
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
        "manual_desired_sizes": manual_desired_sizes,
        "profile_preference_ids": payload.get("profile_preference_ids") or [],
        "size_preferences": payload.get("size_preferences") or [],
        "size_label": payload.get("size_label") or size_label_for_category(payload.get("category")),
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
        "input_origin": payload.get("input_origin") or "manual",
        "source_identifiers": payload.get("source_identifiers") or {},
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
            identity = ProductIdentity(**raw)
        except TypeError:
            identity = None
    else:
        identity = None
    if identity is None:
        identity = identity_from_title(
            watch.get("raw_query"), brand=watch.get("brand"), category=watch.get("category")
        )

    identifiers = watch.get("source_identifiers") or {}
    model_codes = list(identity.model_codes)
    gtins = list(identity.gtins)
    for key, raw_value in identifiers.items():
        value = str(raw_value or "").strip()
        normalized_key = str(key).strip().casefold()
        if not value:
            continue
        if normalized_key in {"product_code", "model_code", "style_code", "sku"}:
            model_codes.append(value.upper())
        elif normalized_key in {"barcode", "gtin", "ean", "upc"} and value.isdigit():
            gtins.append(value)
    identity.model_codes = list(dict.fromkeys(model_codes))
    identity.gtins = list(dict.fromkeys(gtins))
    return identity


def _candidate_identity(candidate, watch):
    url = canonicalize_product_url(candidate.get("url"))
    identity = identity_from_title(candidate.get("title"), brand=candidate.get("brand"), url=url)
    # Product cards frequently omit the SKU from their visible title while the
    # official product URL still carries it (for example ``/JR5220.html``).
    # URL identifiers are evidence from the candidate itself; the search query
    # is deliberately not injected because a store may return recommendations.
    url_identity = identity_from_title(url)
    identity.model_codes = list(dict.fromkeys(identity.model_codes + url_identity.model_codes))
    identity.gtins = list(dict.fromkeys(identity.gtins + url_identity.gtins))
    return identity


async def _search_engine(engine, query):
    if engine.js_search and engine.search_path:
        url = engine.search_path.format(q=quote_plus(query))
        result = (await rendered_search_batch([(engine, url, query)]))[0]
        message = str(result.get("error") or "")
        if result.get("status") == "error":
            result["status"] = _transport_error_status(message)
        return result
    try:
        results = await asyncio.wait_for(
            engine.search(query), timeout=getattr(engine, "search_timeout_seconds", 40)
        )
        return {"store": engine.name, "status": "ok", "results": results, "engine": "static"}
    except TimeoutError:
        return {"store": engine.name, "status": "timeout", "results": [], "error": "Zaman asimi", "engine": "static"}
    except Exception as exc:
        message = str(exc)[:180]
        status = _transport_error_status(message)
        return {"store": engine.name, "status": status, "results": [], "error": message, "engine": "static"}


def _transport_error_status(message):
    lowered = str(message or "").lower()
    if "403" in lowered or "429" in lowered:
        return "blocked"
    if "winerror 5" in lowered or "permissionerror" in lowered:
        return "runtime_error"
    if "all connection attempts failed" in lowered or "name or service not known" in lowered:
        return "network_error"
    if "kapasite" in lowered and ("timeout" in lowered or "zaman asimi" in lowered):
        return "capacity_timeout"
    return "error"


async def _layered_fallback(engine, query):
    async with _fallback_semaphore:
        candidates = await layered_url_discovery(engine, query, limit=20)
    return [
        {
            "title": item.get("title") or "",
            "url": item["url"],
            "score": 0,
            "image": item.get("image"),
            "price": item.get("price"),
            "store": engine.name,
            "discovery_source": item.get("source"),
            "verification_required": bool(item.get("verification_required")),
        }
        for item in candidates
    ]


def _search_status(attempts):
    statuses = [item.get("direct_status") or item.get("status") for item in attempts]
    if "ok" in statuses:
        return "ok"
    for status in (
        "blocked",
        "timeout",
        "error",
        "capacity_timeout",
        "runtime_error",
        "network_error",
        "not_found",
    ):
        if status in statuses:
            return status
    return statuses[-1] if statuses else "error"


async def _search_engine_plan(engine, plan: list[SearchQuery]):
    """Try a watch's search lanes in priority order and retain audit evidence."""

    attempts = []
    collected_errors = []
    direct_skip_reason = None
    for item in plan:
        if direct_skip_reason:
            result = {
                "store": engine.name,
                "status": direct_skip_reason,
                "results": [],
                "engine": "layered_only",
            }
        else:
            result = await _search_engine(engine, item.query)
            if result.get("status") in DIRECT_TERMINAL_STATES:
                # One transport/access/capacity failure is enough for this run.
                # Remaining identifier lanes still use robots-aware public
                # fallbacks, without repeatedly hitting the same endpoint.
                direct_skip_reason = result.get("status")
        direct_results = result.get("results") or []
        fallback_results = []
        if not direct_results:
            fallback_results = await _layered_fallback(engine, item.query)
        results = direct_results or fallback_results
        status = "ok" if results else (result.get("status") or "error")
        attempt = {
            **item.to_dict(),
            "status": status,
            "direct_status": result.get("status"),
            "direct_count": len(direct_results),
            "fallback_count": len(fallback_results),
            "engine": result.get("engine"),
        }
        if result.get("engine") == "layered_only":
            attempt["direct_skipped_reason"] = direct_skip_reason
        if result.get("error"):
            attempt["error"] = str(result["error"])[:180]
            collected_errors.append(attempt["error"])
        attempts.append(attempt)
        if not results:
            continue

        annotated_results = []
        for candidate in results:
            annotated_results.append(
                {
                    **candidate,
                    "discovery_query": item.query,
                    "discovery_query_kind": item.kind,
                }
            )
        output = {
            **result,
            "status": "ok",
            "results": annotated_results,
            "fallback": bool(fallback_results),
            "direct_status": result.get("status"),
            "matched_query": item.query,
            "matched_query_kind": item.kind,
            "query_attempts": attempts,
        }
        if collected_errors:
            output["direct_error"] = "; ".join(dict.fromkeys(collected_errors))[:300]
            output.setdefault("error", output["direct_error"])
        return output

    output = {
        "store": engine.name,
        "status": _search_status(attempts),
        "results": [],
        "query_attempts": attempts,
        "direct_status": _search_status(attempts),
    }
    if collected_errors:
        output["error"] = "; ".join(dict.fromkeys(collected_errors))[:300]
    return output


async def _fallback_engine_plan(engine, plan: list[SearchQuery], circuit=None):
    """Keep catalog/sitemap discovery alive while direct store search rests."""

    attempts = []
    for item in plan:
        fallback_results = await _layered_fallback(engine, item.query)
        attempts.append(
            {
                **item.to_dict(),
                "status": "ok" if fallback_results else "deferred",
                "direct_count": 0,
                "fallback_count": len(fallback_results),
                "engine": "circuit_safe_fallback",
            }
        )
        if not fallback_results:
            continue
        return {
            "store": engine.name,
            "status": "ok",
            "results": [
                {
                    **candidate,
                    "discovery_query": item.query,
                    "discovery_query_kind": item.kind,
                }
                for candidate in fallback_results
            ],
            "fallback": True,
            "circuit_fallback": True,
            "matched_query": item.query,
            "matched_query_kind": item.kind,
            "query_attempts": attempts,
        }
    return {
        "store": engine.name,
        "status": "deferred",
        "results": [],
        "fallback": True,
        "circuit_fallback": True,
        "query_attempts": attempts,
        "retry_at": (circuit or {}).get("retry_at"),
        "error": (circuit or {}).get("last_error") or "Magaza dogrudan aramasi gecici olarak dinleniyor",
    }


async def _run_fair_store_searches(engines, search_one):
    """Run browser-backed stores through a fair queue without delaying HTML stores.

    The browser pool already limits page concurrency, but starting one separately
    timed browser batch per store made later stores spend their deadline waiting
    for a slot.  Queue waiting now happens before ``search_one`` starts, so each
    store receives its full per-store budget when a browser worker reaches it.
    """

    ordered_engines = list(engines)
    results = [None] * len(ordered_engines)
    browser_queue = asyncio.Queue()
    static_tasks = []

    for index, engine in enumerate(ordered_engines):
        capabilities = engine.capabilities()
        if capabilities.get("requires_browser"):
            browser_queue.put_nowait((index, engine))
        else:
            static_tasks.append((index, asyncio.create_task(search_one(engine))))

    async def browser_worker():
        while True:
            try:
                index, engine = browser_queue.get_nowait()
            except asyncio.QueueEmpty:
                return
            try:
                results[index] = await search_one(engine)
            finally:
                browser_queue.task_done()

    workers = [
        asyncio.create_task(browser_worker())
        for _ in range(min(browser_queue.qsize(), GLOBAL_BROWSER_CONCURRENCY))
    ]
    if static_tasks or workers:
        completed = await asyncio.gather(
            *(task for _, task in static_tasks),
            *workers,
            return_exceptions=True,
        )
        static_count = len(static_tasks)
        for (index, _task), value in zip(static_tasks, completed[:static_count], strict=True):
            if isinstance(value, BaseException):
                raise value
            results[index] = value
        for value in completed[static_count:]:
            if isinstance(value, BaseException):
                raise value

    return results


def _coverage_summary(store_summaries):
    selected = len(store_summaries)
    deferred = sum(item.get("status") in DEFERRED_STATES for item in store_summaries)
    successful = sum(item.get("status") == "ok" for item in store_summaries)
    not_found = sum(item.get("status") == "not_found" for item in store_summaries)
    failed = sum(item.get("status") in FAILED_STATES for item in store_summaries)
    completed = successful + not_found
    searched = completed + failed
    if selected and deferred == selected:
        status = "deferred"
    elif failed and completed == 0:
        status = "failed"
    elif deferred or failed:
        status = "partial"
    else:
        status = "completed"
    return {
        "status": status,
        "selected_store_count": selected,
        "searched_store_count": searched,
        "successful_store_count": successful,
        "not_found_store_count": not_found,
        "completed_store_count": completed,
        "deferred_store_count": deferred,
        "failed_store_count": failed,
        # Coverage means a usable store outcome, not merely that a request was
        # attempted. This prevents an all-blocked run from reporting 100%.
        "coverage_percent": round((completed / selected) * 100, 1) if selected else 0.0,
        "attempted_percent": round((searched / selected) * 100, 1) if selected else 0.0,
    }


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
            "category": watch.get("category"),
            "tracking_origins": ["radar"],
            "tracking_source": "radar",
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
    else:
        await db.products.update_one(
            {"id": product["id"]},
            {"$addToSet": {"tracking_origins": "radar"}, "$set": {"tracking_source": "radar"}},
        )
        product["tracking_origins"] = sorted(set((product.get("tracking_origins") or []) + ["radar"]))
        product["tracking_source"] = "radar"
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
                    "size_preferences": watch.get("size_preferences") or [],
                    "category": watch.get("category"),
                    "size_label": watch.get("size_label") or size_label_for_category(watch.get("category")),
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
        "last_cart_price_source": data.get("cart_price_source"),
        "last_cart_price_confidence": data.get("cart_price_confidence"),
        "last_cart_price_conditions": data.get("cart_price_conditions") or [],
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
                "cart_price_source": listing.get("last_cart_price_source"),
                "cart_price_confidence": listing.get("last_cart_price_confidence"),
                "cart_price_conditions": listing.get("last_cart_price_conditions") or [],
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
    available_sizes = available_size_labels(listing.get("last_sizes"))
    matched_sizes = matching_size_labels(watch.get("desired_sizes"), available_sizes)
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
        size=matched_sizes[0] if matched_sizes else None,
        sizes=matched_sizes,
        size_label=watch.get("size_label") or size_label_for_category(watch.get("category")),
        audience=watch_audience_for_sizes(watch, matched_sizes),
        confidence=match.get("confidence") or 0,
        evidence=match.get("evidence") or [],
    )
    await notify_alert(db, alert)
    await evaluate_product_rules(db, product["id"])
    return listing, True


async def _run_watch_discovery(db, watch):
    started = utcnow()
    search_plan = build_search_plan(watch)
    run = {
        "id": new_id(),
        "watch_id": watch["id"],
        "query": watch["raw_query"],
        "started_at": started,
        "status": "running",
        "search_plan": plan_as_dicts(search_plan),
        "stores": [],
    }
    await db.discovery_runs.insert_one(dict(run))
    expected = _watch_identity(watch)
    scope = set(watch.get("store_scope") or [])
    engines = [engine for engine in ENGINES if not scope or engine.slug in scope]

    async def search_one(engine):
        started_at = time.perf_counter()
        try:
            circuit = await store_circuit_status(db, engine.slug, operation="discovery")
            if circuit["open"]:
                try:
                    result = await asyncio.wait_for(
                        _fallback_engine_plan(engine, search_plan, circuit=circuit),
                        timeout=DISCOVERY_FALLBACK_BUDGET_SECONDS,
                    )
                except TimeoutError:
                    result = {
                        "store": engine.name,
                        "status": "deferred",
                        "results": [],
                        "fallback": True,
                        "circuit_fallback": True,
                        "query_attempts": [],
                        "retry_at": circuit.get("retry_at"),
                        "error": "Guvenli kaynak taramasi zaman butcesini asti",
                    }
                await record_store_result(
                    db,
                    engine.slug,
                    "ok" if result.get("results") else "deferred",
                    latency_ms=(time.perf_counter() - started_at) * 1000,
                    price_ok=any(
                        item.get("price") is not None for item in result.get("results") or []
                    ),
                    stock_ok=False,
                    parser_version=getattr(engine, "parser_version", "1"),
                    error=result.get("error"),
                    source="circuit_safe_fallback",
                    operation="discovery",
                    affects_circuit=False,
                )
                return engine, result

            try:
                result = await asyncio.wait_for(
                    _search_engine_plan(engine, search_plan),
                    timeout=DISCOVERY_STORE_BUDGET_SECONDS,
                )
            except TimeoutError:
                result = {
                    "store": engine.name,
                    "status": "capacity_timeout",
                    "direct_status": "capacity_timeout",
                    "results": [],
                    "query_attempts": [],
                    "error": "Magaza aramasi ayrilan adil zaman butcesini asti",
                    "engine": "store_budget",
                }
            health_result = await record_store_result(
                db,
                engine.slug,
                result.get("status") or "error",
                latency_ms=(time.perf_counter() - started_at) * 1000,
                price_ok=any(item.get("price") is not None for item in result.get("results") or []),
                stock_ok=False,
                parser_version=getattr(engine, "parser_version", "1"),
                error=result.get("error"),
                source="discovery_plan",
                operation="discovery",
                circuit_status=(result.get("direct_status") if result.get("fallback") else None),
            )
            if health_result.get("retry_at") and not result.get("retry_at"):
                result["retry_at"] = health_result["retry_at"]
            return engine, result
        except Exception as exc:
            # A programming, parser, or database-adjacent failure in one store
            # must not cancel the other 26 store tasks. The error is persisted
            # best-effort and retried on a short bounded schedule.
            message = str(exc)[:300]
            result = {
                "store": engine.name,
                "status": "runtime_error",
                "direct_status": "runtime_error",
                "results": [],
                "query_attempts": [],
                "error": message,
                "engine": "isolated_store_task",
                "retry_at": utcnow() + timedelta(minutes=2),
            }
            try:
                await record_store_result(
                    db,
                    engine.slug,
                    "runtime_error",
                    latency_ms=(time.perf_counter() - started_at) * 1000,
                    parser_version=getattr(engine, "parser_version", "1"),
                    error=message,
                    source="discovery_plan",
                    operation="discovery",
                )
            except Exception:
                pass
            return engine, result

    # Static stores stay fully parallel. Browser-capable stores enter a bounded
    # FIFO queue so their store budget starts only after a real browser slot is
    # available instead of expiring while they wait behind earlier stores.
    search_results = await _run_fair_store_searches(engines, search_one)
    auto_count = review_count = rejected_count = attached_count = 0
    store_summaries = []
    for engine, store_result in search_results:
        store_summaries.append(
            {
                "store": engine.name,
                "slug": engine.slug,
                "status": store_result.get("status"),
                "direct_status": store_result.get("direct_status"),
                "direct_error": store_result.get("direct_error"),
                "count": len(store_result.get("results") or []),
                "fallback": bool(store_result.get("fallback")),
                "matched_query": store_result.get("matched_query"),
                "matched_query_kind": store_result.get("matched_query_kind"),
                "query_attempts": store_result.get("query_attempts") or [],
                "error": store_result.get("error"),
                "retry_at": store_result.get("retry_at"),
                "circuit_fallback": bool(store_result.get("circuit_fallback")),
            }
        )
        for candidate in store_result.get("results") or []:
            url = canonicalize_product_url(candidate.get("url"))
            if not url:
                continue
            identity = _candidate_identity(candidate, watch)
            match = match_identities(
                expected,
                identity,
                required_tokens=watch.get("required_tokens"),
                excluded_tokens=watch.get("excluded_tokens"),
            )
            if not _color_allowed(watch, identity):
                match = {"confidence": 0.0, "decision": "rejected", "evidence": ["color_policy_mismatch"]}
            decision = match["decision"]
            if candidate.get("verification_required") and decision == "auto":
                match = {
                    **match,
                    "confidence": min(float(match.get("confidence") or 0), 0.89),
                    "decision": "review",
                    "evidence": (match.get("evidence") or []) + ["official_code_route_requires_page_verification"],
                }
                decision = "review"
            candidate_doc = {
                "watch_id": watch["id"],
                "url": url,
                "store": engine.name,
                "store_slug": engine.slug,
                "title": candidate.get("title"),
                "image": candidate.get("image"),
                "price": candidate.get("price"),
                "source": candidate.get("discovery_source") or "store_search",
                "verification_required": bool(candidate.get("verification_required")),
                "search_query": candidate.get("discovery_query"),
                "search_query_kind": candidate.get("discovery_query_kind"),
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

    regular_next_run = utcnow() + timedelta(hours=int(watch.get("discovery_frequency_hours") or 6))
    retry_times = [
        item.get("retry_at")
        for item in store_summaries
        if isinstance(item.get("retry_at"), datetime)
    ]
    retry_run = min(retry_times) if retry_times else None
    if retry_run:
        retry_run = max(retry_run, utcnow() + timedelta(minutes=1))
    next_run = min(regular_next_run, retry_run) if retry_run else regular_next_run
    coverage = _coverage_summary(store_summaries)
    summary = {
        **coverage,
        "finished_at": utcnow(),
        "stores": store_summaries,
        "search_plan": plan_as_dicts(search_plan),
        "retry_scheduled_for": retry_run,
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
    owner = new_id()
    lock_key = f"discovery_watch:{watch['id']}"
    acquired = await acquire_lock(db, lock_key, owner, lease_seconds=DISCOVERY_LOCK_SECONDS)
    if not acquired:
        existing = await db.discovery_runs.find_one(
            {"watch_id": watch["id"], "status": "running"},
            {"_id": 0},
            sort=[("started_at", -1)],
        )
        return {
            "id": (existing or {}).get("id"),
            "watch_id": watch["id"],
            "query": watch.get("raw_query"),
            "status": "deferred",
            "reason": "discovery_already_running",
            "retry_scheduled_for": utcnow() + timedelta(minutes=2),
        }
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
    finally:
        await release_lock(db, lock_key, owner)


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
