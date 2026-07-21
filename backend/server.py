import asyncio
import hmac
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from datetime import datetime, timezone
from typing import Literal, Optional
from urllib.parse import quote_plus

import httpx
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI, APIRouter, File, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, StreamingResponse
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field

from engines import ENGINES, _score_result, get_engine_for_url
from browser_search import rendered_search_batch
from discovery_sources import layered_url_discovery
from insights import compute_price_insight, compute_buy_decision, short_comment
from family import make_family_key
from services import (
    batch_check,
    check_listing,
    default_settings,
    evaluate_product_rules,
    get_settings,
    public_settings,
    new_id,
    now_iso,
    send_telegram,
    stock_status_from_listing,
    stock_status_from_values,
)
from ai_service import coach_stream, analyze_search_query
from backup_service import price_history_csv, product_export
from browser_runtime import shutdown_browser_pool
from commerce_intelligence import canonical_product_projection, enrich_listing_commerce, parse_gs1_digital_link
from database_setup import ensure_database, purge_expired_ai_history
from discovery_service import ensure_watch_product, make_watch_document, review_candidate, run_watch_discovery
from job_queue import claim_job, complete_job, enqueue_job, fail_job
from label_scan import LabelScanError, MAX_IMAGE_BYTES, scan_product_label
from physical_price_evidence_service import (
    create_physical_price_evidence,
    ensure_physical_evidence_indexes,
    list_physical_price_evidence,
    moderate_physical_price_evidence,
)
from product_identity import canonicalize_product_url, identity_from_title, normalize_size
from size_profiles import (
    infer_product_category,
    merge_watch_sizes,
    prepare_household_members,
    resolve_profile_preferences,
    size_label_for_category,
)
from secret_store import get_secret, set_secret
from security import (
    SESSION_COOKIE,
    SecurityMiddleware,
    clear_session_cookies,
    create_session,
    ensure_admin,
    hash_password,
    login_limiter,
    set_session_cookies,
    token_hash,
    utcnow,
    validate_password_strength,
    validate_remote_url,
    verify_password,
)
from store_health import health_snapshot, record_store_result
from version import app_version
from variant_service import discover_product_variants

logging.basicConfig(level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger("shoehunter")

mongo_client = AsyncIOMotorClient(
    os.environ.get("MONGO_URL", "mongodb://localhost:27017"),
    serverSelectionTimeoutMS=2000,
    tz_aware=True,
)
db = mongo_client[os.environ.get("DB_NAME", "shoehunter_ai")]

scheduler = AsyncIOScheduler()
SCHED_JOB_ID = "auto_check"
DISCOVERY_JOB_ID = "auto_discovery"
EMBEDDED_SCHEDULER = os.environ.get("EMBEDDED_SCHEDULER", "true").lower() in {"1", "true", "yes"}


async def scheduled_check():
    logger.info("Scheduler: otomatik kontrol kuyruga aliniyor")
    settings = await get_settings(db)
    minutes = max(1, int((settings.get("scheduler") or {}).get("interval_minutes") or 30))
    bucket = int(datetime.now(timezone.utc).timestamp() // (minutes * 60))
    await enqueue_job(db, "batch_check", idempotency_key=f"embedded-batch:{bucket}", queue="browser")


async def scheduled_discovery():
    logger.info("Scheduler: urun radari kesfi kuyruga aliniyor")
    bucket = int(datetime.now(timezone.utc).timestamp() // 3600)
    await enqueue_job(db, "discover_due", idempotency_key=f"embedded-discovery:{bucket}", queue="browser")


async def embedded_worker_loop():
    from worker import handle_job

    worker_id = f"embedded-{os.getpid()}"
    while True:
        job = await claim_job(db, worker_id)
        if not job:
            await asyncio.sleep(1)
            continue
        try:
            result = await handle_job(db, job)
            await complete_job(db, job["id"], result)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await fail_job(db, job, exc)


async def apply_scheduler_settings():
    settings = await get_settings(db)
    sched = settings.get("scheduler", {})
    if scheduler.get_job(SCHED_JOB_ID):
        scheduler.remove_job(SCHED_JOB_ID)
    if scheduler.get_job(DISCOVERY_JOB_ID):
        scheduler.remove_job(DISCOVERY_JOB_ID)
    if sched.get("enabled"):
        minutes = max(1, int(sched.get("interval_minutes") or 30))
        scheduler.add_job(scheduled_check, IntervalTrigger(minutes=minutes), id=SCHED_JOB_ID)
        discovery_hours = max(6, int(sched.get("discovery_interval_hours") or 6))
        scheduler.add_job(
            scheduled_discovery,
            IntervalTrigger(hours=discovery_hours),
            id=DISCOVERY_JOB_ID,
        )
        logger.info(f"Scheduler aktif: {minutes} dk")


@asynccontextmanager
async def lifespan(app: FastAPI):
    embedded_worker = None
    try:
        await ensure_database(db)
        await ensure_physical_evidence_indexes(db)
        from telemetry_service import ensure_telemetry_indexes
        await ensure_telemetry_indexes(db)
        await ensure_admin(db)
        settings = await get_settings(db)
        await purge_expired_ai_history(db, (settings.get("privacy") or {}).get("ai_history_retention_days", 30))
        if EMBEDDED_SCHEDULER:
            await apply_scheduler_settings()
    except Exception as exc:
        logger.warning("MongoDB baglantisi hazir degil: %s", exc)
    if EMBEDDED_SCHEDULER:
        scheduler.start()
        embedded_worker = asyncio.create_task(embedded_worker_loop())
    yield
    if embedded_worker:
        embedded_worker.cancel()
        try:
            await embedded_worker
        except asyncio.CancelledError:
            pass
    if EMBEDDED_SCHEDULER and scheduler.running:
        scheduler.shutdown(wait=False)
    await shutdown_browser_pool()
    mongo_client.close()


app = FastAPI(title="ShoeHunter AI", lifespan=lifespan)
api = APIRouter(prefix="/api")


class ProductCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    brand: Optional[str] = None
    model: Optional[str] = None
    image: Optional[str] = None
    notes: Optional[str] = None
    category: Optional[str] = None
    attributes: dict[str, object] = Field(default_factory=dict)
    url: Optional[str] = None


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    image: Optional[str] = None
    notes: Optional[str] = None
    category: Optional[str] = None
    attributes: Optional[dict[str, object]] = None
    active: Optional[bool] = None


class ListingCreate(BaseModel):
    url: str = Field(min_length=10, max_length=2048)


class ManualPrice(BaseModel):
    price: float
    old_price: Optional[float] = None


class QuickTrack(BaseModel):
    url: str = Field(min_length=10, max_length=2048)
    name: Optional[str] = None
    image: Optional[str] = None
    tracking_origin: Literal["link", "ai_search"] = "link"


class RuleCreate(BaseModel):
    product_id: str
    target_price: float
    size: Optional[str] = None
    desired_sizes: list[str] = Field(default_factory=list)
    spectrum_mode: bool = False
    near_target_enabled: bool = False
    near_target_percent: float = 0
    cooldown_hours: float = 24


class RuleUpdate(BaseModel):
    target_price: Optional[float] = None
    size: Optional[str] = None
    desired_sizes: Optional[list[str]] = None
    spectrum_mode: Optional[bool] = None
    near_target_enabled: Optional[bool] = None
    near_target_percent: Optional[float] = None
    cooldown_hours: Optional[float] = None
    enabled: Optional[bool] = None


class TelegramSettings(BaseModel):
    enabled: bool
    bot_token: Optional[str] = None
    chat_id: str


class SchedulerSettings(BaseModel):
    enabled: bool
    interval_minutes: int
    discovery_interval_hours: int = 6


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=160)
    use_ai: bool = True


class TrackCandidate(BaseModel):
    title: str
    url: str = Field(min_length=10, max_length=2048)
    brand: Optional[str] = None
    model: Optional[str] = None
    image: Optional[str] = None


class CoachMessage(BaseModel):
    session_id: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=4000)


class SizePreferenceInput(BaseModel):
    id: Optional[str] = Field(default=None, max_length=80)
    category: str = Field(default="shoes", min_length=1, max_length=60)
    label: Optional[str] = Field(default=None, max_length=80)
    size_system: str = Field(default="EU", min_length=1, max_length=30)
    sizes: list[str] = Field(default_factory=list, max_length=12)
    notes: Optional[str] = Field(default=None, max_length=300)


class HouseholdMemberInput(BaseModel):
    id: Optional[str] = Field(default=None, max_length=80)
    name: str = Field(min_length=1, max_length=80)
    relationship: Optional[str] = Field(default=None, max_length=60)
    preferences: list[SizePreferenceInput] = Field(default_factory=list, max_length=20)


class ProfileUpdate(BaseModel):
    weight: Optional[str] = None
    target_weight: Optional[str] = None
    shoe_size: Optional[str] = None
    foot_notes: Optional[str] = None
    usage: Optional[str] = None
    priorities: Optional[str] = None
    notes: Optional[str] = None
    share_profile_with_ai: Optional[bool] = None
    household_members: Optional[list[HouseholdMemberInput]] = Field(default=None, max_length=20)


class AuthSetup(BaseModel):
    username: str = Field(default="admin", min_length=3, max_length=50)
    password: str = Field(min_length=12, max_length=200)
    setup_token: Optional[str] = None


class AuthLogin(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=200)


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=12, max_length=200)


