import asyncio
import logging
import os
import time
import uuid
from datetime import datetime, timedelta, timezone

import httpx

from alerting import create_alert, telegram_alert_message
from engines import get_engine_for_url
from insights import compute_buy_decision, compute_price_insight, short_comment
from product_identity import normalize_size
from secret_store import get_secret
from store_health import record_store_result, store_circuit_open

logger = logging.getLogger("shoehunter.services")


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def new_id():
    return str(uuid.uuid4())


def stock_status_from_values(stock_status=None, in_stock=None, sizes=None, error=None, price=None):
    valid = {"in_stock", "out_of_stock", "unknown", "blocked", "not_found", "error"}
    if stock_status in valid:
        return stock_status
    if in_stock is True:
        return "in_stock"
    sizes = sizes or []
    if sizes:
        return "in_stock" if any(size.get("in_stock") for size in sizes) else "out_of_stock"
    if error:
        lowered = str(error).lower()
        if any(token in lowered for token in ("403", "429", "bot koruma", "captcha")):
            return "blocked"
        if "404" in lowered or "bulunamadi" in lowered or "bulunamadı" in lowered:
            return "not_found"
        return "error"
    return "unknown" if price is not None else "unknown"


def stock_status_from_listing(listing):
    return stock_status_from_values(
        stock_status=listing.get("last_stock_status"),
        in_stock=listing.get("last_in_stock"),
        sizes=listing.get("last_sizes"),
        error=listing.get("last_error"),
        price=listing.get("last_price"),
    )


def default_settings():
    return {
        "id": "main",
        "telegram": {
            "enabled": True,
            "chat_id": os.environ.get("TELEGRAM_CHAT_ID", ""),
        },
        "scheduler": {
            "enabled": False,
            "interval_minutes": 30,
            "discovery_interval_hours": 12,
        },
        "privacy": {
            "ai_history_retention_days": int(os.environ.get("AI_HISTORY_RETENTION_DAYS", "30")),
        },
        "updated_at": now_iso(),
    }


async def get_settings(db):
    doc = await db.settings.find_one({"id": "main"}, {"_id": 0})
    if not doc:
        doc = default_settings()
        await db.settings.insert_one(dict(doc))
        doc.pop("_id", None)
    defaults = default_settings()
    doc.setdefault("telegram", defaults["telegram"])
    doc.setdefault("scheduler", defaults["scheduler"])
    doc.setdefault("privacy", defaults["privacy"])
    return doc


async def public_settings(db):
    settings = await get_settings(db)
    telegram = dict(settings.get("telegram") or {})
    telegram.pop("bot_token", None)
    token = await get_secret(db, "telegram_bot_token")
    telegram["configured"] = bool(token and telegram.get("chat_id"))
    return {
        **settings,
        "telegram": telegram,
    }


async def send_telegram(db, text):
    settings = await get_settings(db)
    telegram = settings.get("telegram", {})
    if not telegram.get("enabled"):
        return {"sent": False, "skipped": True, "reason": "telegram_kapali"}
    token = (await get_secret(db, "telegram_bot_token")).strip()
    chat_id = str(telegram.get("chat_id") or os.environ.get("TELEGRAM_CHAT_ID", "")).strip()
    if not token or not chat_id:
        return {"sent": False, "skipped": True, "reason": "token_veya_chat_id_eksik"}
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(url, json=payload)
            data = response.json()
        if data.get("ok"):
            return {"sent": True}
        if data.get("error_code") == 401:
            return {
                "sent": False,
                "error": "Telegram bot tokeni gecersiz veya BotFather tarafindan iptal edilmis.",
            }
        error = str(data).replace(token, "***")[:500]
        return {"sent": False, "error": error}
    except Exception as exc:
        return {"sent": False, "error": str(exc).replace(token, "***")[:500]}


