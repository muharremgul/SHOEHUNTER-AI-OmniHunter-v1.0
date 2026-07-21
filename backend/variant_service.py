import asyncio

from alerting import create_alert
from engines import get_engine_for_url
from product_identity import ProductIdentity, canonicalize_product_url, identity_from_title, match_identities
from security import validate_remote_url
from services import evaluate_product_rules, new_id, notify_alert, now_iso, stock_status_from_values
from size_profiles import available_size_labels, size_label_for_category


def _product_identity(product):
    raw = product.get("identity")
    if isinstance(raw, dict):
        try:
            return ProductIdentity(**raw)
        except TypeError:
            pass
    return identity_from_title(product.get("name"), brand=product.get("brand"))


async def discover_product_variants(db, product_id, urls):
    product = await db.products.find_one({"id": product_id}, {"_id": 0})
    if not product:
        raise ValueError("Urun bulunamadi")
    expected = _product_identity(product)
    created = 0
    skipped = 0
    for raw_url in list(dict.fromkeys(urls or []))[:100]:
        try:
            engine = get_engine_for_url(raw_url)
            url = canonicalize_product_url(await validate_remote_url(raw_url, engine.domains))
            if await db.listings.find_one({"url": url}, {"_id": 0, "id": 1}):
                skipped += 1
                continue
            data = await asyncio.wait_for(engine.get_product_data(url), timeout=40)
            title = data.get("title") or ""
            candidate_identity = identity_from_title(title, brand=data.get("brand") or product.get("brand"), url=url)
            match = match_identities(expected, candidate_identity)
            if match["decision"] != "auto":
                skipped += 1
                continue
            stock_status = stock_status_from_values(
                stock_status=data.get("stock_status"),
                in_stock=data.get("in_stock"),
                sizes=data.get("sizes"),
                price=data.get("current_price"),
            )
            listing = {
                "id": new_id(),
                "product_id": product["id"],
                "url": url,
                "canonical_url": url,
                "store": engine.name,
                "store_slug": engine.slug,
                "title": title,
                "image": data.get("image"),
                "model_code": data.get("model_code"),
                "active": True,
                "last_price": data.get("current_price"),
                "last_old_price": data.get("old_price"),
                "last_cart_price": data.get("cart_price"),
                "last_cart_price_source": data.get("cart_price_source"),
                "last_cart_price_confidence": data.get("cart_price_confidence"),
                "last_cart_price_conditions": data.get("cart_price_conditions") or [],
                "last_price_source": data.get("price_source"),
                "last_confidence": data.get("confidence") or match["confidence"],
                "last_stock_count": data.get("stock_count") or 0,
                "last_in_stock": stock_status == "in_stock",
                "last_stock_status": stock_status,
                "last_sizes": data.get("sizes") or [],
                "last_raw": data.get("debug"),
                "last_error": None,
                "match_confidence": match["confidence"],
                "match_evidence": match["evidence"],
                "last_checked_at": now_iso(),
                "created_at": now_iso(),
            }
            await db.listings.insert_one(dict(listing))
            if listing["last_price"] is not None:
                await db.price_history.insert_one(
                    {
                        "id": new_id(),
                        "listing_id": listing["id"],
                        "product_id": product["id"],
                        "store": engine.name,
                        "price": listing["last_price"],
                        "old_price": listing["last_old_price"],
                        "cart_price": listing["last_cart_price"],
                        "cart_price_source": listing.get("last_cart_price_source"),
                        "cart_price_confidence": listing.get("last_cart_price_confidence"),
                        "cart_price_conditions": listing.get("last_cart_price_conditions") or [],
                        "price_source": listing["last_price_source"],
                        "confidence": listing["last_confidence"],
                        "stock_count": listing["last_stock_count"],
                        "stock_status": stock_status,
                        "checked_at": now_iso(),
                    }
                )
            if listing.get("image") and not product.get("image"):
                await db.products.update_one({"id": product["id"]}, {"$set": {"image": listing["image"]}})
                product["image"] = listing["image"]
            alert = await create_alert(
                db,
                alert_type="new_variant",
                title="Yeni renk veya varyant bulundu",
                product_id=product["id"],
                listing_id=listing["id"],
                product_name=product.get("name"),
                store=engine.name,
                url=url,
                price=listing.get("last_price"),
                sizes=available_size_labels(listing.get("last_sizes")),
                size_label=size_label_for_category(product.get("category")),
                confidence=match["confidence"],
                evidence=match["evidence"],
            )
            await notify_alert(db, alert)
            created += 1
        except Exception:
            skipped += 1
    if created:
        await evaluate_product_rules(db, product["id"])
    return {"created": created, "skipped": skipped}
