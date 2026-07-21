import hashlib
import html
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from pymongo.errors import DuplicateKeyError

from size_profiles import alert_size_text

DEFAULT_COOLDOWNS = {
    "target_price": 24,
    "near_target": 24,
    "price_drop": 12,
    "cart_price": 12,
    "restock": 12,
    "size_restock": 6,
    "discounted_restock": 6,
    "single_variant_restock": 6,
    "last_size_deal": 12,
    "tracked_size_price_drop": 12,
    "cart_price_continues": 24,
    "critical_stock": 12,
    "new_listing": 24,
    "new_variant": 24,
    "period_low": 24,
    "listing_missing": 48,
    "parser_failure": 24,
}


def now_utc():
    return datetime.now(timezone.utc)


def make_deduplication_key(alert_type, product_id=None, listing_id=None, watch_id=None, detail=None):
    raw = "|".join(str(value or "-") for value in (alert_type, product_id, listing_id, watch_id, detail))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def create_alert(
    db,
    *,
    alert_type,
    title,
    product_id=None,
    listing_id=None,
    watch_id=None,
    rule_id=None,
    product_name=None,
    store=None,
    url=None,
    price=None,
    previous_price=None,
    target_price=None,
    size=None,
    sizes=None,
    size_label=None,
    audience=None,
    price_type=None,
    confidence=1.0,
    evidence=None,
    cooldown_hours=None,
    detail=None,
    extra=None,
):
    now = now_utc()
    cooldown = float(cooldown_hours if cooldown_hours is not None else DEFAULT_COOLDOWNS.get(alert_type, 24))
    dedupe = make_deduplication_key(alert_type, product_id, listing_id, watch_id, detail)
    existing = await db.alerts.find_one({"deduplication_key": dedupe}, {"_id": 0})
    if existing:
        last_seen = existing.get("last_seen_at") or existing.get("created_at")
        if isinstance(last_seen, str):
            try:
                last_seen = datetime.fromisoformat(last_seen)
            except ValueError:
                last_seen = None
        if isinstance(last_seen, datetime) and last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=timezone.utc)
        await db.alerts.update_one(
            {"deduplication_key": dedupe},
            {
                "$set": {
                    "last_seen_at": now,
                    "price": price,
                    "previous_price": previous_price,
                    "evidence": evidence or existing.get("evidence") or [],
                    "confidence": confidence,
                    "size": size or existing.get("size"),
                    "sizes": sizes or existing.get("sizes") or [],
                    "size_label": size_label or existing.get("size_label"),
                    "audience": audience or existing.get("audience") or [],
                },
                "$inc": {"occurrence_count": 1},
            },
        )
        if last_seen and now - last_seen < timedelta(hours=cooldown):
            return None
        await db.alerts.update_one(
            {"deduplication_key": dedupe},
            {"$set": {"is_read": False, "notification_status": "pending", "last_notified_at": now}},
        )
        return await db.alerts.find_one({"deduplication_key": dedupe}, {"_id": 0})

    doc = {
        "id": hashlib.sha256(f"{dedupe}|{now.isoformat()}".encode()).hexdigest()[:32],
        "alert_type": alert_type,
        "deduplication_key": dedupe,
        "rule_id": rule_id,
        "watch_id": watch_id,
        "product_id": product_id,
        "listing_id": listing_id,
        "title": title,
        "product_name": product_name,
        "store": store,
        "url": url,
        "price": price,
        "previous_price": previous_price,
        "target_price": target_price,
        "size": size,
        "sizes": sizes or ([size] if size else []),
        "size_label": size_label or "Beden / numara",
        "audience": audience or [],
        "price_type": price_type,
        "confidence": round(float(confidence or 0), 4),
        "evidence": evidence or [],
        "cooldown_hours": cooldown,
        "notification_status": "pending",
        "telegram_sent": False,
        "is_read": False,
        "occurrence_count": 1,
        "first_seen_at": now,
        "last_seen_at": now,
        "created_at": now,
    }
    if extra:
        doc.update(extra)
    try:
        await db.alerts.insert_one(dict(doc))
    except DuplicateKeyError:
        return None
    return doc


def safe_external_url(url):
    parsed = urlparse(str(url or ""))
    if parsed.scheme != "https" or not parsed.hostname:
        return None
    return parsed.geturl()


def telegram_alert_message(alert):
    title = html.escape(str(alert.get("title") or "ShoeHunter bildirimi"))
    product = html.escape(str(alert.get("product_name") or "Urun"))
    store = html.escape(str(alert.get("store") or "Bilinmiyor"))
    sizes = alert.get("sizes") or ([alert.get("size")] if alert.get("size") else [])
    size = html.escape(alert_size_text(sizes))
    size_label = html.escape(str(alert.get("size_label") or "Beden / numara"))
    audience = [html.escape(str(value)) for value in (alert.get("audience") or []) if value]
    price = alert.get("price")
    price_text = f"{float(price):,.2f} TL" if isinstance(price, (int, float)) else "Bilinmiyor"
    lines = [f"<b>{title}</b>", "", f"<b>Urun:</b> {product}", f"<b>Magaza:</b> {store}"]
    lines.append(f"<b>{size_label}:</b> {size}")
    if audience:
        lines.append(f"<b>Kimin icin:</b> {', '.join(audience)}")
    lines.append(f"<b>Fiyat:</b> {html.escape(price_text)}")
    safe_url = safe_external_url(alert.get("url"))
    if safe_url:
        lines.extend(["", f"<a href='{html.escape(safe_url, quote=True)}'>Urune Git</a>"])
    return "\n".join(lines)


async def pending_alert_digest(db, limit=20):
    alerts = await db.alerts.find({"notification_status": "pending"}, {"_id": 0}).sort("created_at", 1).to_list(limit)
    if not alerts:
        return None, []
    grouped: dict[str, list[dict]] = {}
    for alert in alerts:
        key = str(alert.get("product_id") or alert.get("watch_id") or alert.get("product_name") or "unknown")
        grouped.setdefault(key, []).append(alert)
    lines = ["<b>ShoeHunter firsat ozeti</b>"]
    for items in grouped.values():
        name = html.escape(str(items[0].get("product_name") or "Urun"))
        lines.append(f"\n<b>{name}</b> icin {len(items)} gelisme")

        def price_key(item: dict) -> float:
            value = item.get("price")
            return float(value) if isinstance(value, (int, float)) else float("inf")

        for alert in sorted(items, key=price_key)[:5]:
            store = html.escape(str(alert.get("store") or "Magaza"))
            price = alert.get("price")
            price_text = f"{price:,.2f} TL" if isinstance(price, (int, float)) else "fiyat belirsiz"
            sizes = alert.get("sizes") or ([alert.get("size")] if alert.get("size") else [])
            size_text = html.escape(alert_size_text(sizes))
            lines.append(f"- {store}: {html.escape(price_text)} | Beden/numara: {size_text}")
    return "\n".join(lines), alerts