async def notify_alert(db, alert):
    if not alert:
        return None
    if os.environ.get("NOTIFICATION_MODE", "immediate").strip().lower() == "digest":
        return {"sent": False, "queued": True, "reason": "digest_mode"}
    result = await send_telegram(db, telegram_alert_message(alert))
    status = "sent" if result.get("sent") else ("skipped" if result.get("skipped") else "failed")
    await db.alerts.update_one(
        {"id": alert["id"]},
        {
            "$set": {
                "telegram_sent": bool(result.get("sent")),
                "telegram_error": result.get("error") or result.get("reason"),
                "notification_status": status,
                "last_notified_at": datetime.now(timezone.utc),
            }
        },
    )
    return result


async def send_alert_digest(db):
    from alerting import pending_alert_digest

    message, alerts = await pending_alert_digest(db)
    if not alerts:
        return {"sent": False, "skipped": True, "reason": "bekleyen_bildirim_yok"}
    result = await send_telegram(db, message)
    status = "sent" if result.get("sent") else ("skipped" if result.get("skipped") else "failed")
    await db.alerts.update_many(
        {"id": {"$in": [alert["id"] for alert in alerts]}},
        {
            "$set": {
                "telegram_sent": bool(result.get("sent")),
                "telegram_error": result.get("error") or result.get("reason"),
                "notification_status": status,
                "last_notified_at": datetime.now(timezone.utc),
            }
        },
    )
    return {**result, "alert_count": len(alerts)}


def _size_signature(sizes):
    return sorted(
        (
            normalize_size(size.get("name") or size.get("size")),
            bool(size.get("in_stock")),
        )
        for size in (sizes or [])
        if size.get("name") or size.get("size")
    )


def _values_changed(listing, data, stock_status):
    if listing.get("last_checked_at") is None:
        return True
    if listing.get("last_price") != data.get("current_price"):
        return True
    if listing.get("last_old_price") != data.get("old_price"):
        return True
    if listing.get("last_cart_price") != data.get("cart_price"):
        return True
    if stock_status_from_listing(listing) != stock_status:
        return True
    return _size_signature(listing.get("last_sizes")) != _size_signature(data.get("sizes"))


async def _period_low(db, listing_id, current_price, days):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    row = await db.price_history.find_one(
        {"listing_id": listing_id, "checked_at": {"$gte": cutoff}, "price": {"$ne": None}},
        {"_id": 0, "price": 1},
        sort=[("price", 1)],
    )
    if not row:
        return False
    try:
        return float(current_price) < float(row["price"])
    except (TypeError, ValueError):
        return False


