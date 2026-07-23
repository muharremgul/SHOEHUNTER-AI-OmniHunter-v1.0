import asyncio
import json
import logging
import os
from typing import Any

logger = logging.getLogger("shoehunter.fcm")

FCM_PROJECT_ID = os.environ.get("FIREBASE_PROJECT_ID", "shophunter-radar").strip()
DEVELOPER_ONLY_ALERT_TYPES = {"parser_failure", "listing_missing"}


def _text(value: Any, limit: int = 700) -> str:
    return str(value or "").strip()[:limit]


def alert_notification_body(alert: dict) -> str:
    parts = [
        _text(alert.get("product_name") or "Ürün", 180),
        _text(alert.get("store") or "Mağaza", 100),
    ]
    sizes = [str(value).strip() for value in (alert.get("sizes") or []) if str(value).strip()]
    if not sizes and alert.get("size"):
        sizes = [_text(alert.get("size"), 40)]
    if sizes:
        parts.append(f"Numara/beden: {', '.join(sizes[:8])}")
    price = alert.get("price")
    if isinstance(price, (int, float)):
        parts.append(f"{float(price):,.2f} TL")
    return " · ".join(part for part in parts if part)[:900]


def alert_data_payload(alert: dict) -> dict[str, str]:
    sizes = [str(value).strip() for value in (alert.get("sizes") or []) if str(value).strip()]
    audience = [str(value).strip() for value in (alert.get("audience") or []) if str(value).strip()]
    return {
        "alert_id": _text(alert.get("id"), 120),
        "alert_type": _text(alert.get("alert_type"), 80),
        "title": _text(alert.get("title") or "ShopHunter Radar", 220),
        "notification_body": alert_notification_body(alert),
        "product_name": _text(alert.get("product_name"), 220),
        "store": _text(alert.get("store"), 120),
        "sizes": json.dumps(sizes[:12], ensure_ascii=False),
        "audience": json.dumps(audience[:12], ensure_ascii=False),
        "price": _text(alert.get("price"), 40),
        "url": _text(alert.get("url"), 1800),
    }


def _send_fids(fids: list[str], payload: dict[str, str]) -> dict:
    try:
        import firebase_admin
        from firebase_admin import messaging
    except ImportError:
        return {"sent": False, "skipped": True, "reason": "firebase_admin_yuklu_degil"}

    try:
        try:
            app = firebase_admin.get_app()
        except ValueError:
            app = firebase_admin.initialize_app(options={"projectId": FCM_PROJECT_ID})
    except Exception as exc:
        logger.warning("FCM baslatilamadi: %s", type(exc).__name__)
        return {"sent": False, "skipped": True, "reason": "firebase_kimligi_hazir_degil"}

    sent_count = 0
    invalid_fids: list[str] = []
    failure_count = 0
    last_error = None
    for fid in fids:
        message = messaging.Message(
            fid=fid,
            data=payload,
            android=messaging.AndroidConfig(priority="high"),
        )
        try:
            messaging.send(message, app=app)
            sent_count += 1
        except Exception as exc:
            failure_count += 1
            name = type(exc).__name__
            if name in {"UnregisteredError", "SenderIdMismatchError"}:
                invalid_fids.append(fid)
            last_error = name
            logger.warning("FCM gonderimi basarisiz: %s", name)
    return {
        "sent": sent_count > 0,
        "sent_count": sent_count,
        "failure_count": failure_count,
        "invalid_fids": invalid_fids,
        "error": last_error,
    }


async def send_fcm_alert(db, alert: dict | None) -> dict:
    if not alert:
        return {"sent": False, "skipped": True, "reason": "alarm_yok"}
    if alert.get("alert_type") in DEVELOPER_ONLY_ALERT_TYPES:
        return {"sent": False, "skipped": True, "reason": "gelistirici_alarmi"}
    if not FCM_PROJECT_ID:
        return {"sent": False, "skipped": True, "reason": "firebase_proje_kimligi_yok"}

    devices = await db.mobile_devices.find(
        {"enabled": True, "fcm_fid": {"$type": "string", "$ne": ""}},
        {"_id": 0, "fcm_fid": 1},
    ).to_list(500)
    fids = list(dict.fromkeys(row["fcm_fid"] for row in devices if row.get("fcm_fid")))
    if not fids:
        return {"sent": False, "skipped": True, "reason": "kayitli_fcm_cihazi_yok"}

    result = await asyncio.to_thread(_send_fids, fids, alert_data_payload(alert))
    invalid_fids = result.pop("invalid_fids", [])
    if invalid_fids:
        await db.mobile_devices.update_many(
            {"fcm_fid": {"$in": invalid_fids}},
            {
                "$set": {"fcm_invalid": True},
                "$unset": {"fcm_fid": "", "fcm_fid_hash": ""},
            },
        )
    return result