class WatchCreate(BaseModel):
    raw_query: str = Field(min_length=2, max_length=160)
    brand: Optional[str] = Field(default=None, max_length=80)
    model: Optional[str] = Field(default=None, max_length=120)
    generation: Optional[str] = Field(default=None, max_length=30)
    gender: Optional[str] = Field(default=None, max_length=30)
    category: Optional[str] = Field(default=None, max_length=60)
    desired_sizes: list[str] = Field(default_factory=list, max_length=12)
    profile_preference_ids: list[str] = Field(default_factory=list, max_length=40)
    color_policy: Literal["any", "dark", "specific", "exclude"] = "any"
    allowed_colors: list[str] = Field(default_factory=list, max_length=20)
    excluded_colors: list[str] = Field(default_factory=list, max_length=20)
    target_price: Optional[float] = Field(default=None, gt=0)
    minimum_drop_percent: float = Field(default=0, ge=0, le=100)
    minimum_drop_amount: float = Field(default=0, ge=0)
    store_scope: list[str] = Field(default_factory=list, max_length=50)
    required_tokens: list[str] = Field(default_factory=list, max_length=20)
    excluded_tokens: list[str] = Field(default_factory=list, max_length=20)
    discovery_frequency_hours: int = Field(default=6, ge=6, le=168)
    refresh_frequency_minutes: int = Field(default=360, ge=30, le=1440)
    input_origin: Literal["manual", "label_scan"] = "manual"
    source_identifiers: dict[str, str] = Field(default_factory=dict)


class WatchUpdate(BaseModel):
    desired_sizes: Optional[list[str]] = None
    profile_preference_ids: Optional[list[str]] = None
    color_policy: Optional[Literal["any", "dark", "specific", "exclude"]] = None
    allowed_colors: Optional[list[str]] = None
    excluded_colors: Optional[list[str]] = None
    target_price: Optional[float] = Field(default=None, gt=0)
    minimum_drop_percent: Optional[float] = Field(default=None, ge=0, le=100)
    minimum_drop_amount: Optional[float] = Field(default=None, ge=0)
    store_scope: Optional[list[str]] = None
    required_tokens: Optional[list[str]] = None
    excluded_tokens: Optional[list[str]] = None
    discovery_frequency_hours: Optional[int] = Field(default=None, ge=6, le=168)
    refresh_frequency_minutes: Optional[int] = Field(default=None, ge=30, le=1440)
    active: Optional[bool] = None


class CandidateReview(BaseModel):
    decision: str


class BrowserAssistSubmission(BaseModel):
    url: str = Field(min_length=10, max_length=2048)
    title: str = Field(min_length=2, max_length=200)
    price: Optional[float] = None
    old_price: Optional[float] = None
    image: Optional[str] = None
    sizes: list[dict] = Field(default_factory=list)
    product_id: Optional[str] = None
    watch_id: Optional[str] = None


async def _validated_store_url(raw_url):
    url = canonicalize_product_url(raw_url)
    try:
        engine = get_engine_for_url(url)
        await validate_remote_url(url, engine.domains)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return engine, url


# ---------- Authentication and health ----------
@api.get("/health")
async def health():
    database = False
    try:
        await db.command("ping")
        database = True
    except Exception:
        pass
    return {"status": "ok" if database else "degraded", "database": database, "version": app_version()}


@api.get("/auth/status")
async def auth_status(request: Request):
    admin = await db.admin_users.find_one({"id": "main"}, {"_id": 0, "password_hash": 0})
    authenticated = False
    raw_token = request.cookies.get(SESSION_COOKIE)
    if raw_token:
        session = await db.auth_sessions.find_one(
            {"token_hash": token_hash(raw_token), "expires_at": {"$gt": utcnow()}}, {"_id": 0, "id": 1}
        )
        authenticated = bool(session)
    return {
        "setup_required": not bool(admin),
        "authenticated": authenticated,
        "username": admin.get("username") if admin and authenticated else None,
        "cookie_secure": os.environ.get("COOKIE_SECURE", "false").lower() in {"1", "true", "yes"},
    }


@api.post("/auth/setup")
async def auth_setup(body: AuthSetup, request: Request, response: Response):
    if await db.admin_users.find_one({"id": "main"}, {"_id": 0, "id": 1}):
        raise HTTPException(409, "Yonetici hesabi zaten olusturulmus")
    expected_setup_token = os.environ.get("SETUP_TOKEN", "").strip()
    if expected_setup_token and not hmac.compare_digest(expected_setup_token, body.setup_token or ""):
        raise HTTPException(403, "Kurulum anahtari gecersiz")
    try:
        validate_password_strength(body.password)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    await db.admin_users.insert_one(
        {
            "id": "main",
            "username": body.username.strip(),
            "password_hash": hash_password(body.password),
            "created_at": utcnow(),
        }
    )
    session_token, csrf_token = await create_session(db, request)
    set_session_cookies(response, session_token, csrf_token)
    return {"authenticated": True, "username": body.username.strip()}


@api.post("/auth/login")
async def auth_login(body: AuthLogin, request: Request, response: Response):
    client_ip = request.client.host if request.client else "unknown"
    admin = await db.admin_users.find_one({"id": "main"}, {"_id": 0})
    if (
        not admin
        or not hmac.compare_digest(admin.get("username", ""), body.username)
        or not verify_password(body.password, admin.get("password_hash"))
    ):
        if not login_limiter.allow((client_ip, body.username.lower()), 5, 15 * 60):
            raise HTTPException(429, "Cok fazla basarisiz giris. 15 dakika sonra tekrar deneyin.")
        raise HTTPException(401, "Kullanici adi veya parola hatali")
    session_token, csrf_token = await create_session(db, request)
    set_session_cookies(response, session_token, csrf_token)
    return {"authenticated": True, "username": admin["username"]}


@api.post("/auth/logout")
async def auth_logout(request: Request, response: Response):
    raw_token = request.cookies.get(SESSION_COOKIE)
    if raw_token:
        await db.auth_sessions.delete_one({"token_hash": token_hash(raw_token)})
    clear_session_cookies(response)
    return {"authenticated": False}


@api.put("/auth/password")
async def change_password(body: PasswordChange):
    admin = await db.admin_users.find_one({"id": "main"}, {"_id": 0})
    if not admin or not verify_password(body.current_password, admin.get("password_hash")):
        raise HTTPException(401, "Mevcut parola hatali")
    try:
        validate_password_strength(body.new_password)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    await db.admin_users.update_one(
        {"id": "main"}, {"$set": {"password_hash": hash_password(body.new_password), "updated_at": utcnow()}}
    )
    await db.auth_sessions.delete_many({})
    return {"changed": True, "login_required": True}


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
def _product_stock_status(listings):
    statuses = [stock_status_from_listing(l) for l in listings]
    if any(s == "in_stock" for s in statuses):
        return "in_stock"
    if statuses and all(s in {"out_of_stock", "not_found"} for s in statuses):
        return "out_of_stock"
    if any(s == "blocked" for s in statuses):
        return "blocked"
    if any(s == "error" for s in statuses):
        return "error"
    return "unknown"


def _in_stock_priced_listings(listings):
    return [
        listing
        for listing in listings
        if listing.get("last_price") is not None and stock_status_from_listing(listing) == "in_stock"
    ]


