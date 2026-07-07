import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI, APIRouter, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel

from engines import ENGINES, get_engine_for_url, search_engines
from browser_search import rendered_search_batch
from insights import compute_price_insight, compute_buy_decision, short_comment
from family import make_family_key
from services import (
    batch_check,
    check_listing,
    default_settings,
    evaluate_product_rules,
    get_settings,
    new_id,
    now_iso,
    send_telegram,
)
from ai_service import coach_stream, analyze_search_query

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("shoehunter")

mongo_client = AsyncIOMotorClient(
    os.environ.get("MONGO_URL", "mongodb://localhost:27017"),
    serverSelectionTimeoutMS=2000,
)
db = mongo_client[os.environ.get("DB_NAME", "shoehunter_ai")]

scheduler = AsyncIOScheduler()
SCHED_JOB_ID = "auto_check"


async def scheduled_check():
    logger.info("Scheduler: otomatik kontrol basladi")
    try:
        await batch_check(db, trigger="scheduler")
    except Exception as exc:
        logger.error(f"Scheduler hatasi: {exc}")


async def apply_scheduler_settings():
    settings = await get_settings(db)
    sched = settings.get("scheduler", {})
    if scheduler.get_job(SCHED_JOB_ID):
        scheduler.remove_job(SCHED_JOB_ID)
    if sched.get("enabled"):
        minutes = max(1, int(sched.get("interval_minutes") or 30))
        scheduler.add_job(scheduled_check, IntervalTrigger(minutes=minutes), id=SCHED_JOB_ID)
        logger.info(f"Scheduler aktif: {minutes} dk")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        async for p in db.products.find({"family_key": {"$exists": False}}, {"_id": 0, "id": 1, "name": 1}):
            await db.products.update_one({"id": p["id"]}, {"$set": {"family_key": make_family_key(p.get("name"))}})
        await apply_scheduler_settings()
    except Exception as exc:
        logger.warning("MongoDB baglantisi hazir degil: %s", exc)
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)
    mongo_client.close()


app = FastAPI(title="ShoeHunter AI", lifespan=lifespan)
api = APIRouter(prefix="/api")


class ProductCreate(BaseModel):
    name: str
    brand: Optional[str] = None
    model: Optional[str] = None
    image: Optional[str] = None
    notes: Optional[str] = None
    url: Optional[str] = None


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    image: Optional[str] = None
    notes: Optional[str] = None
    active: Optional[bool] = None


class ListingCreate(BaseModel):
    url: str


class ManualPrice(BaseModel):
    price: float
    old_price: Optional[float] = None


class QuickTrack(BaseModel):
    url: str
    name: Optional[str] = None


class RuleCreate(BaseModel):
    product_id: str
    target_price: float
    size: Optional[str] = None
    spectrum_mode: bool = False
    cooldown_hours: float = 24


class RuleUpdate(BaseModel):
    target_price: Optional[float] = None
    size: Optional[str] = None
    spectrum_mode: Optional[bool] = None
    cooldown_hours: Optional[float] = None
    enabled: Optional[bool] = None


class TelegramSettings(BaseModel):
    enabled: bool
    bot_token: str
    chat_id: str


class SchedulerSettings(BaseModel):
    enabled: bool
    interval_minutes: int


class SearchRequest(BaseModel):
    query: str
    use_ai: bool = True


class TrackCandidate(BaseModel):
    title: str
    url: str
    brand: Optional[str] = None
    model: Optional[str] = None
    image: Optional[str] = None


class CoachMessage(BaseModel):
    session_id: str
    message: str


class ProfileUpdate(BaseModel):
    weight: Optional[str] = None
    target_weight: Optional[str] = None
    shoe_size: Optional[str] = None
    foot_notes: Optional[str] = None
    usage: Optional[str] = None
    priorities: Optional[str] = None
    notes: Optional[str] = None