async def _event_alerts(db, listing, data, stock_status, engine):
    alerts = []
    current_price = data.get("current_price")
    previous_price = listing.get("last_price")
    previous_status = stock_status_from_listing(listing)
    name = data.get("title") or listing.get("title") or "Isimsiz Urun"

    previous_valid = isinstance(previous_price, (int, float)) and 50 <= previous_price <= 200000
    if previous_valid and current_price and current_price < previous_price:
        drop_pct = round(((previous_price - current_price) / previous_price) * 100, 2)
        drop_amount = round(previous_price - current_price, 2)
        watches = await db.watch_queries.find(
            {"product_id": listing["product_id"], "active": True}, {"_id": 0}
        ).to_list(100)
        qualified_watches = []
        for watch in watches:
            minimum_percent = float(watch.get("minimum_drop_percent") or 0)
            minimum_amount = float(watch.get("minimum_drop_amount") or 0)
            if minimum_percent <= 0 and minimum_amount <= 0:
                continue
            size_ok, _ = _size_match(watch.get("desired_sizes") or [], data.get("sizes") or [])
            if watch.get("desired_sizes") and not size_ok:
                continue
            if drop_pct >= minimum_percent and drop_amount >= minimum_amount:
                qualified_watches.append(watch)
        alert_targets = qualified_watches or ([None] if drop_pct >= 3 else [])
        for watch in alert_targets:
            alert = await create_alert(
                db,
                alert_type="price_drop",
                title=f"Indirim radari: %{drop_pct:g} dusus",
                product_id=listing["product_id"],
                listing_id=listing["id"],
                watch_id=watch.get("id") if watch else None,
                product_name=name,
                store=engine.name,
                url=listing["url"],
                price=current_price,
                previous_price=previous_price,
                confidence=data.get("confidence") or 0.5,
                evidence=[
                    f"previous_price={previous_price}",
                    f"current_price={current_price}",
                    f"drop_amount={drop_amount}",
                ],
                detail=f"{(watch or {}).get('id', 'global')}:{previous_price}>{current_price}",
            )
            if alert:
                alerts.append(alert)

    if listing.get("last_checked_at") and previous_status != "in_stock" and stock_status == "in_stock":
        alert = await create_alert(
            db,
            alert_type="restock",
            title="Urun yeniden stokta",
            product_id=listing["product_id"],
            listing_id=listing["id"],
            product_name=name,
            store=engine.name,
            url=listing["url"],
            price=current_price,
            confidence=data.get("confidence") or 0.5,
            evidence=[f"stock:{previous_status}->in_stock"],
        )
        if alert:
            alerts.append(alert)

    cart_price = data.get("cart_price")
    shelf_price = data.get("current_price")
    if (
        isinstance(cart_price, (int, float))
        and isinstance(shelf_price, (int, float))
        and cart_price < shelf_price
        and listing.get("last_cart_price") != cart_price
    ):
        alert = await create_alert(
            db,
            alert_type="cart_price",
            title="Sepet fiyati normal fiyatın altina indi",
            product_id=listing["product_id"],
            listing_id=listing["id"],
            product_name=name,
            store=engine.name,
            url=listing["url"],
            price=cart_price,
            previous_price=shelf_price,
            price_type="Sepet indirimi",
            confidence=data.get("confidence") or 0.5,
            evidence=[f"shelf_price={shelf_price}", f"cart_price={cart_price}"],
            detail=str(cart_price),
        )
        if alert:
            alerts.append(alert)

    for days in (30, 90):
        if current_price and await _period_low(db, listing["id"], current_price, days):
            alert = await create_alert(
                db,
                alert_type="period_low",
                title=f"Son {days} gunun en dusuk fiyati",
                product_id=listing["product_id"],
                listing_id=listing["id"],
                product_name=name,
                store=engine.name,
                url=listing["url"],
                price=current_price,
                confidence=data.get("confidence") or 0.5,
                evidence=[f"period_days={days}"],
                detail=str(days),
            )
            if alert:
                alerts.append(alert)
    return alerts