@api.get("/products")
async def list_products():
    products = await db.products.aggregate(
        [
            {"$sort": {"created_at": -1}},
            {"$limit": 300},
            {
                "$lookup": {
                    "from": "listings",
                    "let": {"product_id": "$id"},
                    "pipeline": [
                        {
                            "$match": {
                                "$expr": {
                                    "$and": [{"$eq": ["$product_id", "$$product_id"]}, {"$eq": ["$active", True]}]
                                }
                            }
                        },
                        {
                            "$project": {
                                "_id": 0,
                                "last_price": 1,
                                "last_stock_status": 1,
                                "last_in_stock": 1,
                                "last_sizes": 1,
                                "last_error": 1,
                                "image": 1,
                            }
                        },
                    ],
                    "as": "_listings",
                }
            },
            {
                "$lookup": {
                    "from": "rules",
                    "let": {"product_id": "$id"},
                    "pipeline": [
                        {
                            "$match": {
                                "$expr": {
                                    "$and": [{"$eq": ["$product_id", "$$product_id"]}, {"$eq": ["$enabled", True]}]
                                }
                            }
                        },
                        {"$project": {"_id": 0, "target_price": 1, "hard_target_price": 1}},
                        {"$limit": 1},
                    ],
                    "as": "_rules",
                }
            },
            {
                "$lookup": {
                    "from": "watch_queries",
                    "let": {"product_id": "$id"},
                    "pipeline": [
                        {
                            "$match": {
                                "$expr": {
                                    "$and": [
                                        {"$eq": ["$product_id", "$$product_id"]},
                                        {"$eq": ["$active", True]},
                                    ]
                                }
                            }
                        },
                        {"$project": {"_id": 0, "id": 1}},
                    ],
                    "as": "_watches",
                }
            },
            {"$project": {"_id": 0}},
        ]
    ).to_list(300)
    for p in products:
        listings = p.pop("_listings", [])
        rules = p.pop("_rules", [])
        watches = p.pop("_watches", [])
        prices = [listing["last_price"] for listing in _in_stock_priced_listings(listings)]
        stock_status = _product_stock_status(listings)
        p["listing_count"] = len(listings)
        p["best_price"] = min(prices) if prices else None
        p["stock_status"] = stock_status
        p["in_stock"] = stock_status == "in_stock"
        p["radar_watch_count"] = len(watches)
        origins = list(p.get("tracking_origins") or [])
        if watches and "radar" not in origins:
            origins.append("radar")
        p["tracking_origins"] = origins or ["legacy"]

        sizes_set = set()
        for l in listings:
            for sz in l.get("last_sizes") or []:
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
        rule = rules[0] if rules else None
        p["target_price"] = (rule or {}).get("hard_target_price", (rule or {}).get("target_price"))
    return sorted(products, key=lambda item: (item.get("best_price") is None, item.get("best_price") or 0))


@api.post("/products")
async def create_product(body: ProductCreate):
    validated_url = None
    engine = None
    if body.url and body.url.strip():
        engine, validated_url = await _validated_store_url(body.url)
        if await db.listings.find_one({"url": validated_url}, {"_id": 0, "id": 1}):
            raise HTTPException(409, "Bu link zaten takip ediliyor")
    identity = identity_from_title(body.name, brand=body.brand, url=validated_url)
    doc = None
    if identity.canonical_key:
        doc = await db.products.find_one({"canonical_key": identity.canonical_key}, {"_id": 0})
    if doc and not validated_url:
        raise HTTPException(409, "Bu urun zaten kayitli")
    if not doc:
        doc = {
            "id": new_id(),
            "name": body.name.strip(),
            "brand": body.brand,
            "model": body.model,
            "image": body.image,
            "notes": body.notes,
            "category": body.category,
            "attributes": body.attributes,
            "tracking_origins": ["manual"],
            "tracking_source": "manual",
            "family_key": identity.family_key,
            "canonical_key": identity.canonical_key or None,
            "identity": identity.to_dict(),
            "identity_version": 2,
            "active": True,
            "created_at": now_iso(),
        }
        await db.products.insert_one(dict(doc))
        doc.pop("_id", None)
    else:
        await db.products.update_one(
            {"id": doc["id"]},
            {"$addToSet": {"tracking_origins": "manual"}},
        )
        doc["tracking_origins"] = sorted(set((doc.get("tracking_origins") or []) + ["manual"]))

    # Eger URL verilmisse otomatik listing olustur ve tara
    if validated_url:
        url = validated_url
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
            "last_stock_status": "unknown",
            "last_checked_at": None,
            "created_at": now_iso(),
        }
        await db.listings.insert_one(dict(listing))
        listing.pop("_id", None)
        await enqueue_job(
            db,
            "refresh_listing",
            {"listing_id": listing["id"]},
            idempotency_key=f"listing:{listing['id']}:initial",
            queue="browser",
        )
        doc["listing"] = listing

    return doc


async def _bg_check_listing(listing):
    """Arka planda listing'in fiyatini kontrol et."""
    return await enqueue_job(
        db,
        "refresh_listing",
        {"listing_id": listing["id"]},
        idempotency_key=f"listing:{listing['id']}:legacy",
        queue="browser",
    )
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
    listings = [enrich_listing_commerce(listing) for listing in listings]
    rules = await db.rules.find({"product_id": product_id}, {"_id": 0}).to_list(50)
    alerts = await db.alerts.find({"product_id": product_id}, {"_id": 0}).sort("created_at", -1).to_list(20)
    history = await db.price_history.find({"product_id": product_id}, {"_id": 0}).sort("checked_at", 1).to_list(1000)
    watches = await db.watch_queries.find({"product_id": product_id, "active": True}, {"_id": 0}).to_list(100)
    origins = list(product.get("tracking_origins") or [])
    if watches and "radar" not in origins:
        origins.append("radar")
    product["tracking_origins"] = origins or ["legacy"]
    product["radar_watch_count"] = len(watches)
    family = []
    if product.get("family_key"):
        siblings = await db.products.find(
            {"family_key": product["family_key"], "id": {"$ne": product_id}, "active": True}, {"_id": 0}
        ).to_list(50)
        for s in siblings:
            s_listings = await db.listings.find({"product_id": s["id"], "active": True}, {"_id": 0}).to_list(50)
            prices = [listing["last_price"] for listing in _in_stock_priced_listings(s_listings)]
            stock_status = _product_stock_status(s_listings)
            family.append(
                {
                    "id": s["id"],
                    "name": s["name"],
                    "image": s.get("image") or next((l.get("image") for l in s_listings if l.get("image")), None),
                    "best_price": min(prices) if prices else None,
                    "stock_status": stock_status,
                    "in_stock": stock_status == "in_stock",
                }
            )
    return {
        "product": product,
        "listings": listings,
        "commerce_model": canonical_product_projection(product, listings),
        "rules": rules,
        "alerts": alerts,
        "history": history,
        "family": family,
        "watches": watches,
    }


@api.patch("/products/{product_id}")
async def update_product(product_id: str, body: ProductUpdate):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    current = await db.products.find_one({"id": product_id}, {"_id": 0})
    if not current:
        raise HTTPException(404, "Ürün bulunamadı")
    if "name" in updates or "brand" in updates:
        identity = identity_from_title(
            updates.get("name", current.get("name")), brand=updates.get("brand", current.get("brand"))
        )
        updates.update(
            {
                "identity": identity.to_dict(),
                "identity_version": 2,
                "canonical_key": identity.canonical_key or None,
                "family_key": identity.family_key,
            }
        )
    if updates:
        await db.products.update_one({"id": product_id}, {"$set": updates})
    product = await db.products.find_one({"id": product_id}, {"_id": 0})
    if not product:
        raise HTTPException(404, "Ürün bulunamadı")
    return product


@api.delete("/products/{product_id}")
async def delete_product(product_id: str):
    watches = await db.watch_queries.find({"product_id": product_id}, {"_id": 0, "id": 1}).to_list(200)
    watch_ids = [watch["id"] for watch in watches]
    await db.products.delete_one({"id": product_id})
    await db.listings.delete_many({"product_id": product_id})
    await db.rules.delete_many({"product_id": product_id})
    await db.price_history.delete_many({"product_id": product_id})
    await db.alerts.delete_many({"product_id": product_id})
    if watch_ids:
        await db.candidate_listings.delete_many({"watch_id": {"$in": watch_ids}})
        await db.discovery_runs.delete_many({"watch_id": {"$in": watch_ids}})
        await db.watch_queries.delete_many({"id": {"$in": watch_ids}})
    return {"deleted": True}