# ---------- Dashboard ----------
@api.get("/dashboard")
async def dashboard():
    try:
        products = await db.products.count_documents({"active": True})
        listings = await db.listings.count_documents({"active": True})
        rules = await db.rules.count_documents({"enabled": True})
        unread_alerts = await db.alerts.count_documents({"is_read": False})
        total_alerts = await db.alerts.count_documents({})
        settings = await get_settings(db)
        last_run = await db.check_runs.find_one({}, {"_id": 0, "results": 0}, sort=[("started_at", -1)])
        recent_alerts = await db.alerts.find({}, {"_id": 0}).sort("created_at", -1).to_list(8)
        database_available = True
    except Exception as exc:
        logger.warning("Dashboard veritabani kullanilamiyor: %s", exc)
        products = listings = rules = unread_alerts = total_alerts = 0
        settings = default_settings()
        last_run = None
        recent_alerts = []
        database_available = False
    job = scheduler.get_job(SCHED_JOB_ID)
    return {
        "products": products,
        "listings": listings,
        "rules": rules,
        "unread_alerts": unread_alerts,
        "total_alerts": total_alerts,
        "scheduler": {
            "enabled": settings["scheduler"]["enabled"],
            "interval_minutes": settings["scheduler"]["interval_minutes"],
            "next_run": job.next_run_time.isoformat() if job and job.next_run_time else None,
        },
        "last_run": last_run,
        "recent_alerts": recent_alerts,
        "database_available": database_available,
    }


# ---------- Products ----------
@api.get("/products")
async def list_products():
    products = await db.products.find({}, {"_id": 0}).sort("created_at", -1).to_list(300)
    for p in products:
        listings = await db.listings.find({"product_id": p["id"], "active": True}, {"_id": 0}).to_list(50)
        prices = [l["last_price"] for l in listings if l.get("last_price") is not None]
        p["listing_count"] = len(listings)
        p["best_price"] = min(prices) if prices else None
        p["in_stock"] = any(l.get("last_in_stock") for l in listings)
        
        sizes_set = set()
        for l in listings:
            for sz in (l.get("last_sizes") or []):
                if sz.get("in_stock"):
                    size_name = sz.get("name") or sz.get("size")
                    if size_name:
                        sizes_set.add(str(size_name))
        
        # Sort sizes smartly (try numeric first, then string)
        def sort_key(s):
            try:
                return (0, float(s.replace(",", ".")))
            except ValueError:
                return (1, s)
        p["available_sizes"] = sorted(list(sizes_set), key=sort_key)

        if not p.get("image"):
            img = next((l.get("image") for l in listings if l.get("image")), None)
            p["image"] = img
        rule = await db.rules.find_one({"product_id": p["id"], "enabled": True}, {"_id": 0, "target_price": 1})
        p["target_price"] = rule["target_price"] if rule else None
    return products


@api.post("/products")
async def create_product(body: ProductCreate, background_tasks: BackgroundTasks):
    doc = {
        "id": new_id(),
        "name": body.name.strip(),
        "brand": body.brand,
        "model": body.model,
        "image": body.image,
        "notes": body.notes,
        "family_key": make_family_key(body.name),
        "active": True,
        "created_at": now_iso(),
    }
    await db.products.insert_one(dict(doc))
    doc.pop("_id", None)

    # Eger URL verilmisse otomatik listing olustur ve tara
    if body.url and body.url.strip():
        url = body.url.strip()
        engine = get_engine_for_url(url)
        listing = {
            "id": new_id(),
            "product_id": doc["id"],
            "url": url,
            "store": engine.name,
            "store_slug": engine.slug,
            "title": None,
            "image": None,
            "active": True,
            "last_price": None,
            "last_checked_at": None,
            "created_at": now_iso(),
        }
        await db.listings.insert_one(dict(listing))
        listing.pop("_id", None)
        # Arka planda fiyat tara
        background_tasks.add_task(_bg_check_listing, listing)
        doc["listing"] = listing

    return doc


