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
from product_identity import identity_from_title, normalize_size
from secret_store import get_secret
from size_profiles import (
    available_size_labels,
    matching_size_labels,
    newly_available_size_labels,
    size_label_for_category,
    watch_audience_for_sizes,
)
from store_health import record_store_result, store_circuit_open

logger = logging.getLogger("shoehunter.services")
GLOBAL_PRICE_DROP_PERCENT = 3.0


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
            "discovery_interval_hours": 6,
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


async def send_telegram(db, text, reply_markup=None):
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
    if reply_markup:
        payload["reply_markup"] = reply_markup
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


DEVELOPER_ONLY_ALERT_TYPES = {"parser_failure", "listing_missing"}
TELEGRAM_FEEDBACK_CODES = {"bought", "no_size", "wrong"}


def telegram_feedback_keyboard(alert_id):
    return {
        "inline_keyboard": [
            [
                {"text": "Satın aldım", "callback_data": f"feedback:{alert_id}:bought"},
                {"text": "Beden yoktu", "callback_data": f"feedback:{alert_id}:no_size"},
                {"text": "Yanlış ürün", "callback_data": f"feedback:{alert_id}:wrong"},
            ]
        ]
    }


async def notify_alert(db, alert):
    if not alert:
        return None
    if os.environ.get("NOTIFICATION_MODE", "immediate").strip().lower() == "digest":
        return {"sent": False, "queued": True, "reason": "digest_mode"}
    if alert.get("alert_type") in DEVELOPER_ONLY_ALERT_TYPES:
        logger.warning(
            "Gelistirici alarmi Telegram'a gonderilmedi: type=%s listing=%s",
            alert.get("alert_type"),
            alert.get("listing_id"),
        )
        await db.alerts.update_one(
            {"id": alert["id"]},
            {"$set": {"telegram_sent": False, "notification_status": "dev_only"}},
        )
        return {"sent": False, "skipped": True, "reason": "developer_only_alert"}
    result = await send_telegram(
        db,
        telegram_alert_message(alert),
        reply_markup=telegram_feedback_keyboard(alert["id"]),
    )
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
    if (listing.get("last_cart_price_conditions") or []) != (data.get("cart_price_conditions") or []):
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


async def _historical_low(db, listing_id):
    row = await db.price_history.find_one(
        {"listing_id": listing_id, "price": {"$ne": None}},
        {"_id": 0, "price": 1},
        sort=[("price", 1)],
    )
    if not row:
        return None
    try:
        return float(row["price"])
    except (TypeError, ValueError):
        return None


def _watch_size_context(watch, available_sizes):
    matched = matching_size_labels((watch or {}).get("desired_sizes"), available_sizes)
    if (watch or {}).get("desired_sizes") and not matched:
        return None
    return {
        "sizes": matched,
        "size": matched[0] if matched else None,
        "size_label": (watch or {}).get("size_label")
        or size_label_for_category((watch or {}).get("category")),
        "audience": watch_audience_for_sizes(watch, matched),
    }


def _combined_size_context(watches, available_sizes):
    audience = []
    size_label = "Beden / numara"
    for watch in watches or []:
        context = _watch_size_context(watch, available_sizes)
        if not context:
            continue
        size_label = context["size_label"]
        for name in context["audience"]:
            if name not in audience:
                audience.append(name)
    return {
        "sizes": list(available_sizes or [])[:12],
        "size": (available_sizes or [None])[0],
        "size_label": size_label,
        "audience": audience,
    }