# ---------- Listings ----------
@api.post("/products/{product_id}/listings")
async def add_listing(product_id: str, body: ListingCreate):
    product = await db.products.find_one({"id": product_id}, {"_id": 0})
    if not product:
        raise HTTPException(404, "Ürün bulunamadı")
    engine, url = await _validated_store_url(body.url)
    if await db.listings.find_one({"url": url}, {"_id": 0, "id": 1}):
        raise HTTPException(409, "Bu link zaten takip ediliyor")
    doc = {
        "id": new_id(),
        "product_id": product_id,
        "url": url,
        "canonical_url": url,
        "store": engine.name,
        "store_slug": engine.slug,
        "title": None,
        "image": None,
        "active": True,
        "last_price": None,
        "last_stock_status": "unknown",
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
async def quick_track(body: QuickTrack):
    engine, url = await _validated_store_url(body.url)
    existing = await db.listings.find_one({"url": url}, {"_id": 0})
    if existing:
        raise HTTPException(409, "Bu link zaten takip ediliyor")
    try:
        data = await engine.get_product_data(url)
    except Exception as exc:
        msg = str(exc)[:200]
        if "403" in msg or "429" in msg:
            raise HTTPException(
                422,
                "Bu mağaza bot koruması kullanıyor, sayfa okunamadı. Ürünü 'Manuel Ekle' ile oluşturup linki ekledikten sonra fiyatı elle girebilirsiniz.",
            )
        raise HTTPException(422, f"Ürün sayfası okunamadı: {msg}")
    name = body.name or data.get("title") or "İsimsiz Ürün"
    image = data.get("image") or body.image
    stock_status = stock_status_from_values(
        stock_status=data.get("stock_status"),
        in_stock=data.get("in_stock"),
        sizes=data.get("sizes"),
        price=data.get("current_price"),
    )
    identity = identity_from_title(name, brand=data.get("brand"), url=url)
    product = None
    if identity.canonical_key:
        product = await db.products.find_one({"canonical_key": identity.canonical_key}, {"_id": 0})
    if not product:
        category = data.get("category") or infer_product_category(name)
        product = {
            "id": new_id(),
            "name": name,
            "brand": data.get("brand"),
            "model": None,
            "image": image,
            "notes": None,
            "category": category,
            "attributes": {},
            "tracking_origins": [body.tracking_origin],
            "tracking_source": body.tracking_origin,
            "family_key": identity.family_key,
            "canonical_key": identity.canonical_key or None,
            "identity": identity.to_dict(),
            "identity_version": 2,
            "active": True,
            "created_at": now_iso(),
        }
        await db.products.insert_one(dict(product))
    else:
        product_updates = {"$addToSet": {"tracking_origins": body.tracking_origin}}
        if image and not product.get("image"):
            product_updates["$set"] = {"image": image}
            product["image"] = image
        await db.products.update_one({"id": product["id"]}, product_updates)
        product["tracking_origins"] = sorted(
            set((product.get("tracking_origins") or []) + [body.tracking_origin])
        )
    listing = {
        "id": new_id(),
        "product_id": product["id"],
        "url": url,
        "canonical_url": url,
        "store": engine.name,
        "store_slug": engine.slug,
        "title": data.get("title"),
        "image": image,
        "active": True,
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
                "cart_price_source": data.get("cart_price_source"),
                "cart_price_confidence": data.get("cart_price_confidence"),
                "cart_price_conditions": data.get("cart_price_conditions") or [],
                "price_source": data.get("price_source"),
                "confidence": data.get("confidence"),
                "stock_count": data.get("stock_count"),
                "stock_status": stock_status,
                "checked_at": now_iso(),
            }
        )
    product.pop("_id", None)
    listing.pop("_id", None)

    variant_urls = data.get("variant_urls") or []
    if variant_urls:
        await enqueue_job(
            db,
            "discover_variants",
            {"product_id": product["id"], "urls": variant_urls[:100]},
            idempotency_key=f"variants:{listing['id']}",
            queue="browser",
        )

    return {"product": product, "listing": listing}


async def _discover_variants(source_product: dict, variant_urls: list):
    """Arka planda diger renk varyasyonlarini sisteme ekler."""
    return await discover_product_variants(db, source_product["id"], variant_urls)
    family_key = source_product.get("family_key")
    for vurl in variant_urls:
        try:
            engine, vurl = await _validated_store_url(vurl)
            # Zaten var mi kontrol et
            existing = await db.listings.find_one({"url": vurl}, {"_id": 0})
            if existing:
                continue

            data = await engine.get_product_data(vurl)
            name = data.get("title") or "İsimsiz Varyasyon"
            vfam = make_family_key(name)

            # Ayni aileden mi kontrol et (farkli urun ailesine ait linkleri ekleme)
            if family_key and vfam and vfam != family_key:
                logger.info(
                    "Varyasyon ailesi eslesmiyor, atlanıyor: %s (beklenen: %s, bulunan: %s)", vurl, family_key, vfam
                )
                continue

            identity = identity_from_title(name, brand=data.get("brand") or source_product.get("brand"), url=vurl)
            product = {
                "id": new_id(),
                "name": name,
                "brand": data.get("brand") or source_product.get("brand"),
                "model": None,
                "image": data.get("image"),
                "notes": f"Otomatik kesfedildi ({source_product['name']})",
                "family_key": family_key or vfam,
                "canonical_key": identity.canonical_key or None,
                "identity": identity.to_dict(),
                "identity_version": 2,
                "active": True,
                "created_at": now_iso(),
            }
            await db.products.insert_one(dict(product))

            stock_status = stock_status_from_values(
                stock_status=data.get("stock_status"),
                in_stock=data.get("in_stock"),
                sizes=data.get("sizes"),
                price=data.get("current_price"),
            )
            listing = {
                "id": new_id(),
                "product_id": product["id"],
                "url": vurl,
                "canonical_url": vurl,
                "store": engine.name,
                "store_slug": engine.slug,
                "title": data.get("title"),
                "image": data.get("image"),
                "active": True,
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
                        "cart_price_source": data.get("cart_price_source"),
                        "cart_price_confidence": data.get("cart_price_confidence"),
                        "cart_price_conditions": data.get("cart_price_conditions") or [],
                        "price_source": data.get("price_source"),
                        "confidence": data.get("confidence"),
                        "stock_count": data.get("stock_count"),
                        "stock_status": stock_status,
                        "checked_at": now_iso(),
                    }
                )
            logger.info("Varyasyon eklendi: %s — %s TL", name, data.get("current_price"))
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
            "stock_status": stock_status_from_listing(listing),
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
    await db.alerts.delete_many({"listing_id": listing_id})
    await db.candidate_listings.update_many(
        {"listing_id": listing_id}, {"$set": {"status": "listing_deleted"}, "$unset": {"listing_id": ""}}
    )
    return {"deleted": True}


@api.get("/listings/{listing_id}/debug")
async def listing_debug(listing_id: str):
    listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(404, "Link bulunamadı")
    listing.pop("request_headers", None)
    listing.pop("cookies", None)
    raw = listing.get("last_raw")
    if isinstance(raw, dict):
        listing["last_raw"] = {
            key: value for key, value in raw.items() if key not in {"headers", "cookies", "authorization", "set-cookie"}
        }
    return listing


@api.get("/listings")
async def all_listings():
    listings = await db.listings.find({}, {"_id": 0}).sort("created_at", -1).to_list(300)
    return [enrich_listing_commerce(listing) for listing in listings]


