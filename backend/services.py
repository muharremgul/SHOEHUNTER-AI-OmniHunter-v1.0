import asyncio
import os
import uuid
from datetime import datetime, timezone, timedelta

import httpx

from engines import get_engine_for_url
from insights import compute_price_insight, compute_buy_decision, short_comment
from family import make_family_key


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def new_id():
    return str(uuid.uuid4())


def default_settings():
    return {
        "id": "main",
        "telegram": {
            "enabled": True,
            "bot_token": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
            "chat_id": os.environ.get("TELEGRAM_CHAT_ID", ""),
        },
        "scheduler": {"enabled": False, "interval_minutes": 30},
        "updated_at": now_iso(),
    }


async def get_settings(db):
    doc = await db.settings.find_one({"id": "main"}, {"_id": 0})
    if not doc:
        doc = default_settings()
        await db.settings.insert_one(dict(doc))
        doc.pop("_id", None)
    return doc


async def send_telegram(db, text):
    settings = await get_settings(db)
    tg = settings.get("telegram", {})
    if not tg.get("enabled"):
        return {"sent": False, "skipped": True, "reason": "telegram_kapali"}
    token = (tg.get("bot_token") or "").strip()
    chat_id = str(tg.get("chat_id") or "").strip()
    if not token or not chat_id:
        return {"sent": False, "skipped": True, "reason": "token_veya_chat_id_eksik"}
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": False}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(url, json=payload)
            data = resp.json()
        if data.get("ok"):
            return {"sent": True}
        return {"sent": False, "error": str(data)}
    except Exception as exc:
        return {"sent": False, "error": str(exc)}


async def check_listing(db, listing):
    engine = get_engine_for_url(listing["url"])
    base = {
        "listing_id": listing["id"],
        "product_id": listing["product_id"],
        "store": listing.get("store") or engine.name,
        "url": listing["url"],
        "title": listing.get("title"),
    }
    try:
        data = await engine.get_product_data(listing["url"])
    except Exception as exc:
        msg = str(exc)[:300]
        update_doc = {"last_error": msg, "last_checked_at": now_iso()}
        if "403" in msg or "429" in msg:
            msg = "MaÄŸaza sunucu taraflÄ± eriÅŸimi engelliyor (bot korumasÄ±). FiyatÄ± 'elle fiyat gir' ile gÃ¼ncelleyebilirsiniz."
            update_doc["last_error"] = msg
        elif "404" in msg:
            msg = "ÃœrÃ¼n sayfasÄ± bulunamadÄ± (404). ÃœrÃ¼n yayÄ±ndan kaldÄ±rÄ±lmÄ±ÅŸ."
            update_doc["last_error"] = msg
            update_doc["last_in_stock"] = False
            update_doc["last_stock_count"] = 0

        await db.listings.update_one(
            {"id": listing["id"]},
            {"$set": update_doc},
        )
        return {**base, "status": "error", "error": msg}

    update = {
        "last_price": data["current_price"],
        "last_old_price": data["old_price"],
        "last_cart_price": data["cart_price"],
        "last_price_source": data["price_source"],
        "last_confidence": data["confidence"],
        "last_stock_count": data["stock_count"],
        "last_in_stock": data["in_stock"],
        "last_sizes": data["sizes"],
        "last_raw": data.get("debug"),
        "last_error": None,
        "last_checked_at": now_iso(),
        "store": engine.name,
    }
    if data.get("title") and not listing.get("title"):
        update["title"] = data["title"]
    if data.get("image") and not listing.get("image"):
        update["image"] = data["image"]
    await db.listings.update_one({"id": listing["id"]}, {"$set": update})
    if data.get("image"):
        await db.products.update_one(
            {"id": listing["product_id"], "$or": [{"image": None}, {"image": ""}, {"image": {"$exists": False}}]},
            {"$set": {"image": data["image"]}},
        )

    if data["current_price"] is not None:
        last_p = listing.get("last_price")
        curr_p = data["current_price"]

        last_p_valid = (
            isinstance(last_p, (int, float))
            and 50 <= last_p <= 200000
            and last_p <= curr_p * 5
        )

        # Evrensel Indirim Radari: Fiyat son degere gore %3 veya daha fazla duserse
        if last_p_valid and curr_p < last_p * 0.97:
            drop_pct = round(((last_p - curr_p) / last_p) * 100)
            p_name = update.get("title") or listing.get("title") or "Ä°simsiz ÃœrÃ¼n"
            alert = {
                "id": new_id(),
                "rule_id": "universal_radar",
                "product_id": listing["product_id"],
                "listing_id": listing["id"],
                "title": f"ğŸ“‰ Ä°NDÄ°RÄ°M RADARI: %{drop_pct} DÃ¼ÅŸÃ¼ÅŸ!",
                "product_name": p_name,
                "store": engine.name,
                "url": listing["url"],
                "price": curr_p,
                "previous_price": last_p,
                "target_price": None,
                "size": "TÃ¼mÃ¼",
                "price_type": "Normal fiyat",
                "ai_decision": "STRONG_BUY",
                "ai_score": 90,
                "ai_comment": f"Fiyat {last_p} TL'den {curr_p} TL'ye dÃ¼ÅŸtÃ¼! (Kuraldan baÄŸÄ±msÄ±z otomatik uyarÄ±)",
                "telegram_sent": False,
                "created_at": now_iso()
            }
            await db.alerts.insert_one(dict(alert))
            tg_text = (
                f"ğŸ“‰ <b>Ä°NDÄ°RÄ°M YAKALANDI! (%{drop_pct})</b>\n\n"
                f"ğŸ· <b>ÃœrÃ¼n:</b> {p_name}\n"
                f"âŒ <b>Eski:</b> {last_p} TL\n"
                f"âœ… <b>Yeni:</b> {curr_p} TL\n"
                f"ğŸª <b>MaÄŸaza:</b> {engine.name}\n"
                f"ğŸ”— <a href='{listing['url']}'>ÃœrÃ¼ne Git</a>"
            )
            tg_res = await send_telegram(db, tg_text)
            if tg_res.get("sent"):
                await db.alerts.update_one({"id": alert["id"]}, {"$set": {"telegram_sent": True}})

        await db.price_history.insert_one(
            {
                "id": new_id(),
                "listing_id": listing["id"],
                "product_id": listing["product_id"],
                "store": engine.name,
                "price": curr_p,
                "old_price": data["old_price"],
                "cart_price": data["cart_price"],
                "price_source": data["price_source"],
                "confidence": data["confidence"],
                "stock_count": data["stock_count"],
                "checked_at": now_iso(),
            }
        )

    return {
        **base,
        "title": update.get("title") or listing.get("title"),
        "status": "ok" if data["current_price"] is not None else "no_price",
        "price": data["current_price"],
        "old_price": data["old_price"],
        "cart_price": data["cart_price"],
        "price_source": data["price_source"],
        "stock_count": data["stock_count"],
        "in_stock": data["in_stock"],
        "sizes": data["sizes"],
    }