async def check_listing(db, listing):
    engine = get_engine_for_url(listing["url"])
    base = {
        "listing_id": listing["id"],
        "product_id": listing["product_id"],
        "store": listing.get("store") or engine.name,
        "url": listing["url"],
        "title": listing.get("title"),
    }
    if await store_circuit_open(db, engine.slug):
        return {**base, "status": "deferred", "error": "Magaza devre kesicisi gecici olarak acik"}

    started = time.perf_counter()
    try:
        data = await engine.get_product_data(listing["url"])
    except Exception as exc:
        latency = (time.perf_counter() - started) * 1000
        message = str(exc)[:300]
        status = stock_status_from_values(error=message)
        if status == "blocked":
            user_message = "Magaza erisimi bot korumasi veya hiz siniri nedeniyle engelledi."
        elif status == "not_found":
            user_message = "Urun sayfasi bulunamadi veya yayindan kaldirildi."
        else:
            user_message = "Urun verisi okunamadi: " + message
        await db.listings.update_one(
            {"id": listing["id"]},
            {
                "$set": {
                    "last_error": user_message,
                    "last_checked_at": now_iso(),
                    "last_stock_status": status,
                    **({"last_in_stock": False, "last_stock_count": 0} if status == "not_found" else {}),
                }
            },
        )
        await record_store_result(db, engine.slug, status, latency_ms=latency)
        alert_type = "listing_missing" if status == "not_found" else "parser_failure"
        alert = await create_alert(
            db,
            alert_type=alert_type,
            title="Urun yayindan kalkti" if status == "not_found" else "Magaza verisi okunamiyor",
            product_id=listing["product_id"],
            listing_id=listing["id"],
            product_name=listing.get("title"),
            store=engine.name,
            url=listing["url"],
            confidence=1.0,
            evidence=[status, message[:160]],
        )
        await notify_alert(db, alert)
        return {**base, "status": status, "error": user_message}

    latency = (time.perf_counter() - started) * 1000
    stock_status = stock_status_from_values(
        stock_status=data.get("stock_status"),
        in_stock=data.get("in_stock"),
        sizes=data.get("sizes"),
        price=data.get("current_price"),
    )
    changed = _values_changed(listing, data, stock_status)
    update = {
        "last_price": data.get("current_price"),
        "last_old_price": data.get("old_price"),
        "last_cart_price": data.get("cart_price"),
        "last_price_source": data.get("price_source"),
        "last_confidence": data.get("confidence"),
        "last_stock_count": data.get("stock_count"),
        "last_in_stock": stock_status == "in_stock",
        "last_stock_status": stock_status,
        "last_sizes": data.get("sizes") or [],
        "last_raw": data.get("debug"),
        "last_error": None,
        "last_checked_at": now_iso(),
        "store": engine.name,
        "model_code": data.get("model_code"),
        "seller": data.get("seller"),
        "seller_rating": data.get("seller_rating"),
        "official_seller": data.get("official_seller"),
        "shipping": data.get("shipping"),
        "campaigns": data.get("campaigns") or [],
    }
    if data.get("title"):
        update["title"] = data["title"]
    if data.get("image"):
        update["image"] = data["image"]
    await db.listings.update_one({"id": listing["id"]}, {"$set": update})
    if data.get("image"):
        await db.products.update_one(
            {"id": listing["product_id"], "$or": [{"image": None}, {"image": ""}, {"image": {"$exists": False}}]},
            {"$set": {"image": data["image"]}},
        )

    event_alerts = await _event_alerts(db, listing, data, stock_status, engine)
    for alert in event_alerts:
        await notify_alert(db, alert)

    if data.get("current_price") is not None and changed:
        await db.price_history.insert_one(
            {
                "id": new_id(),
                "listing_id": listing["id"],
                "product_id": listing["product_id"],
                "store": engine.name,
                "price": data.get("current_price"),
                "old_price": data.get("old_price"),
                "cart_price": data.get("cart_price"),
                "price_source": data.get("price_source"),
                "confidence": data.get("confidence"),
                "stock_count": data.get("stock_count"),
                "stock_status": stock_status,
                "sizes_signature": _size_signature(data.get("sizes")),
                "checked_at": now_iso(),
            }
        )

    await record_store_result(
        db,
        engine.slug,
        "ok",
        latency_ms=latency,
        price_ok=data.get("current_price") is not None,
        stock_ok=stock_status in {"in_stock", "out_of_stock"},
        parser_version=getattr(engine, "parser_version", "1"),
    )
    return {
        **base,
        "title": update.get("title") or listing.get("title"),
        "status": "ok" if data.get("current_price") is not None else "no_price",
        "price": data.get("current_price"),
        "old_price": data.get("old_price"),
        "cart_price": data.get("cart_price"),
        "price_source": data.get("price_source"),
        "stock_count": data.get("stock_count"),
        "in_stock": stock_status == "in_stock",
        "stock_status": stock_status,
        "sizes": data.get("sizes") or [],
        "changed": changed,
    }


def _size_match(rule_sizes, sizes):
    wanted = {normalize_size(value) for value in (rule_sizes or []) if value and value != "-"}
    if not wanted:
        return None, None
    for size in sizes or []:
        label = size.get("name") or size.get("size")
        if normalize_size(label) in wanted:
            return bool(size.get("in_stock")), label
    return False, None