async def _product_advice(product):
    product_id = product["id"]
    listings = await db.listings.find({"product_id": product_id, "active": True}, {"_id": 0}).to_list(100)
    listings = [enrich_listing_commerce(item) for item in listings]
    priced = _in_stock_priced_listings(listings)
    listing = min(priced, key=lambda item: item["last_price"]) if priced else None
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
    history = (
        await db.price_history.find({"product_id": product_id}, {"_id": 0, "price": 1, "checked_at": 1})
        .sort("checked_at", 1)
        .to_list(2000)
    )
    profile = await db.user_profile.find_one({"id": "main"}, {"_id": 0})
    insight = compute_price_insight(history, listing.get("last_price"), (rule or {}).get("target_price"))
    result = compute_buy_decision(listing, rule, insight, profile, product.get("name", ""))
    result["listing_store"] = listing.get("store")
    result["listing_url"] = listing.get("url")
    result["total_cost"] = listing.get("total_cost")
    result["seller_trust"] = listing.get("seller_trust")
    total_cost = listing.get("total_cost") or {}
    result["price"] = total_cost.get("amount") if total_cost.get("complete") else listing.get("last_price")
    if not total_cost.get("complete"):
        result.setdefault("risks", []).append("Kargo veya kampanya koşulu eksik; toplam maliyet kesin değil")
    if (listing.get("seller_trust") or {}).get("band") == "low":
        result.setdefault("risks", []).append("Satıcı kanıtı düşük; satın almadan önce satıcıyı doğrulayın")
    result["risks"] = result.get("risks", [])[:7]
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
    if body.target_price <= 0:
        raise HTTPException(400, "Hedef fiyat sifirdan buyuk olmalidir")
    desired_sizes = sorted({normalize_size(item) for item in body.desired_sizes if item})
    if body.size and normalize_size(body.size) not in desired_sizes:
        desired_sizes.append(normalize_size(body.size))
    doc = {
        "id": new_id(),
        "product_id": body.product_id,
        "target_price": body.target_price,
        "hard_target_price": body.target_price,
        "size": desired_sizes[0] if desired_sizes else None,
        "desired_sizes": desired_sizes,
        "spectrum_mode": body.spectrum_mode,
        "near_target_enabled": body.near_target_enabled,
        "near_target_percent": max(0, min(50, body.near_target_percent)),
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
    if "target_price" in updates:
        if updates["target_price"] <= 0:
            raise HTTPException(400, "Hedef fiyat sifirdan buyuk olmalidir")
        updates["hard_target_price"] = updates["target_price"]
    if "desired_sizes" in updates:
        updates["desired_sizes"] = sorted({normalize_size(item) for item in updates["desired_sizes"] if item})
        updates["size"] = updates["desired_sizes"][0] if updates["desired_sizes"] else None
    if "near_target_percent" in updates:
        updates["near_target_percent"] = max(0, min(50, updates["near_target_percent"]))
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
    bucket = int(datetime.now(timezone.utc).timestamp() // 300)
    job = await enqueue_job(
        db,
        "batch_check",
        {"trigger": "manual", "force": True},
        idempotency_key=f"manual-batch:{bucket}",
        queue="browser",
    )
    return {"queued": True, "job_id": job["id"]}


@api.get("/check/runs")
async def list_check_runs():
    return await db.check_runs.find({}, {"_id": 0}).sort("started_at", -1).to_list(20)


# ---------- Settings ----------
@api.get("/settings")
async def read_settings():
    try:
        settings = await public_settings(db)
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
    if body.bot_token and body.bot_token.strip():
        await set_secret(db, "telegram_bot_token", body.bot_token.strip())
    await db.settings.update_one(
        {"id": "main"},
        {
            "$set": {
                "telegram.enabled": body.enabled,
                "telegram.chat_id": body.chat_id.strip(),
                "updated_at": now_iso(),
            },
            "$unset": {"telegram.bot_token": ""},
        },
    )
    return await public_settings(db)


@api.put("/settings/scheduler")
async def update_scheduler(body: SchedulerSettings):
    await get_settings(db)
    await db.settings.update_one(
        {"id": "main"},
        {"$set": {"scheduler": body.model_dump(), "updated_at": now_iso()}},
    )
    if EMBEDDED_SCHEDULER:
        await apply_scheduler_settings()
    return await public_settings(db)


@api.post("/telegram/test")
async def telegram_test():
    result = await send_telegram(
        db,
        "\U0001f45f <b>ShoeHunter AI</b>\nTelegram bağlantısı çalışıyor. Bot ayakkabı kovalamaya hazır!",
    )
    return result


@api.post("/telegram/webhook/configure")
async def configure_telegram_webhook():
    webhook_url = os.environ.get("TELEGRAM_WEBHOOK_URL", "").strip()
    webhook_secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "").strip()
    if not webhook_url.startswith("https://"):
        raise HTTPException(400, "TELEGRAM_WEBHOOK_URL HTTPS adresi olarak ayarlanmali")
    if not 16 <= len(webhook_secret) <= 256:
        raise HTTPException(400, "TELEGRAM_WEBHOOK_SECRET 16-256 karakter olmali")
    token = (await get_secret(db, "telegram_bot_token")).strip()
    if not token:
        raise HTTPException(400, "Telegram bot tokeni ayarlanmamis")
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"https://api.telegram.org/bot{token}/setWebhook",
                json={
                    "url": webhook_url,
                    "secret_token": webhook_secret,
                    "allowed_updates": ["callback_query"],
                },
            )
            data = response.json()
    except Exception as exc:
        raise HTTPException(502, "Telegram webhook kurulumu basarisiz") from exc
    if not data.get("ok"):
        logger.warning("Telegram webhook kurulumu reddedildi: %s", str(data).replace(token, "***")[:500])
        raise HTTPException(502, "Telegram webhook kurulumu Telegram tarafindan reddedildi")
    return {"configured": True, "url": webhook_url}


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
        "mode": "embedded" if EMBEDDED_SCHEDULER else "durable_worker",
    }


# ---------- Stores ----------
@api.get("/stores")
async def list_stores():
    health_docs = {item["store_slug"]: item for item in await health_snapshot(db)}
    return [
        {
            "name": engine.name,
            "slug": engine.slug,
            "domains": engine.domains,
            "searchable": True,
            "native_search": bool(engine.search_path),
            "capabilities": engine.capabilities(),
            "health": health_docs.get(engine.slug),
        }
        for engine in ENGINES
    ]


@api.get("/stores/health")
async def stores_health():
    return await health_snapshot(db)


@api.get("/metrics", response_class=PlainTextResponse)
async def metrics():
    lines = [
        "# HELP shoehunter_products_total Kayitli urun sayisi",
        "# TYPE shoehunter_products_total gauge",
        f"shoehunter_products_total {await db.products.count_documents({})}",
        "# HELP shoehunter_listings_total Kayitli magaza ilani sayisi",
        "# TYPE shoehunter_listings_total gauge",
        f"shoehunter_listings_total {await db.listings.count_documents({})}",
        "# HELP shoehunter_jobs_pending Bekleyen kalici is sayisi",
        "# TYPE shoehunter_jobs_pending gauge",
        f'shoehunter_jobs_pending {await db.jobs.count_documents({"status": "pending"})}',
        "# HELP shoehunter_dead_letter_jobs_total Kalici olarak basarisiz is sayisi",
        "# TYPE shoehunter_dead_letter_jobs_total gauge",
        f"shoehunter_dead_letter_jobs_total {await db.dead_letter_jobs.count_documents({})}",
    ]
    for health in await health_snapshot(db):
        slug = str(health.get("store_slug") or "unknown").replace('"', "")
        rate = health.get("success_rate_24h")
        if rate is not None:
            lines.append(f'shoehunter_store_success_rate_24h{{store="{slug}"}} {rate}')
        lines.append(
            f'shoehunter_store_circuit_open{{store="{slug}"}} ' f'{1 if health.get("circuit_open") else 0}'
        )
    return "\n".join(lines) + "\n"


# ---------- Zero-link Search ----------
async def _enrich_results(store_results, limit=8):
    flat = [r for s in store_results for r in s["results"]]
    targets = []
    seen_urls = set()

    def add_target(result):
        url = result.get("url")
        if not url or url in seen_urls:
            return
        seen_urls.add(url)
        targets.append(result)

    for result in sorted(flat, key=lambda r: -r["score"])[:limit]:
        add_target(result)

    for store in store_results:
        for result in sorted(store.get("results") or [], key=lambda r: -r["score"])[:2]:
            add_target(result)

    for store in store_results:
        if "yali" not in str(store.get("store", "")).lower():
            continue
        for result in sorted(store.get("results") or [], key=lambda r: -r["score"])[:5]:
            add_target(result)

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
                r["stock_status"] = data.get("stock_status") or stock_status_from_values(
                    in_stock=data.get("in_stock"),
                    sizes=sizes,
                    price=data.get("current_price"),
                )
                r["sizes_in_stock"] = [s["name"] for s in sizes if s.get("in_stock")][:14]
                r["sizes_total"] = len(sizes)
                r["enriched"] = True
            except Exception:
                r["enriched"] = False

    if targets:
        await asyncio.gather(*[enrich(r) for r in targets])