async def _bg_check_listing(listing):
    """Arka planda listing'in fiyatini kontrol et."""
    try:
        await check_listing(db, listing)
        await evaluate_product_rules(db, listing["product_id"])
    except Exception as exc:
        logger.warning("Arka plan listing kontrolu basarisiz (%s): %s", listing["url"], str(exc)[:200])


@api.get("/products/{product_id}")
async def get_product(product_id: str):
    product = await db.products.find_one({"id": product_id}, {"_id": 0})
    if not product:
        raise HTTPException(404, "Ürün bulunamadı")
    listings = await db.listings.find({"product_id": product_id}, {"_id": 0}).to_list(100)
    rules = await db.rules.find({"product_id": product_id}, {"_id": 0}).to_list(50)
    alerts = await db.alerts.find({"product_id": product_id}, {"_id": 0}).sort("created_at", -1).to_list(20)
    history = (
        await db.price_history.find({"product_id": product_id}, {"_id": 0}).sort("checked_at", 1).to_list(1000)
    )
    family = []
    if product.get("family_key"):
        siblings = await db.products.find(
            {"family_key": product["family_key"], "id": {"$ne": product_id}, "active": True}, {"_id": 0}
        ).to_list(50)
        for s in siblings:
            s_listings = await db.listings.find({"product_id": s["id"], "active": True}, {"_id": 0}).to_list(50)
            prices = [l["last_price"] for l in s_listings if l.get("last_price") is not None]
            family.append(
                {
                    "id": s["id"],
                    "name": s["name"],
                    "image": s.get("image") or next((l.get("image") for l in s_listings if l.get("image")), None),
                    "best_price": min(prices) if prices else None,
                    "in_stock": any(l.get("last_in_stock") for l in s_listings),
                }
            )
    return {"product": product, "listings": listings, "rules": rules, "alerts": alerts, "history": history, "family": family}


@api.patch("/products/{product_id}")
async def update_product(product_id: str, body: ProductUpdate):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if updates:
        await db.products.update_one({"id": product_id}, {"$set": updates})
    product = await db.products.find_one({"id": product_id}, {"_id": 0})
    if not product:
        raise HTTPException(404, "Ürün bulunamadı")
    return product


@api.delete("/products/{product_id}")
async def delete_product(product_id: str):
    await db.products.delete_one({"id": product_id})
    await db.listings.delete_many({"product_id": product_id})
    await db.rules.delete_many({"product_id": product_id})
    await db.price_history.delete_many({"product_id": product_id})
    return {"deleted": True}


# ---------- Listings ----------
@api.post("/products/{product_id}/listings")
async def add_listing(product_id: str, body: ListingCreate):
    product = await db.products.find_one({"id": product_id}, {"_id": 0})
    if not product:
        raise HTTPException(404, "Ürün bulunamadı")
    engine = get_engine_for_url(body.url)
    doc = {
        "id": new_id(),
        "product_id": product_id,
        "url": body.url.strip(),
        "store": engine.name,
        "store_slug": engine.slug,
        "title": None,
        "image": None,
        "active": True,
        "last_price": None,
        "last_checked_at": None,
        "created_at": now_iso(),
    }
    await db.listings.insert_one(dict(doc))
    doc.pop("_id", None)
    result = await check_listing(db, doc)
    await evaluate_product_rules(db, product_id)
    fresh = await db.listings.find_one({"id": doc["id"]}, {"_id": 0})
    return {"listing": fresh, "check": result}