async def evaluate_product_rules(db, product_id):
    product = await db.products.find_one({"id": product_id, "active": True}, {"_id": 0})
    if not product:
        return []
    rules = await db.rules.find({"product_id": product_id, "enabled": True}, {"_id": 0}).to_list(100)
    listings = await db.listings.find({"product_id": product_id, "active": True}, {"_id": 0}).to_list(200)
    if not rules or not listings:
        return []

    alerts_created = []
    profile = await db.user_profile.find_one({"id": "main"}, {"_id": 0})
    history = (
        await db.price_history.find({"product_id": product_id}, {"_id": 0, "price": 1, "checked_at": 1})
        .sort("checked_at", 1)
        .to_list(2000)
    )

    family_listings = None
    family_names = {}
    family_key = product.get("family_key")
    if family_key and any(rule.get("spectrum_mode") for rule in rules):
        family_products = await db.products.find(
            {"family_key": family_key, "active": True}, {"_id": 0, "id": 1, "name": 1}
        ).to_list(100)
        family_ids = [item["id"] for item in family_products]
        family_names = {item["id"]: item["name"] for item in family_products}
        family_listings = await db.listings.find(
            {"product_id": {"$in": family_ids}, "active": True}, {"_id": 0}
        ).to_list(500)

    for rule in rules:
        hard_target = rule.get("hard_target_price", rule.get("target_price"))
        if hard_target is None:
            continue
        near_enabled = bool(rule.get("near_target_enabled", False))
        near_percent = max(0.0, min(50.0, float(rule.get("near_target_percent") or 0)))
        maximum_price = hard_target * (1 + near_percent / 100) if near_enabled else hard_target
        desired_sizes = rule.get("desired_sizes") or ([rule.get("size")] if rule.get("size") else [])
        scan = family_listings if rule.get("spectrum_mode") and family_listings else listings
        candidates = []
        for listing in scan:
            price_values = [
                value
                for value in (listing.get("last_price"), listing.get("last_cart_price"))
                if isinstance(value, (int, float)) and value > 0
            ]
            price = min(price_values) if price_values else None
            if price is None or price > maximum_price:
                continue
            if stock_status_from_listing(listing) != "in_stock":
                continue
            sizes = listing.get("last_sizes") or []
            size_match, matched_size = _size_match(desired_sizes, sizes)
            if desired_sizes and not size_match:
                continue
            if not desired_sizes:
                if sizes and not any(size.get("in_stock") for size in sizes):
                    continue
                matched_size = "Herhangi bir beden" if sizes else "Beden bilgisi yok"
            candidates.append((listing, price, matched_size))
        if not candidates:
            continue
        if rule.get("spectrum_mode"):
            candidates = [min(candidates, key=lambda item: item[1])]

        for listing, price, matched_size in candidates:
            is_near = price > hard_target
            alert_type = "near_target" if is_near else "target_price"
            display_name = family_names.get(listing["product_id"]) or product.get("name")
            insight = compute_price_insight(history, price, hard_target)
            decision = compute_buy_decision(listing, rule, insight, profile, display_name)
            title = "Hedefe yaklasti" if is_near else "Hedef fiyat yakalandi"
            campaign_types = {item.get("type") for item in (listing.get("campaigns") or [])}
            if listing.get("last_cart_price"):
                price_type = "Sepet indirimi"
            elif "coupon" in campaign_types:
                price_type = "Kuponlu fiyat"
            elif "membership" in campaign_types:
                price_type = "Uyelik fiyati"
            elif "bank" in campaign_types:
                price_type = "Banka kampanyasi"
            else:
                price_type = "Normal fiyat"
            alert = await create_alert(
                db,
                alert_type=alert_type,
                title=f"{title}: {display_name}",
                product_id=product_id,
                listing_id=listing["id"],
                rule_id=rule["id"],
                product_name=display_name,
                store=listing.get("store"),
                url=listing.get("url"),
                price=price,
                target_price=hard_target,
                size=matched_size,
                price_type=price_type,
                confidence=listing.get("last_confidence") or 0.5,
                evidence=[f"price<={maximum_price:.2f}", f"stock=in_stock", f"size={matched_size}"],
                cooldown_hours=float(rule.get("cooldown_hours") or 24),
                detail=rule["id"],
                extra={
                    "ai_decision": decision["decision"],
                    "ai_score": decision["score"],
                    "ai_comment": short_comment(decision),
                },
            )
            if alert:
                await notify_alert(db, alert)
                alerts_created.append(alert)
    return alerts_created