@api.post("/search")
async def zero_link_search(body: SearchRequest):
    query = body.query.strip()
    if not query:
        raise HTTPException(400, "Sorgu boş olamaz")
    analysis = (
        await analyze_search_query(query) if body.use_ai else {"brand": "", "model": "", "normalized_query": query}
    )
    search_query = analysis["normalized_query"]

    static_engines = [engine for engine in ENGINES if not engine.js_search]
    js_engines = [engine for engine in ENGINES if engine.js_search and engine.search_path]

    def _candidate_results(engine, candidates):
        results = []
        seen = set()
        for item in candidates:
            title = item.get("title") or ""
            score = _score_result(title, search_query)
            if score < 45:
                continue
            url = canonicalize_product_url(item.get("url"))
            if not url or url in seen:
                continue
            results.append(
                {
                    "title": title,
                    "url": url,
                    "score": score,
                    "image": item.get("image"),
                    "price": item.get("price"),
                    "store": engine.name,
                    "discovery_source": item.get("source"),
                }
            )
            seen.add(url)
        return results

    async def _search(engine):
        try:
            results = await asyncio.wait_for(
                engine.search(search_query), timeout=getattr(engine, "search_timeout_seconds", 40)
            )
            used_fallback = False
            if not results:
                candidates = await asyncio.wait_for(layered_url_discovery(engine, search_query, limit=6), timeout=22)
                results = _candidate_results(engine, candidates)
                used_fallback = bool(results)
            await record_store_result(
                db,
                engine.slug,
                "ok",
                price_ok=any(item.get("price") is not None for item in results),
                stock_ok=False,
                parser_version=getattr(engine, "parser_version", "1"),
                source="ai_search",
            )
            return {
                "store": engine.name,
                "status": "ok",
                "results": results,
                "engine": "layered" if used_fallback else "static",
            }
        except asyncio.TimeoutError:
            await record_store_result(
                db,
                engine.slug,
                "timeout",
                parser_version=getattr(engine, "parser_version", "1"),
                error="Zaman asimi",
                source="ai_search",
            )
            return {
                "store": engine.name,
                "status": "timeout",
                "results": [],
                "error": "Zaman aşımı",
                "engine": "static",
            }
        except Exception as exc:
            msg = str(exc)[:150]
            if "403" in msg or "429" in msg:
                status = "blocked"
            elif "404" in msg:
                status = "not_found"
            else:
                status = "error"
            fallback = []
            try:
                fallback = await asyncio.wait_for(layered_url_discovery(engine, search_query, limit=6), timeout=22)
            except Exception:
                pass
            results = _candidate_results(engine, fallback)
            final_status = "ok" if results else status
            await record_store_result(
                db,
                engine.slug,
                final_status,
                parser_version=getattr(engine, "parser_version", "1"),
                error=None if results else msg,
                source="ai_search",
            )
            return {
                "store": engine.name,
                "status": final_status,
                "results": results,
                "error": None if results else msg,
                "engine": "layered" if results else "static",
            }

    js_batch = [(e, e.search_path.format(q=quote_plus(search_query)), search_query) for e in js_engines]
    static_task = asyncio.gather(*[_search(e) for e in static_engines])
    js_task = asyncio.ensure_future(rendered_search_batch(js_batch)) if js_batch else None

    static_results = await static_task
    js_results = []
    if js_task:
        # rendered_search_batch owns a deadline based on the browser pool's
        # actual concurrency and preserves stores that finish before it.  A
        # second global wait_for used to cancel the whole batch at 150s and
        # replace even completed stores with empty timeout records.
        js_results = await js_task

    js_fallback_sem = asyncio.Semaphore(4)

    async def _apply_js_fallback(store_result, engine):
        if not store_result.get("results"):
            async with js_fallback_sem:
                try:
                    candidates = await asyncio.wait_for(
                        layered_url_discovery(engine, search_query, limit=6), timeout=22
                    )
                except Exception:
                    candidates = []
            if candidates:
                filtered_candidates = _candidate_results(engine, candidates)
                if filtered_candidates:
                    store_result["results"] = filtered_candidates
                    store_result["status"] = "ok"
                    store_result["engine"] = "layered"
        return store_result

    if js_results:
        js_results = list(
            await asyncio.gather(
                *[
                    _apply_js_fallback(store_result, engine)
                    for store_result, engine in zip(js_results, js_engines, strict=True)
                ]
            )
        )

    for store_result, engine in zip(js_results, js_engines, strict=True):
        await record_store_result(
            db,
            engine.slug,
            store_result.get("status") or "error",
            price_ok=any(item.get("price") is not None for item in store_result.get("results") or []),
            stock_ok=False,
            parser_version=getattr(engine, "parser_version", "1"),
            error=store_result.get("error"),
            source="ai_search_browser",
        )

    store_results = list(static_results) + list(js_results)
    await _enrich_results(store_results)
    total = sum(len(s["results"]) for s in store_results)
    return {"query": query, "analysis": analysis, "stores": store_results, "total_results": total}


@api.post("/search/track")
async def track_candidate(body: TrackCandidate):
    engine, url = await _validated_store_url(body.url)
    existing = await db.listings.find_one({"url": url}, {"_id": 0})
    if existing:
        raise HTTPException(409, "Bu link zaten takip ediliyor")
    try:
        return await quick_track(
            QuickTrack(url=url, name=body.title, image=body.image, tracking_origin="ai_search")
        )
    except HTTPException:
        # Fiyat okunamasa bile urunu linksiz olarak ekle
        name = body.title or "Isimsiz Urun"
        identity = identity_from_title(name, brand=body.brand, url=url)
        product = {
            "id": new_id(),
            "name": name,
            "brand": None,
            "model": None,
            "image": body.image,
            "notes": "Fiyat okunamadi, link eklendi. Sonraki taramada okunacak.",
            "category": infer_product_category(name),
            "tracking_origins": ["ai_search"],
            "tracking_source": "ai_search",
            "family_key": identity.family_key,
            "canonical_key": identity.canonical_key or None,
            "identity": identity.to_dict(),
            "identity_version": 2,
            "active": True,
            "created_at": now_iso(),
        }
        await db.products.insert_one(dict(product))
        listing = {
            "id": new_id(),
            "product_id": product["id"],
            "url": url,
            "canonical_url": url,
            "store": engine.name,
            "store_slug": engine.slug,
            "title": name,
            "image": body.image,
            "active": True,
            "last_price": None,
            "last_stock_count": 0,
            "last_in_stock": False,
            "last_stock_status": "error",
            "last_sizes": [],
            "last_error": "Ilk taramada fiyat okunamadi",
            "last_checked_at": now_iso(),
            "created_at": now_iso(),
        }
        await db.listings.insert_one(dict(listing))
        product.pop("_id", None)
        listing.pop("_id", None)
        return {"product": product, "listing": listing}


# ---------- Product Radar / autonomous discovery ----------
@api.post("/radar/scan-label")
async def scan_radar_label(image: UploadFile = File(...)):
    content_type = (image.content_type or "").lower()
    data = await image.read(MAX_IMAGE_BYTES + 1)
    await image.close()
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "Fotograf en fazla 12 MB olabilir")
    try:
        return await asyncio.to_thread(scan_product_label, data, content_type)
    except LabelScanError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        logger.exception("Etiket okuma basarisiz")
        raise HTTPException(500, "Etiket okuma tamamlanamadi") from exc


@api.get("/watches")
async def list_watches():
    return await db.watch_queries.aggregate(
        [
            {"$sort": {"created_at": -1}},
            {
                "$lookup": {
                    "from": "candidate_listings",
                    "let": {"watch_id": "$id"},
                    "pipeline": [
                        {"$match": {"$expr": {"$eq": ["$watch_id", "$$watch_id"]}}},
                        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
                    ],
                    "as": "candidate_counts",
                }
            },
            {
                "$lookup": {
                    "from": "listings",
                    "let": {"product_id": "$product_id"},
                    "pipeline": [
                        {"$match": {"$expr": {"$eq": ["$product_id", "$$product_id"]}}},
                        {"$count": "count"},
                    ],
                    "as": "listing_count_rows",
                }
            },
            {"$project": {"_id": 0}},
        ]
    ).to_list(300)


@api.post("/watches")
async def create_watch(body: WatchCreate):
    analysis = await analyze_search_query(body.raw_query)
    payload = body.model_dump()
    payload["source_identifiers"] = {
        str(key)[:40]: str(value)[:300]
        for key, value in list((payload.get("source_identifiers") or {}).items())[:8]
        if str(key).strip() and str(value).strip()
    }
    profile = await db.user_profile.find_one({"id": "main"}, {"_id": 0})
    snapshots = resolve_profile_preferences(profile, payload.get("profile_preference_ids"))
    if payload.get("category"):
        snapshots = [item for item in snapshots if item.get("category") == payload["category"]]
    manual_sizes = payload.get("desired_sizes") or []
    payload["manual_desired_sizes"] = manual_sizes
    payload["size_preferences"] = snapshots
    payload["desired_sizes"] = merge_watch_sizes(manual_sizes, snapshots)
    payload["size_label"] = size_label_for_category(payload.get("category"))
    watch = make_watch_document(payload, analysis=analysis)
    duplicate = await db.watch_queries.find_one(
        {"user_id": "main", "canonical_query": watch["canonical_query"]}, {"_id": 0, "id": 1}
    )
    if duplicate:
        raise HTTPException(409, "Bu urun radari zaten kayitli")
    await db.watch_queries.insert_one(dict(watch))
    watch.pop("_id", None)
    await ensure_watch_product(db, watch)
    await enqueue_job(
        db,
        "discover_watch",
        {"watch_id": watch["id"]},
        idempotency_key=f"watch:{watch['id']}:initial",
        queue="browser",
    )
    return watch