def normalize_size(s):
    if not s:
        return "-"
    return str(s).replace(",", ".").strip().upper()


def _size_match(rule_size, sizes):
    rule_norm = normalize_size(rule_size)
    for s in sizes or []:
        if normalize_size(s.get("name") or s.get("size")) == rule_norm:
            return bool(s.get("in_stock")), s.get("name")
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
    history = await db.price_history.find(
        {"product_id": product_id}, {"_id": 0, "price": 1, "checked_at": 1}
    ).sort("checked_at", 1).to_list(2000)

    # Spektrum modu icin urun ailesi (ayni modelin tum renkleri)
    family_listings = None
    family_names = {}
    fam_key = product.get("family_key")
    if fam_key and any(r.get("spectrum_mode") for r in rules):
        fam_products = await db.products.find(
            {"family_key": fam_key, "active": True}, {"_id": 0, "id": 1, "name": 1}
        ).to_list(100)
        fam_ids = [p["id"] for p in fam_products]
        family_names = {p["id"]: p["name"] for p in fam_products}
        family_listings = await db.listings.find(
            {"product_id": {"$in": fam_ids}, "active": True}, {"_id": 0}
        ).to_list(500)

    for rule in rules:
        target = rule.get("target_price")
        if target is None:
            continue
        scan_listings = family_listings if (rule.get("spectrum_mode") and family_listings) else listings
        candidates = []
        for listing in scan_listings:
            price = listing.get("last_price")
            # Hedefin %10 ustune kadar tolerans tani (1 lira sorunu icin esneklik)
            if price is None or price > target * 1.10:
                continue
            sizes = listing.get("last_sizes") or []
            matched_size = None
            if rule.get("size") and rule["size"] != "-":
                ok, matched = _size_match(rule["size"], sizes)
                if not ok:
                    continue
                matched_size = matched
            else:
                if sizes:
                    stocked = [s for s in sizes if s.get("in_stock")]
                    if not stocked:
                        continue
                    matched_size = "Herhangi bir beden"
                else:
                    if not listing.get("last_in_stock"):
                        continue
                    matched_size = "Beden bilgisi yok"
            candidates.append((listing, price, matched_size))

        if not candidates:
            continue
        if rule.get("spectrum_mode"):
            candidates = [min(candidates, key=lambda c: c[1])]

        cooldown = float(rule.get("cooldown_hours") or 24)
        for listing, price, matched_size in candidates:
            last_alert = await db.alerts.find_one(
                {"rule_id": rule["id"], "listing_id": listing["id"]},
                {"_id": 0, "created_at": 1},
                sort=[("created_at", -1)],
            )
            if last_alert:
                try:
                    prev = datetime.fromisoformat(last_alert["created_at"])
                    if datetime.now(timezone.utc) - prev < timedelta(hours=cooldown):
                        continue
                except (ValueError, TypeError):
                    pass

            price_type = "Sepet indirimi" if listing.get("last_cart_price") else "Normal fiyat"
            display_name = family_names.get(listing["product_id"]) or product.get("name")
            insight = compute_price_insight(history, price, target)
            decision = compute_buy_decision(listing, rule, insight, profile, display_name)
            ai_comment = short_comment(decision)

            is_tolerance = price > target
            title_prefix = "ğŸ¯ HEDEFE YAKLAÅTI" if is_tolerance else "âœ… HEDEF YAKALANDI"

            alert = {
                "id": new_id(),
                "rule_id": rule["id"],
                "product_id": product_id,
                "listing_id": listing["id"],
                "title": f"{title_prefix}: {display_name}",
                "product_name": display_name,
                "store": listing.get("store"),
                "url": listing.get("url"),
                "price": price,
                "target_price": target,
                "size": matched_size,
                "price_type": price_type,
                "ai_decision": decision["decision"],
                "ai_score": decision["score"],
                "ai_comment": ai_comment,
                "telegram_sent": False,
                "is_read": False,
                "created_at": now_iso(),
            }
            message = (
                "\U0001f45f <b>ShoeHunter AI Ä°ndirim YakaladÄ±!</b>\n\n"
                f"<b>ÃœrÃ¼n:</b> {display_name}\n"
                f"<b>MaÄŸaza:</b> {listing.get('store')}\n"
                f"<b>Beden:</b> {matched_size}\n"
                f"<b>GÃ¼ncel fiyat:</b> {price:.2f} TL \U0001f525\n"
                f"<b>Hedef fiyat:</b> {target:.2f} TL\n"
                f"<b>Fiyat tipi:</b> {price_type}\n"
                f"<b>Stok durumu:</b> Bildirim anÄ±nda stokta gÃ¶rÃ¼nÃ¼yordu\n\n"
                f"\U0001f916 <b>AI Yorumu:</b> {ai_comment}\n\n"
                f"\U0001f6d2 <a href='{listing.get('url')}'>ÃœrÃ¼ne Git</a>"
            )
            tg_result = await send_telegram(db, message)
            alert["telegram_sent"] = bool(tg_result.get("sent"))
            alert["telegram_error"] = tg_result.get("error") or tg_result.get("reason")
            await db.alerts.insert_one(dict(alert))
            alert.pop("_id", None)
            alerts_created.append(alert)
    return alerts_created


async def batch_check(db, trigger="manual"):
    run_id = new_id()
    started_at = now_iso()
    listings = await db.listings.find({"active": True}, {"_id": 0}).to_list(500)

    sem = asyncio.Semaphore(4)

    async def _check(listing):
        async with sem:
            return await check_listing(db, listing)

    results = await asyncio.gather(*[_check(l) for l in listings]) if listings else []

    product_ids = {l["product_id"] for l in listings}
    all_alerts = []
    for pid in product_ids:
        alerts = await evaluate_product_rules(db, pid)
        all_alerts.extend(alerts)

    run = {
        "id": run_id,
        "trigger": trigger,
        "started_at": started_at,
        "finished_at": now_iso(),
        "total": len(results),
        "success": sum(1 for r in results if r["status"] == "ok"),
        "failed": sum(1 for r in results if r["status"] == "error"),
        "no_price": sum(1 for r in results if r["status"] == "no_price"),
        "alerts_created": len(all_alerts),
        "results": [{k: v for k, v in r.items() if k != "sizes"} for r in results],
    }
    await db.check_runs.insert_one(dict(run))
    run.pop("_id", None)
    return run, all_alerts