async def batch_check(db, trigger="manual", force=False):
    run_id = new_id()
    started_at = now_iso()
    now = datetime.now(timezone.utc)
    active_filter = {"active": True}
    due_filter = active_filter
    if not force:
        due_filter = {
            **active_filter,
            "$or": [
                {"next_refresh_at": {"$exists": False}},
                {"next_refresh_at": None},
                {"next_refresh_at": {"$lte": now}},
            ],
        }
    listings = await db.listings.find(due_filter, {"_id": 0}).to_list(2000)
    active_count = await db.listings.count_documents(active_filter)
    watch_ids = {watch_id for listing in listings for watch_id in (listing.get("watch_ids") or []) if watch_id}
    watches = (
        await db.watch_queries.find(
            {"id": {"$in": list(watch_ids)}, "active": True},
            {"_id": 0, "id": 1, "refresh_frequency_minutes": 1},
        ).to_list(len(watch_ids))
        if watch_ids
        else []
    )
    watch_refresh = {
        watch["id"]: max(30, min(1440, int(watch.get("refresh_frequency_minutes") or 360))) for watch in watches
    }
    settings = await get_settings(db)
    default_refresh = max(1, int((settings.get("scheduler") or {}).get("interval_minutes") or 30))
    global_sem = asyncio.Semaphore(max(1, int(os.environ.get("GLOBAL_FETCH_CONCURRENCY", "4"))))
    store_sems = {}

    async def check_one(listing):
        store_slug = listing.get("store_slug") or "generic"
        store_sem = store_sems.setdefault(store_slug, asyncio.Semaphore(2))
        async with global_sem, store_sem:
            result = await check_listing(db, listing)
            intervals = [watch_refresh[item] for item in listing.get("watch_ids") or [] if item in watch_refresh]
            refresh_minutes = min(intervals) if intervals else default_refresh
            await db.listings.update_one(
                {"id": listing["id"]},
                {"$set": {"next_refresh_at": datetime.now(timezone.utc) + timedelta(minutes=refresh_minutes)}},
            )
            return result

    results = await asyncio.gather(*[check_one(listing) for listing in listings]) if listings else []
    product_ids = {listing["product_id"] for listing in listings}
    all_alerts = []
    for product_id in product_ids:
        all_alerts.extend(await evaluate_product_rules(db, product_id))
    run = {
        "id": run_id,
        "trigger": trigger,
        "started_at": started_at,
        "finished_at": now_iso(),
        "total": len(results),
        "skipped_not_due": max(0, active_count - len(listings)),
        "success": sum(1 for result in results if result["status"] == "ok"),
        "failed": sum(1 for result in results if result["status"] in {"error", "blocked", "not_found"}),
        "deferred": sum(1 for result in results if result["status"] == "deferred"),
        "no_price": sum(1 for result in results if result["status"] == "no_price"),
        "unchanged": sum(1 for result in results if result.get("changed") is False),
        "alerts_created": len(all_alerts),
        "results": [{key: value for key, value in result.items() if key != "sizes"} for result in results],
    }
    await db.check_runs.insert_one(dict(run))
    run.pop("_id", None)
    return run, all_alerts