@api.get("/watches/{watch_id}")
async def get_watch(watch_id: str):
    watch = await db.watch_queries.find_one({"id": watch_id}, {"_id": 0})
    if not watch:
        raise HTTPException(404, "Urun radari bulunamadi")
    candidates = (
        await db.candidate_listings.find(
            {"watch_id": watch_id, "status": {"$in": ["review", "attached", "user_rejected"]}}, {"_id": 0}
        )
        .sort("confidence", -1)
        .to_list(300)
    )
    runs = await db.discovery_runs.find({"watch_id": watch_id}, {"_id": 0}).sort("started_at", -1).to_list(20)
    return {"watch": watch, "candidates": candidates, "runs": runs}


@api.patch("/watches/{watch_id}")
async def update_watch(watch_id: str, body: WatchUpdate):
    watch = await db.watch_queries.find_one({"id": watch_id}, {"_id": 0})
    if not watch:
        raise HTTPException(404, "Urun radari bulunamadi")
    updates = body.model_dump(exclude_unset=True)
    if "desired_sizes" in updates or "profile_preference_ids" in updates:
        manual_sizes = updates.get(
            "desired_sizes",
            watch.get("manual_desired_sizes")
            or ([] if watch.get("size_preferences") else watch.get("desired_sizes") or []),
        )
        preference_ids = updates.get("profile_preference_ids", watch.get("profile_preference_ids") or [])
        profile = await db.user_profile.find_one({"id": "main"}, {"_id": 0})
        snapshots = resolve_profile_preferences(profile, preference_ids)
        if watch.get("category"):
            snapshots = [item for item in snapshots if item.get("category") == watch["category"]]
        updates["manual_desired_sizes"] = sorted(
            {normalize_size(item) for item in manual_sizes if item}
        )
        updates["profile_preference_ids"] = preference_ids
        updates["size_preferences"] = snapshots
        updates["desired_sizes"] = merge_watch_sizes(manual_sizes, snapshots)
    if "discovery_frequency_hours" in updates:
        updates["discovery_frequency_hours"] = max(6, min(168, int(updates["discovery_frequency_hours"])))
    if "refresh_frequency_minutes" in updates:
        updates["refresh_frequency_minutes"] = max(30, min(1440, int(updates["refresh_frequency_minutes"])))
    if updates.get("target_price") is not None and updates["target_price"] <= 0:
        raise HTTPException(400, "Hedef fiyat sifirdan buyuk olmalidir")
    updates["updated_at"] = utcnow()
    updates["next_discovery_at"] = utcnow()
    await db.watch_queries.update_one({"id": watch_id}, {"$set": updates})
    merged = {**watch, **updates}
    if watch.get("product_id"):
        target = merged.get("target_price")
        await db.rules.update_one(
            {"watch_id": watch_id},
            {
                "$set": {
                    "target_price": target,
                    "hard_target_price": target,
                    "desired_sizes": merged.get("desired_sizes") or [],
                    "size": (merged.get("desired_sizes") or [None])[0],
                    "size_preferences": merged.get("size_preferences") or [],
                    "category": merged.get("category"),
                    "size_label": merged.get("size_label") or size_label_for_category(merged.get("category")),
                    "enabled": target is not None and merged.get("active", True),
                }
            },
        )
    return await db.watch_queries.find_one({"id": watch_id}, {"_id": 0})


@api.delete("/watches/{watch_id}")
async def delete_watch(watch_id: str):
    await db.watch_queries.delete_one({"id": watch_id})
    await db.candidate_listings.delete_many({"watch_id": watch_id})
    await db.discovery_runs.delete_many({"watch_id": watch_id})
    await db.rules.delete_many({"watch_id": watch_id})
    return {"deleted": True}


@api.post("/watches/{watch_id}/run")
async def run_watch_now(watch_id: str):
    watch = await db.watch_queries.find_one({"id": watch_id}, {"_id": 0})
    if not watch:
        raise HTTPException(404, "Urun radari bulunamadi")
    bucket = int(datetime.now(timezone.utc).timestamp() // 300)
    job = await enqueue_job(
        db,
        "discover_watch",
        {"watch_id": watch_id},
        idempotency_key=f"watch:{watch_id}:manual:{bucket}",
        queue="browser",
    )
    return {"queued": True, "job_id": job["id"]}


@api.get("/candidates/review")
async def review_queue():
    return await db.candidate_listings.find({"status": "review"}, {"_id": 0}).sort("confidence", -1).to_list(300)


@api.post("/candidates/{candidate_id}/review")
async def apply_candidate_review(candidate_id: str, body: CandidateReview):
    if body.decision not in {"approve", "variant", "same_family", "reject"}:
        raise HTTPException(400, "Gecersiz inceleme karari")
    result = await review_candidate(db, candidate_id, body.decision)
    if result is None:
        raise HTTPException(404, "Aday bulunamadi")
    return result


@api.post("/browser-assist/submit")
async def browser_assist_submit(body: BrowserAssistSubmission):
    engine, url = await _validated_store_url(body.url)
    stock_status = stock_status_from_values(sizes=body.sizes, price=body.price)
    existing = await db.listings.find_one({"url": url}, {"_id": 0})
    if existing:
        changed = (
            existing.get("last_price") != body.price
            or existing.get("last_old_price") != body.old_price
            or existing.get("last_stock_status") != stock_status
            or (existing.get("last_sizes") or []) != body.sizes
        )
        await db.listings.update_one(
            {"id": existing["id"]},
            {
                "$set": {
                    "title": body.title,
                    "image": body.image or existing.get("image"),
                    "last_price": body.price,
                    "last_old_price": body.old_price,
                    "last_sizes": body.sizes,
                    "last_stock_status": stock_status,
                    "last_in_stock": stock_status == "in_stock",
                    "last_confidence": 0.99,
                    "last_price_source": "user_browser_assist",
                    "last_error": None,
                    "last_checked_at": now_iso(),
                }
            },
        )
        if changed:
            await db.price_history.insert_one(
                {
                    "id": new_id(),
                    "listing_id": existing["id"],
                    "product_id": existing["product_id"],
                    "store": engine.name,
                    "price": body.price,
                    "old_price": body.old_price,
                    "cart_price": None,
                    "price_source": "user_browser_assist",
                    "confidence": 0.99,
                    "stock_count": sum(1 for size in body.sizes if size.get("in_stock")),
                    "stock_status": stock_status,
                    "checked_at": now_iso(),
                }
            )
        if body.image:
            await db.products.update_one(
                {"id": existing["product_id"], "image": {"$in": [None, ""]}},
                {"$set": {"image": body.image}},
            )
        alerts = await evaluate_product_rules(db, existing["product_id"])
        return {"listing_id": existing["id"], "updated": True, "changed": changed, "alerts": len(alerts)}
    product = None
    if body.product_id:
        product = await db.products.find_one({"id": body.product_id}, {"_id": 0})
    elif body.watch_id:
        watch = await db.watch_queries.find_one({"id": body.watch_id}, {"_id": 0})
        if watch:
            product = await ensure_watch_product(db, watch)
    if not product:
        raise HTTPException(400, "Yeni link icin product_id veya watch_id gerekli")
    listing = {
        "id": new_id(),
        "product_id": product["id"],
        "url": url,
        "canonical_url": url,
        "store": engine.name,
        "store_slug": engine.slug,
        "title": body.title,
        "image": body.image,
        "active": True,
        "last_price": body.price,
        "last_old_price": body.old_price,
        "last_sizes": body.sizes,
        "last_stock_status": stock_status,
        "last_in_stock": stock_status == "in_stock",
        "last_confidence": 0.99,
        "last_price_source": "user_browser_assist",
        "last_checked_at": now_iso(),
        "created_at": utcnow(),
    }
    await db.listings.insert_one(dict(listing))
    listing.pop("_id", None)
    if body.price is not None:
        await db.price_history.insert_one(
            {
                "id": new_id(),
                "listing_id": listing["id"],
                "product_id": product["id"],
                "store": engine.name,
                "price": body.price,
                "old_price": body.old_price,
                "cart_price": None,
                "price_source": "user_browser_assist",
                "confidence": 0.99,
                "stock_count": sum(1 for size in body.sizes if size.get("in_stock")),
                "stock_status": stock_status,
                "checked_at": now_iso(),
            }
        )
    if body.image and not product.get("image"):
        await db.products.update_one({"id": product["id"]}, {"$set": {"image": body.image}})
    alerts = await evaluate_product_rules(db, product["id"])
    return {"listing": listing, "created": True, "alerts": len(alerts)}


# ---------- Privacy, export and operations ----------
@api.get("/privacy")
async def privacy_status():
    settings = await get_settings(db)
    providers = [
        {"name": "Gemini", "configured": bool(os.environ.get("GEMINI_API_KEY"))},
        {"name": "Groq", "configured": bool(os.environ.get("GROQ_API_KEY"))},
        {"name": "OpenAI", "configured": bool(os.environ.get("OPENAI_API_KEY"))},
    ]
    return {
        "providers": providers,
        "profile_fields": [
            "weight",
            "target_weight",
            "shoe_size",
            "foot_notes",
            "usage",
            "priorities",
            "notes",
            "household_members",
        ],
        "profile_shared_only_with_consent": True,
        "history_retention_days": (settings.get("privacy") or {}).get("ai_history_retention_days", 30),
    }


@api.delete("/ai/coach/history")
async def delete_all_coach_history():
    result = await db.ai_messages.delete_many({})
    return {"deleted": result.deleted_count}


@api.delete("/ai/coach/history/{session_id}")
async def delete_coach_history(session_id: str):
    result = await db.ai_messages.delete_many({"session_id": session_id})
    return {"deleted": result.deleted_count}


@api.get("/export/products.json")
async def export_products():
    return Response(
        content=await product_export(db),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=shoehunter-products.json"},
    )


@api.get("/export/price-history.csv")
async def export_price_history():
    return PlainTextResponse(
        content=await price_history_csv(db),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=shoehunter-price-history.csv"},
    )


@api.post("/backups")
async def request_backup():
    bucket = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H")
    job = await enqueue_job(db, "backup", idempotency_key=f"manual-backup:{bucket}")
    return {"queued": True, "job_id": job["id"]}


@api.get("/jobs")
async def list_jobs():
    jobs = await db.jobs.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    dead = await db.dead_letter_jobs.find({}, {"_id": 0}).sort("failed_at", -1).to_list(50)
    return {"jobs": jobs, "dead_letter": dead}


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
    if "household_members" in updates:
        updates["household_members"] = prepare_household_members(updates["household_members"], new_id)
    updates["updated_at"] = now_iso()
    await db.user_profile.update_one({"id": "main"}, {"$set": updates}, upsert=True)
    profile = await db.user_profile.find_one({"id": "main"}, {"_id": 0})
    if "household_members" in updates:
        watches = await db.watch_queries.find(
            {"profile_preference_ids.0": {"$exists": True}}, {"_id": 0}
        ).to_list(300)
        for watch in watches:
            snapshots = resolve_profile_preferences(profile, watch.get("profile_preference_ids"))
            if watch.get("category"):
                snapshots = [item for item in snapshots if item.get("category") == watch["category"]]
            manual_sizes = watch.get("manual_desired_sizes") or []
            desired_sizes = merge_watch_sizes(manual_sizes, snapshots)
            watch_updates = {
                "size_preferences": snapshots,
                "desired_sizes": desired_sizes,
                "updated_at": utcnow(),
            }
            await db.watch_queries.update_one({"id": watch["id"]}, {"$set": watch_updates})
            await db.rules.update_one(
                {"watch_id": watch["id"]},
                {
                    "$set": {
                        "size_preferences": snapshots,
                        "desired_sizes": desired_sizes,
                        "size": desired_sizes[0] if desired_sizes else None,
                    }
                },
            )
    return profile


@app.post("/telegram/callback")
async def telegram_callback(request: Request):
    expected_secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "").strip()
    supplied_secret = request.headers.get("x-telegram-bot-api-secret-token", "")
    if not expected_secret:
        raise HTTPException(503, "Telegram webhook etkin degil")
    if not hmac.compare_digest(supplied_secret, expected_secret):
        raise HTTPException(401, "Gecersiz Telegram webhook imzasi")

    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(400, "Gecersiz Telegram callback verisi") from exc
    callback = body.get("callback_query")
    if not isinstance(callback, dict):
        return {"ok": True, "ignored": True}
    parts = str(callback.get("data") or "").split(":")
    if len(parts) != 3 or parts[0] != "feedback":
        return {"ok": True, "ignored": True}
    _, alert_id, code = parts
    labels = {
        "bought": "Satın aldı",
        "no_size": "Beden yoktu",
        "wrong": "Yanlış ürün",
    }
    if code not in labels or not alert_id or len(alert_id) > 80:
        raise HTTPException(400, "Gecersiz geri bildirim")

    update = await db.alerts.update_one(
        {"id": alert_id},
        {
            "$set": {
                "feedback": code,
                "feedback_label": labels[code],
                "feedback_at": datetime.now(timezone.utc),
            }
        },
    )
    if not update.matched_count:
        raise HTTPException(404, "Alarm bulunamadi")

    callback_id = callback.get("id")
    token = (await get_secret(db, "telegram_bot_token")).strip()
    if callback_id and token:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(
                    f"https://api.telegram.org/bot{token}/answerCallbackQuery",
                    json={"callback_query_id": callback_id, "text": f"Kaydedildi: {labels[code]}"},
                )
        except Exception as exc:
            logger.warning("Telegram callback cevabi gonderilemedi: %s", exc)
    return {"ok": True, "feedback": code}