@api.post("/track/quick")
async def quick_track(body: QuickTrack, background_tasks: BackgroundTasks):
    existing = await db.listings.find_one({"url": body.url.strip()}, {"_id": 0})
    if existing:
        raise HTTPException(409, "Bu link zaten takip ediliyor")
    engine = get_engine_for_url(body.url)
    try:
        data = await engine.get_product_data(body.url)
    except Exception as exc:
        msg = str(exc)[:200]
        if "403" in msg or "429" in msg:
            raise HTTPException(
                422,
                "Bu mağaza bot koruması kullanıyor, sayfa okunamadı. Ürünü 'Manuel Ekle' ile oluşturup linki ekledikten sonra fiyatı elle girebilirsiniz.",
            )
        raise HTTPException(422, f"Ürün sayfası okunamadı: {msg}")
    name = body.name or data.get("title") or "İsimsiz Ürün"
    product = {
        "id": new_id(),
        "name": name,
        "brand": data.get("brand"),
        "model": None,
        "image": data.get("image"),
        "notes": None,
        "family_key": make_family_key(name),
        "active": True,
        "created_at": now_iso(),
    }
    await db.products.insert_one(dict(product))
    listing = {
        "id": new_id(),
        "product_id": product["id"],
        "url": body.url.strip(),
        "store": engine.name,
        "store_slug": engine.slug,
        "title": data.get("title"),
        "image": data.get("image"),
        "active": True,
        "last_price": data.get("current_price"),
        "last_old_price": data.get("old_price"),
        "last_cart_price": data.get("cart_price"),
        "last_price_source": data.get("price_source"),
        "last_confidence": data.get("confidence"),
        "last_stock_count": data.get("stock_count"),
        "last_in_stock": data.get("in_stock"),
        "last_sizes": data.get("sizes"),
        "last_raw": data.get("debug"),
        "last_error": None,
        "last_checked_at": now_iso(),
        "created_at": now_iso(),
    }
    await db.listings.insert_one(dict(listing))
    if data.get("current_price") is not None:
        await db.price_history.insert_one(
            {
                "id": new_id(),
                "listing_id": listing["id"],
                "product_id": product["id"],
                "store": engine.name,
                "price": data["current_price"],
                "old_price": data.get("old_price"),
                "cart_price": data.get("cart_price"),
                "price_source": data.get("price_source"),
                "confidence": data.get("confidence"),
                "stock_count": data.get("stock_count"),
                "checked_at": now_iso(),
            }
        )
    product.pop("_id", None)
    listing.pop("_id", None)

    # Varyasyon (diger renk) kesifleri arka planda baslat
    variant_urls = data.get("variant_urls") or []
    if variant_urls:
        background_tasks.add_task(_discover_variants, product, variant_urls)
        logger.info("Arka planda %d renk varyasyonu kesfedilecek: %s", len(variant_urls), product["name"])

    return {"product": product, "listing": listing}


async def _discover_variants(source_product: dict, variant_urls: list):
    """Arka planda diger renk varyasyonlarini sisteme ekler."""
    family_key = source_product.get("family_key")
    for vurl in variant_urls:
        try:
            # Zaten var mi kontrol et
            existing = await db.listings.find_one({"url": vurl}, {"_id": 0})
            if existing:
                continue

            engine = get_engine_for_url(vurl)
            data = await engine.get_product_data(vurl)
            name = data.get("title") or "İsimsiz Varyasyon"
            vfam = make_family_key(name)

            # Ayni aileden mi kontrol et (farkli urun ailesine ait linkleri ekleme)
            if family_key and vfam and vfam != family_key:
                logger.info("Varyasyon ailesi eslesmiyor, atlanıyor: %s (beklenen: %s, bulunan: %s)", vurl, family_key, vfam)
                continue

            product = {
                "id": new_id(),
                "name": name,
                "brand": data.get("brand") or source_product.get("brand"),
                "model": None,
                "image": data.get("image"),
                "notes": f"Otomatik kesfedildi ({source_product['name']})",
                "family_key": family_key or vfam,
                "active": True,
                "created_at": now_iso(),
            }
            await db.products.insert_one(dict(product))

            listing = {
                "id": new_id(),
                "product_id": product["id"],
                "url": vurl,
                "store": engine.name,
                "store_slug": engine.slug,
                "title": data.get("title"),
                "image": data.get("image"),
                "active": True,
                "last_price": data.get("current_price"),
                "last_old_price": data.get("old_price"),
                "last_cart_price": data.get("cart_price"),
                "last_price_source": data.get("price_source"),
                "last_confidence": data.get("confidence"),
                "last_stock_count": data.get("stock_count"),
                "last_in_stock": data.get("in_stock"),
                "last_sizes": data.get("sizes"),
                "last_raw": data.get("debug"),
                "last_error": None,
                "last_checked_at": now_iso(),
                "created_at": now_iso(),
            }
            await db.listings.insert_one(dict(listing))

            if data.get("current_price") is not None:
                await db.price_history.insert_one(
                    {
                        "id": new_id(),
                        "listing_id": listing["id"],
                        "product_id": product["id"],
                        "store": engine.name,
                        "price": data["current_price"],
                        "old_price": data.get("old_price"),
                        "cart_price": data.get("cart_price"),
                        "price_source": data.get("price_source"),
                        "confidence": data.get("confidence"),
                        "stock_count": data.get("stock_count"),
                        "checked_at": now_iso(),
                    }
                )
            logger.info("Varyasyon eklendi: %s — %s TL", name, data.get('current_price'))
        except Exception as exc:
            logger.warning("Varyasyon eklenemedi (%s): %s", vurl, str(exc)[:200])


