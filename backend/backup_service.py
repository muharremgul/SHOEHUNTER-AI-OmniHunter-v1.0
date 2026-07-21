import csv
import hashlib
import io
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path


BACKUP_COLLECTIONS = [
    "products",
    "listings",
    "rules",
    "alerts",
    "price_history",
    "watch_queries",
    "candidate_listings",
    "discovery_runs",
    "store_health",
    "settings",
    "user_profile",
]


def _json_default(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def backup_dir():
    path = Path(os.environ.get("BACKUP_DIR", Path(__file__).resolve().parents[1] / "backups"))
    path.mkdir(parents=True, exist_ok=True)
    return path


async def create_json_backup(db):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    payload = {
        "schema_version": 2,
        "created_at": datetime.now(timezone.utc),
        "collections": {},
    }
    for name in BACKUP_COLLECTIONS:
        documents = await db[name].find({}, {"_id": 0}).to_list(None)
        if name == "settings":
            for document in documents:
                (document.get("telegram") or {}).pop("bot_token", None)
        payload["collections"][name] = documents
    destination = backup_dir() / f"shoehunter-{stamp}.json"
    temporary = destination.with_suffix(".json.tmp")
    content = json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default)
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(destination)
    destination.with_suffix(".json.sha256").write_text(
        hashlib.sha256(content.encode("utf-8")).hexdigest() + "\n",
        encoding="ascii",
    )
    verify_backup(destination)
    prune_old_backups()
    return {"path": str(destination), "collections": {key: len(value) for key, value in payload["collections"].items()}}


def verify_backup(path):
    source = Path(path)
    content = source.read_text(encoding="utf-8")
    checksum_path = source.with_suffix(source.suffix + ".sha256")
    if checksum_path.exists():
        expected = checksum_path.read_text(encoding="ascii").strip().split()[0]
        actual = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if actual != expected:
            raise ValueError("Yedek butunluk dogrulamasi basarisiz")
    payload = json.loads(content)
    if payload.get("schema_version") != 2 or not isinstance(payload.get("collections"), dict):
        raise ValueError("Gecersiz yedek semasi")
    for required in ("products", "listings", "watch_queries"):
        if required not in payload["collections"]:
            raise ValueError(f"Yedekte {required} koleksiyonu eksik")
    return True


def prune_old_backups():
    retention_days = max(1, int(os.environ.get("BACKUP_RETENTION_DAYS", "30")))
    cutoff = datetime.now(timezone.utc).timestamp() - retention_days * 86400
    removed = 0
    for source in backup_dir().glob("shoehunter-*.json"):
        if source.stat().st_mtime >= cutoff:
            continue
        checksum = source.with_suffix(source.suffix + ".sha256")
        source.unlink(missing_ok=True)
        checksum.unlink(missing_ok=True)
        removed += 1
    return removed


async def product_export(db):
    products = await db.products.find({}, {"_id": 0}).to_list(None)
    listings = await db.listings.find({}, {"_id": 0, "last_raw": 0}).to_list(None)
    rules = await db.rules.find({}, {"_id": 0}).to_list(None)
    return json.dumps(
        {"schema_version": 2, "created_at": datetime.now(timezone.utc), "products": products, "listings": listings, "rules": rules},
        ensure_ascii=False,
        indent=2,
        default=_json_default,
    )


async def price_history_csv(db):
    rows = await db.price_history.find({}, {"_id": 0}).sort("checked_at", 1).to_list(None)
    output = io.StringIO()
    fields = ["id", "product_id", "listing_id", "store", "price", "old_price", "cart_price", "stock_status", "checked_at"]
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()