async def _event_alerts(db, listing, data, stock_status, engine):
    alerts = []
    current_price = data.get("current_price")
    previous_price = listing.get("last_price")
    previous_status = stock_status_from_listing(listing)
    name = data.get("title") or listing.get("title") or "Isimsiz Urun"
    current_available_sizes = available_size_labels(data.get("sizes"))
    newly_available_sizes = newly_available_size_labels(listing.get("last_sizes"), data.get("sizes"))
    preliminary_stock_transition = bool(
        listing.get("last_checked_at") and previous_status != "in_stock" and stock_status == "in_stock"
    )
    previous_valid = isinstance(previous_price, (int, float)) and 50 <= previous_price <= 200000
    price_drop_is_actionable = bool(
        previous_valid
        and current_price
        and current_price < previous_price
        and float(data.get("confidence") or 0.5) >= 0.65
    )
    needs_watch_context = bool(
        price_drop_is_actionable
        or current_available_sizes
        or newly_available_sizes
        or preliminary_stock_transition
    )
    watches = (
        await db.watch_queries.find(
            {"product_id": listing["product_id"], "active": True}, {"_id": 0}
        ).to_list(100)
        if needs_watch_context
        else []
    )
    general_size_context = _combined_size_context(watches, current_available_sizes)

    if previous_valid and current_price and current_price < previous_price:
        drop_pct = round(((previous_price - current_price) / previous_price) * 100, 2)
        drop_amount = round(previous_price - current_price, 2)
        confidence = float(data.get("confidence") or 0.5)
        alert_targets = []
        if confidence < 0.65:
            logger.info(
                "Dusuk guvenli fiyat dususu alarmi atlandi: confidence=%.2f listing=%s source=%s",
                confidence,
                listing.get("id"),
                data.get("price_source"),
            )
        else:
            qualified_watches = []
            for watch in watches:
                minimum_percent = float(watch.get("minimum_drop_percent") or 0)
                minimum_amount = float(watch.get("minimum_drop_amount") or 0)
                size_ok, _ = _size_match(watch.get("desired_sizes") or [], data.get("sizes") or [])
                if watch.get("desired_sizes") and not size_ok:
                    continue
                required_percent = (
                    minimum_percent
                    if minimum_percent > 0
                    else (0 if minimum_amount > 0 else GLOBAL_PRICE_DROP_PERCENT)
                )
                if drop_pct >= required_percent and drop_amount >= minimum_amount:
                    qualified_watches.append(watch)
            alert_targets = qualified_watches or ([None] if drop_pct >= GLOBAL_PRICE_DROP_PERCENT else [])
        for watch in alert_targets:
            size_context = (
                _watch_size_context(watch, current_available_sizes) if watch else general_size_context
            ) or general_size_context
            tracked_size_drop = bool(watch and watch.get("desired_sizes") and size_context.get("sizes"))
            alert = await create_alert(
                db,
                alert_type="tracked_size_price_drop" if tracked_size_drop else "price_drop",
                title=(
                    f"Fiyat %{drop_pct:g} dustu ve takip edilen beden mevcut"
                    if tracked_size_drop
                    else f"Indirim radari: %{drop_pct:g} dusus"
                ),
                product_id=listing["product_id"],
                listing_id=listing["id"],
                watch_id=watch.get("id") if watch else None,
                product_name=name,
                store=engine.name,
                url=listing["url"],
                price=current_price,
                previous_price=previous_price,
                **size_context,
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

    stock_transition = preliminary_stock_transition
    size_event_candidates = newly_available_sizes or (current_available_sizes if stock_transition else [])
    size_event_count = 0
    if size_event_candidates:
        historical_low = await _historical_low(db, listing["id"])
        old_price = data.get("old_price")
        cart_price_candidate = data.get("cart_price")
        price_candidates = [
            value
            for value in (current_price, cart_price_candidate)
            if isinstance(value, (int, float)) and value > 0
        ]
        effective_price = min(price_candidates) if price_candidates else None
        discounted_or_low = bool(
            effective_price is not None
            and (
                (isinstance(old_price, (int, float)) and old_price > effective_price)
                or (historical_low is not None and effective_price <= historical_low)
            )
        )
        color_detected = bool(identity_from_title(name).color_tokens)
        single_variant_return = bool(stock_transition and len(current_available_sizes) == 1 and color_detected)
        for watch in watches:
            size_context = _watch_size_context(watch, size_event_candidates)
            if not size_context:
                continue
            if single_variant_return:
                alert_type = "single_variant_restock"
                title = (
                    "Tek renk/tek beden dusuk fiyattan geri geldi"
                    if discounted_or_low
                    else "Tek renk/tek beden geri geldi"
                )
            elif discounted_or_low:
                alert_type = "discounted_restock"
                title = "Dusuk fiyattan beden yeniden stokta"
            else:
                alert_type = "size_restock"
                title = "Takip edilen beden yeniden stokta"
            alert = await create_alert(
                db,
                alert_type=alert_type,
                title=title,
                product_id=listing["product_id"],
                listing_id=listing["id"],
                watch_id=watch.get("id"),
                product_name=name,
                store=engine.name,
                url=listing["url"],
                price=effective_price,
                previous_price=previous_price,
                price_type=(
                    "Sepet indirimi"
                    if effective_price == cart_price_candidate and cart_price_candidate != current_price
                    else "Normal fiyat"
                ),
                confidence=data.get("confidence") or 0.5,
                evidence=[
                    f"stock:{previous_status}->{stock_status}",
                    f"new_sizes={','.join(size_context['sizes'])}",
                    f"historical_low={historical_low}",
                ],
                detail=f"{watch.get('id')}:{','.join(size_context['sizes'])}:{effective_price}",
                **size_context,
            )
            if alert:
                alerts.append(alert)
                size_event_count += 1

    if stock_transition and size_event_count == 0:
        fallback_single_variant = bool(
            len(current_available_sizes) == 1 and identity_from_title(name).color_tokens
        )
        alert = await create_alert(
            db,
            alert_type=(
                "single_variant_restock"
                if fallback_single_variant
                else ("size_restock" if current_available_sizes else "restock")
            ),
            title=(
                "Tek renk/tek beden geri geldi"
                if fallback_single_variant
                else ("Beden yeniden stokta" if current_available_sizes else "Urun yeniden stokta")
            ),
            product_id=listing["product_id"],
            listing_id=listing["id"],
            product_name=name,
            store=engine.name,
            url=listing["url"],
            price=current_price,
            confidence=data.get("confidence") or 0.5,
            evidence=[f"stock:{previous_status}->in_stock"],
            **general_size_context,
        )
        if alert:
            alerts.append(alert)

    cart_price = data.get("cart_price")
    shelf_price = data.get("current_price")
    cart_offer_active = bool(
        isinstance(cart_price, (int, float))
        and isinstance(shelf_price, (int, float))
        and cart_price < shelf_price
        and not (data.get("cart_price_conditions") or [])
    )
    if cart_offer_active and listing.get("last_cart_price") != cart_price:
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
            **general_size_context,
            confidence=data.get("cart_price_confidence") or data.get("confidence") or 0.5,
            evidence=[
                f"shelf_price={shelf_price}",
                f"cart_price={cart_price}",
                f"cart_source={data.get('cart_price_source') or 'visible_offer'}",
            ],
            detail=str(cart_price),
        )
        if alert:
            alerts.append(alert)
    elif cart_offer_active and listing.get("last_checked_at") and listing.get("last_cart_price") == cart_price:
        alert = await create_alert(
            db,
            alert_type="cart_price_continues",
            title="Sepette indirimli fiyat devam ediyor",
            product_id=listing["product_id"],
            listing_id=listing["id"],
            product_name=name,
            store=engine.name,
            url=listing["url"],
            price=cart_price,
            previous_price=shelf_price,
            price_type="Sepet indirimi devam ediyor",
            **general_size_context,
            confidence=data.get("cart_price_confidence") or data.get("confidence") or 0.5,
            evidence=[
                f"shelf_price={shelf_price}",
                f"cart_price={cart_price}",
                "cart_offer=continued",
            ],
            detail=f"continued:{cart_price}",
        )
        if alert:
            alerts.append(alert)

    effective_deal_price = (
        cart_price if isinstance(cart_price, (int, float)) and cart_price > 0 else current_price
    )
    has_visible_discount = bool(
        isinstance(effective_deal_price, (int, float))
        and (
            (
                isinstance(data.get("old_price"), (int, float))
                and data["old_price"] > effective_deal_price
            )
            or (previous_valid and previous_price > effective_deal_price)
            or (
                isinstance(cart_price, (int, float))
                and isinstance(current_price, (int, float))
                and cart_price < current_price
            )
        )
    )
    if len(current_available_sizes) == 1 and has_visible_discount:
        only_size = current_available_sizes
        for watch in (watches or [None]):
            size_context = (
                _watch_size_context(watch, only_size) if watch else general_size_context
            )
            if not size_context:
                continue
            alert = await create_alert(
                db,
                alert_type="last_size_deal",
                title="Son beden indirim firsati",
                product_id=listing["product_id"],
                listing_id=listing["id"],
                watch_id=watch.get("id") if watch else None,
                product_name=name,
                store=engine.name,
                url=listing["url"],
                price=effective_deal_price,
                previous_price=data.get("old_price") or previous_price,
                price_type=(
                    "Sepet indirimi"
                    if effective_deal_price == cart_price and cart_price != current_price
                    else "Indirimli fiyat"
                ),
                confidence=data.get("confidence") or 0.5,
                evidence=[f"only_size={only_size[0]}", f"effective_price={effective_deal_price}"],
                detail=f"{(watch or {}).get('id', 'global')}:{only_size[0]}:{effective_deal_price}",
                **size_context,
            )
            if alert:
                alerts.append(alert)

    previous_available_sizes = available_size_labels(listing.get("last_sizes"))
    current_stock_count = data.get("stock_count")
    previous_stock_count = listing.get("last_stock_count")
    current_inventory_signal = (
        int(current_stock_count)
        if isinstance(current_stock_count, (int, float)) and current_stock_count > 0
        else len(current_available_sizes)
    )
    previous_inventory_signal = (
        int(previous_stock_count)
        if isinstance(previous_stock_count, (int, float)) and previous_stock_count > 0
        else len(previous_available_sizes)
    )
    became_critical = bool(
        listing.get("last_checked_at")
        and not stock_transition
        and current_inventory_signal in {1, 2}
        and previous_inventory_signal > current_inventory_signal
    )
    if became_critical:
        for watch in (watches or [None]):
            size_context = (
                _watch_size_context(watch, current_available_sizes) if watch else general_size_context
            )
            if not size_context:
                continue
            alert = await create_alert(
                db,
                alert_type="critical_stock",
                title="Takip edilen urunde stok kritik seviyede",
                product_id=listing["product_id"],
                listing_id=listing["id"],
                watch_id=watch.get("id") if watch else None,
                product_name=name,
                store=engine.name,
                url=listing["url"],
                price=effective_deal_price,
                confidence=data.get("confidence") or 0.5,
                evidence=[
                    f"inventory:{previous_inventory_signal}->{current_inventory_signal}",
                    f"available_sizes={','.join(current_available_sizes)}",
                ],
                detail=(
                    f"{(watch or {}).get('id', 'global')}:{current_inventory_signal}:"
                    f"{','.join(current_available_sizes)}"
                ),
                **size_context,
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
                **general_size_context,
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
        await record_store_result(
            db,
            engine.slug,
            status,
            latency_ms=latency,
            error=message,
            source="product_detail",
        )
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
        "last_cart_price_source": data.get("cart_price_source"),
        "last_cart_price_confidence": data.get("cart_price_confidence"),
        "last_cart_price_conditions": data.get("cart_price_conditions") or [],
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
                "cart_price_source": data.get("cart_price_source"),
                "cart_price_confidence": data.get("cart_price_confidence"),
                "cart_price_conditions": data.get("cart_price_conditions") or [],
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
        source="product_detail",
    )
    return {
        **base,
        "title": update.get("title") or listing.get("title"),
        "status": "ok" if data.get("current_price") is not None else "no_price",
        "price": data.get("current_price"),
        "old_price": data.get("old_price"),
        "cart_price": data.get("cart_price"),
        "cart_price_source": data.get("cart_price_source"),
        "cart_price_confidence": data.get("cart_price_confidence"),
        "cart_price_conditions": data.get("cart_price_conditions") or [],
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
                sizes=[matched_size] if matched_size else [],
                size_label=rule.get("size_label") or size_label_for_category(rule.get("category")),
                audience=watch_audience_for_sizes(rule, [matched_size] if matched_size else []),
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