@api.post("/listings/{listing_id}/check")
async def check_single_listing(listing_id: str):
    listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(404, "Link bulunamadı")
    result = await check_listing(db, listing)
    alerts = await evaluate_product_rules(db, listing["product_id"])
    return {"result": result, "alerts_created": len(alerts)}


@api.post("/listings/{listing_id}/manual-price")
async def manual_price(listing_id: str, body: ManualPrice):
    listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(404, "Link bulunamadı")
    if body.price <= 0:
        raise HTTPException(400, "Geçerli bir fiyat girin")
    await db.listings.update_one(
        {"id": listing_id},
        {
            "$set": {
                "last_price": body.price,
                "last_old_price": body.old_price,
                "last_price_source": "manual",
                "last_confidence": 0.99,
                "last_error": None,
                "last_checked_at": now_iso(),
            }
        },
    )
    await db.price_history.insert_one(
        {
            "id": new_id(),
            "listing_id": listing_id,
            "product_id": listing["product_id"],
            "store": listing.get("store"),
            "price": body.price,
            "old_price": body.old_price,
            "cart_price": None,
            "price_source": "manual",
            "confidence": 0.99,
            "stock_count": listing.get("last_stock_count"),
            "checked_at": now_iso(),
        }
    )
    alerts = await evaluate_product_rules(db, listing["product_id"])
    return {"ok": True, "alerts_created": len(alerts)}


@api.patch("/listings/{listing_id}/toggle")
async def toggle_listing(listing_id: str):
    listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(404, "Link bulunamadı")
    await db.listings.update_one({"id": listing_id}, {"$set": {"active": not listing.get("active", True)}})
    return {"active": not listing.get("active", True)}


@api.delete("/listings/{listing_id}")
async def delete_listing(listing_id: str):
    await db.listings.delete_one({"id": listing_id})
    await db.price_history.delete_many({"listing_id": listing_id})
    return {"deleted": True}


@api.get("/listings/{listing_id}/debug")
async def listing_debug(listing_id: str):
    listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(404, "Link bulunamadı")
    return listing


@api.get("/listings")
async def all_listings():
    listings = await db.listings.find({}, {"_id": 0}).sort("created_at", -1).to_list(300)
    return listings


async def _product_advice(product):
    product_id = product["id"]
    listings = await db.listings.find({"product_id": product_id, "active": True}, {"_id": 0}).to_list(100)
    priced = [l for l in listings if l.get("last_price") is not None]
    listing = min(priced, key=lambda l: l["last_price"]) if priced else (listings[0] if listings else None)
    if not listing:
        return {
            "decision": "BELİRSİZ",
            "score": 0,
            "breakdown": {"fiyat": 0, "stok": 0, "profil": 0, "guven": 0},
            "reasons": [],
            "risks": ["Henüz mağaza linki eklenmemiş"],
            "insight": None,
            "listing_store": None,
        }
    rules = await db.rules.find({"product_id": product_id, "enabled": True}, {"_id": 0}).to_list(50)
    rule = min(rules, key=lambda r: r.get("target_price") or 1e12) if rules else None
    history = await db.price_history.find(
        {"product_id": product_id}, {"_id": 0, "price": 1, "checked_at": 1}
    ).sort("checked_at", 1).to_list(2000)
    profile = await db.user_profile.find_one({"id": "main"}, {"_id": 0})
    insight = compute_price_insight(history, listing.get("last_price"), (rule or {}).get("target_price"))
    result = compute_buy_decision(listing, rule, insight, profile, product.get("name", ""))
    result["listing_store"] = listing.get("store")
    result["listing_url"] = listing.get("url")
    result["price"] = listing.get("last_price")
    return result