# ── B5: GS1 Digital Link ─────────────────────────────────────────────────

class GS1ParseRequest(BaseModel):
    url: str

@api.post("/gs1/parse")
async def gs1_parse(body: GS1ParseRequest):
    """Parse a GS1 Digital Link URL without opening it."""
    result = parse_gs1_digital_link(body.url)
    return result


# ── B4: Physical Price Evidence ──────────────────────────────────────────

class PhysicalPriceEvidenceCreate(BaseModel):
    product_id: str
    store_name: str
    price: float
    currency: str = "TRY"
    source_type: Literal["shelf_label", "receipt", "manual"] = "manual"
    notes: str = ""
    identifiers: dict = Field(default_factory=dict)

@api.post("/evidence/physical-price")
async def add_physical_price_evidence(body: PhysicalPriceEvidenceCreate):
    """Record a physical shelf-label or receipt price observation."""
    document = await create_physical_price_evidence(
        db,
        product_id=body.product_id,
        value={
            "store_name": body.store_name,
            "observed_price": body.price,
            "currency": body.currency,
            "source_type": body.source_type,
            "notes": body.notes,
            "identifiers": body.identifiers,
        },
    )
    return {"status": "ok", "evidence_id": document.get("id")}

@api.get("/evidence/physical-price/{product_id}")
async def get_physical_price_evidence(product_id: str, limit: int = 20):
    """List physical price observations for a product."""
    rows = await list_physical_price_evidence(db, product_id=product_id, limit=limit)
    return {"product_id": product_id, "evidence": rows}

@api.post("/evidence/physical-price/moderate")
async def moderate_evidence(product_id: str):
    """Run corroboration check on physical price evidence for a product."""
    result = await moderate_physical_price_evidence(db, product_id=product_id)
    return {"product_id": product_id, "moderation": result}


# ── B3: Visual Search ────────────────────────────────────────────────────

@api.post("/visual-search")
async def visual_search(image: UploadFile = File(...)):
    """Find visually similar products by uploading a query image."""
    from visual_search_service import search_by_image
    data = await image.read()
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "Gorsel dosyasi cok buyuk")
    results = await search_by_image(db, data)
    return {"results": results, "count": len(results)}

@api.get("/visual-search/stats")
async def visual_search_stats():
    """Return visual catalog statistics."""
    from visual_search_service import catalog_stats
    stats = await catalog_stats(db)
    return stats

@api.post("/visual-search/index")
async def visual_search_index_image(listing_url: str, image_url: str, product_id: str = "", store: str = "", title: str = ""):
    """Manually index a listing image into the visual catalog."""
    from visual_search_service import index_listing_image
    doc = await index_listing_image(
        db, listing_url=listing_url, image_url=image_url,
        product_id=product_id or None, store=store or None, title=title or None,
    )
    return {"status": "ok" if doc else "skipped", "image_sha256": (doc or {}).get("image_sha256")}


# ── B1: Telemetry (Field Testing) ────────────────────────────────────────

@api.post("/telemetry/scan-event")
async def telemetry_scan_event(payload: dict):
    from telemetry_service import record_scan_event
    scan_id = await record_scan_event(db, payload)
    return {"status": "ok", "scan_id": scan_id}

@api.post("/telemetry/match-feedback")
async def telemetry_match_feedback(payload: dict):
    from telemetry_service import record_match_feedback
    feedback_id = await record_match_feedback(db, payload)
    return {"status": "ok", "feedback_id": feedback_id}

@api.get("/telemetry/summary")
async def telemetry_summary():
    from telemetry_service import get_weekly_summary
    return await get_weekly_summary(db)


@api.get("/")
async def root():
    return {"app": "ShoeHunter AI", "status": "ok", "version": app_version()}


app.include_router(api)
app.add_middleware(SecurityMiddleware, db=db)

configured_origins = [
    origin.strip()
    for origin in os.environ.get("CORS_ORIGINS", "").split(",")
    if origin.strip() and origin.strip() != "*"
]
if not configured_origins:
    configured_origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=configured_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)