@api.get("/products/{product_id}/buy-advice")
async def buy_advice(product_id: str):
    product = await db.products.find_one({"id": product_id}, {"_id": 0})
    if not product:
        raise HTTPException(404, "Ürün bulunamadı")
    return await _product_advice(product)


@api.get("/dashboard/deals")
async def dashboard_deals():
    products = await db.products.find({"active": True}, {"_id": 0}).to_list(50)
    deals = []
    for p in products:
        advice = await _product_advice(p)
        if advice["decision"] == "BELİRSİZ" and advice["score"] == 0:
            continue
        listings = await db.listings.find({"product_id": p["id"], "active": True}, {"_id": 0, "image": 1}).to_list(10)
        deals.append(
            {
                "product_id": p["id"],
                "name": p["name"],
                "image": p.get("image") or next((l.get("image") for l in listings if l.get("image")), None),
                "decision": advice["decision"],
                "score": advice["score"],
                "price": advice.get("price"),
                "store": advice.get("listing_store"),
                "top_reason": advice["reasons"][0] if advice.get("reasons") else None,
            }
        )
    deals.sort(key=lambda d: -d["score"])
    return deals[:6]


# ---------- Rules ----------
@api.get("/rules")
async def list_rules():
    rules = await db.rules.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
    for r in rules:
        product = await db.products.find_one({"id": r["product_id"]}, {"_id": 0, "name": 1})
        r["product_name"] = product["name"] if product else "?"
    return rules


@api.post("/rules")
async def create_rule(body: RuleCreate):
    product = await db.products.find_one({"id": body.product_id}, {"_id": 0})
    if not product:
        raise HTTPException(404, "Ürün bulunamadı")
    doc = {
        "id": new_id(),
        "product_id": body.product_id,
        "target_price": body.target_price,
        "size": (body.size or "").strip() or None,
        "spectrum_mode": body.spectrum_mode,
        "cooldown_hours": body.cooldown_hours,
        "enabled": True,
        "created_at": now_iso(),
    }
    await db.rules.insert_one(dict(doc))
    doc.pop("_id", None)
    alerts = await evaluate_product_rules(db, body.product_id)
    return {"rule": doc, "alerts_created": len(alerts)}


@api.patch("/rules/{rule_id}")
async def update_rule(rule_id: str, body: RuleUpdate):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if updates:
        await db.rules.update_one({"id": rule_id}, {"$set": updates})
    rule = await db.rules.find_one({"id": rule_id}, {"_id": 0})
    if not rule:
        raise HTTPException(404, "Kural bulunamadı")
    return rule


@api.delete("/rules/{rule_id}")
async def delete_rule(rule_id: str):
    await db.rules.delete_one({"id": rule_id})
    return {"deleted": True}


# ---------- Alerts ----------
@api.get("/alerts")
async def list_alerts():
    return await db.alerts.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)


@api.patch("/alerts/{alert_id}/read")
async def mark_alert_read(alert_id: str):
    await db.alerts.update_one({"id": alert_id}, {"$set": {"is_read": True}})
    return {"ok": True}


@api.post("/alerts/read-all")
async def mark_all_read():
    await db.alerts.update_many({}, {"$set": {"is_read": True}})
    return {"ok": True}


@api.delete("/alerts/{alert_id}")
async def delete_alert(alert_id: str):
    await db.alerts.delete_one({"id": alert_id})
    return {"deleted": True}


# ---------- Batch check ----------
@api.post("/check/all")
async def run_batch_check():
    run, alerts = await batch_check(db, trigger="manual")
    return {"run": run, "alerts": alerts}


@api.get("/check/runs")
async def list_check_runs():
    return await db.check_runs.find({}, {"_id": 0}).sort("started_at", -1).to_list(20)


# ---------- Settings ----------
@api.get("/settings")
async def read_settings():
    try:
        settings = await get_settings(db)
        settings["database_available"] = True
        return settings
    except Exception as exc:
        logger.warning("Ayarlar veritabani kullanilamiyor: %s", exc)
        settings = default_settings()
        settings["database_available"] = False
        return settings


@api.put("/settings/telegram")
async def update_telegram(body: TelegramSettings):
    await get_settings(db)
    await db.settings.update_one(
        {"id": "main"},
        {"$set": {"telegram": body.model_dump(), "updated_at": now_iso()}},
    )
    return await get_settings(db)


@api.put("/settings/scheduler")
async def update_scheduler(body: SchedulerSettings):
    await get_settings(db)
    await db.settings.update_one(
        {"id": "main"},
        {"$set": {"scheduler": body.model_dump(), "updated_at": now_iso()}},
    )
    await apply_scheduler_settings()
    return await get_settings(db)


@api.post("/telegram/test")
async def telegram_test():
    result = await send_telegram(
        db,
        "\U0001f45f <b>ShoeHunter AI</b>\nTelegram bağlantısı çalışıyor. Bot ayakkabı kovalamaya hazır!",
    )
    return result


@api.get("/scheduler/status")
async def scheduler_status():
    try:
        settings = await get_settings(db)
        last_run = await db.check_runs.find_one(
            {"trigger": "scheduler"}, {"_id": 0, "results": 0}, sort=[("started_at", -1)]
        )
        database_available = True
    except Exception as exc:
        logger.warning("Scheduler durumu veritabani kullanilamiyor: %s", exc)
        settings = default_settings()
        last_run = None
        database_available = False
    job = scheduler.get_job(SCHED_JOB_ID)
    return {
        "enabled": settings["scheduler"]["enabled"],
        "interval_minutes": settings["scheduler"]["interval_minutes"],
        "next_run": job.next_run_time.isoformat() if job and job.next_run_time else None,
        "last_run": last_run,
        "database_available": database_available,
    }


# ---------- Stores ----------
@api.get("/stores")
async def list_stores():
    return [
        {"name": e.name, "slug": e.slug, "domains": e.domains, "searchable": bool(e.search_path)}
        for e in ENGINES
    ]



# ---------- Zero-link Search ----------
async def _enrich_results(store_results, limit=8):
    flat = [r for s in store_results for r in s["results"]]
    top = sorted(flat, key=lambda r: -r["score"])[:limit]
    sem = asyncio.Semaphore(4)

    async def enrich(r):
        async with sem:
            try:
                engine = get_engine_for_url(r["url"])
                data = await asyncio.wait_for(engine.get_product_data(r["url"]), timeout=14)
                r["price"] = data.get("current_price")
                r["old_price"] = data.get("old_price")
                if data.get("image"):
                    r["image"] = data["image"]
                sizes = data.get("sizes") or []
                r["sizes_in_stock"] = [s["name"] for s in sizes if s.get("in_stock")][:14]
                r["sizes_total"] = len(sizes)
                r["enriched"] = True
            except Exception:
                r["enriched"] = False

    if top:
        await asyncio.gather(*[enrich(r) for r in top])


@api.post("/search")
async def zero_link_search(body: SearchRequest):
    query = body.query.strip()
    if not query:
        raise HTTPException(400, "Sorgu boş olamaz")
    analysis = await analyze_search_query(query) if body.use_ai else {"brand": "", "model": "", "normalized_query": query}
    search_query = analysis["normalized_query"]

    static_engines = [e for e in search_engines() if not e.js_search]
    js_engines = [e for e in search_engines() if e.js_search]

    async def _search(engine):
        try:
            results = await asyncio.wait_for(engine.search(search_query), timeout=15)
            return {"store": engine.name, "status": "ok", "results": results, "engine": "static"}
        except asyncio.TimeoutError:
            return {"store": engine.name, "status": "timeout", "results": [], "error": "Zaman aşımı", "engine": "static"}
        except Exception as exc:
            msg = str(exc)[:150]
            status = "blocked" if "403" in msg or "429" in msg else "error"
            return {"store": engine.name, "status": status, "results": [], "error": msg, "engine": "static"}

    js_batch = [(e, e.search_path.format(q=quote_plus(search_query)), search_query) for e in js_engines]
    static_task = asyncio.gather(*[_search(e) for e in static_engines])
    js_task = asyncio.ensure_future(rendered_search_batch(js_batch)) if js_batch else None

    static_results = await static_task
    js_results = []
    if js_task:
        try:
            js_results = await asyncio.wait_for(js_task, timeout=75)
        except asyncio.TimeoutError:
            js_results = [
                {"store": e.name, "status": "timeout", "results": [], "error": "Tarayıcı motoru zaman aşımı", "engine": "playwright"}
                for e in js_engines
            ]

    store_results = list(static_results) + list(js_results)
    await _enrich_results(store_results)
    total = sum(len(s["results"]) for s in store_results)
    return {"query": query, "analysis": analysis, "stores": store_results, "total_results": total}


@api.post("/search/track")
async def track_candidate(body: TrackCandidate, background_tasks: BackgroundTasks):
    existing = await db.listings.find_one({"url": body.url}, {"_id": 0})
    if existing:
        raise HTTPException(409, "Bu link zaten takip ediliyor")
    try:
        return await quick_track(QuickTrack(url=body.url, name=body.title), background_tasks)
    except HTTPException:
        # Fiyat okunamasa bile urunu linksiz olarak ekle
        name = body.title or "Isimsiz Urun"
        engine = get_engine_for_url(body.url)
        product = {
            "id": new_id(),
            "name": name,
            "brand": None,
            "model": None,
            "image": None,
            "notes": "Fiyat okunamadi, link eklendi. Sonraki taramada okunacak.",
            "family_key": make_family_key(name),
            "active": True,
            "created_at": now_iso(),
        }
        await db.products.insert_one(dict(product))
        listing = {
            "id": new_id(),
            "product_id": product["id"],
            "url": body.url.strip(),
            "store": engine.name,
            "store_slug": engine.slug,
            "title": name,
            "image": None,
            "active": True,
            "last_price": None,
            "last_error": "Ilk taramada fiyat okunamadi",
            "last_checked_at": now_iso(),
            "created_at": now_iso(),
        }
        await db.listings.insert_one(dict(listing))
        product.pop("_id", None)
        listing.pop("_id", None)
        return {"product": product, "listing": listing}


# ---------- AI Coach ----------
@api.post("/ai/coach")
async def ai_coach(body: CoachMessage):
    return StreamingResponse(
        coach_stream(db, body.session_id, body.message),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@api.get("/ai/coach/history/{session_id}")
async def coach_history(session_id: str):
    msgs = await db.ai_messages.find({"session_id": session_id}, {"_id": 0}).sort("created_at", 1).to_list(100)
    return msgs


# ---------- Profile ----------
@api.get("/profile")
async def get_profile():
    profile = await db.user_profile.find_one({"id": "main"}, {"_id": 0})
    return profile or {"id": "main"}


@api.put("/profile")
async def update_profile(body: ProfileUpdate):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    updates["updated_at"] = now_iso()
    await db.user_profile.update_one({"id": "main"}, {"$set": updates}, upsert=True)
    return await db.user_profile.find_one({"id": "main"}, {"_id": 0})


@api.get("/")
async def root():
    return {"app": "ShoeHunter AI", "status": "ok", "version": "1.1.0"}


app.include_router(api)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
