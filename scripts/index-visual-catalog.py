"""Populate the private visual candidate catalog from verified listing images.

The command reads image URLs already attached to ShoeHunter listings.  Each
store is limited to an explicit CDN allowlist; every redirect is revalidated,
private IP destinations are rejected and responses are byte/type bounded.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urljoin

import httpx
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from security import URLValidationError, validate_remote_url  # noqa: E402
from visual_candidates import MAX_IMAGE_BYTES, VisualIndexMetadata  # noqa: E402
from visual_catalog_service import (  # noqa: E402
    configured_embedding_provider,
    ensure_visual_catalog_indexes,
    upsert_visual_record,
)

IMAGE_DOMAINS_BY_STORE = {
    "amazon": ("m.media-amazon.com",),
    "barcin": ("9b6e8d-barcin.akinoncloudcdn.com",),
    "decathlon": ("contents.mediadecathlon.com",),
    "flo": ("floimages.mncdn.com",),
    "hepsiburada": ("productimages.hepsiburada.net",),
    "intersport": ("aad216.a-cdn.akinoncloud.com", "aad216.cdn.akinoncloud.com"),
    "kaptanspor": ("kaptanspor.com.tr",),
    "korayspor": ("p-korayspor.sm.mncdn.com",),
    "n11": ("n11scdn2-im.akamaized.net",),
    "newbalance": ("newbalance.sm.mncdn.com",),
    "nike": ("static.nike.com",),
    "puma": ("images.puma.net",),
    "sneaksup": ("img-phantomsneaksup.sm.mncdn.com",),
    "sportive": ("0990b9.a-cdn.akinoncloud.com",),
    "superstep": ("8f08a8-ss.akinoncloudcdn.com",),
    "trendyol": ("cdn.dsmcdn.com",),
    "yalispor": ("minio.yalispor.com.tr",),
}

SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
REDIRECT_CODES = {301, 302, 303, 307, 308}


def category_from_title(value: str | None) -> str:
    title = str(value or "").casefold()
    if any(token in title for token in ("ayakkabı", "ayakkabi", "sneaker", "bot", "terlik")):
        return "shoes"
    if any(token in title for token in ("ceket", "mont", "yağmurluk", "yagmurluk")):
        return "outerwear"
    if any(token in title for token in ("tişört", "tisort", "sweat", "üst", "ust")):
        return "tops"
    if any(token in title for token in ("pantolon", "şort", "sort", "tayt")):
        return "bottoms"
    return "products"


def safe_record_id(listing: dict) -> str:
    raw = str(listing.get("id") or "").strip()
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", raw):
        return raw
    raise ValueError("listing id is missing or unsafe")


async def _fetch_verified_image_once(client: httpx.AsyncClient, url: str, allowed_domains: tuple[str, ...]) -> tuple[bytes, str]:
    current = str(url or "").strip()
    for _ in range(4):
        current = await validate_remote_url(current, allowed_domains, resolve_dns=True)
        async with client.stream("GET", current, follow_redirects=False) as response:
            if response.status_code in REDIRECT_CODES:
                location = response.headers.get("location")
                if not location:
                    raise ValueError("redirect has no location")
                current = urljoin(current, location)
                continue
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            if content_type not in SUPPORTED_IMAGE_TYPES:
                raise ValueError("response is not a supported image")
            declared_length = int(response.headers.get("content-length") or 0)
            if declared_length > MAX_IMAGE_BYTES:
                raise ValueError("image exceeds the byte limit")
            chunks: list[bytes] = []
            size = 0
            async for chunk in response.aiter_bytes():
                size += len(chunk)
                if size > MAX_IMAGE_BYTES:
                    raise ValueError("image exceeds the byte limit")
                chunks.append(chunk)
            if size == 0:
                raise ValueError("image response is empty")
            return b"".join(chunks), content_type
    raise ValueError("too many image redirects")


async def fetch_verified_image(client: httpx.AsyncClient, url: str, allowed_domains: tuple[str, ...]) -> tuple[bytes, str]:
    last_error: httpx.HTTPStatusError | None = None
    for attempt in range(3):
        try:
            return await _fetch_verified_image_once(client, url, allowed_domains)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code not in {429, 500, 502, 503, 504}:
                raise
            last_error = exc
            await asyncio.sleep(2 ** attempt)
    assert last_error is not None
    raise last_error


async def populate(*, limit: int, store_filter: set[str], dry_run: bool) -> Counter:
    load_dotenv(ROOT / ".env")
    client = AsyncIOMotorClient(
        os.environ.get("MONGO_URL", "mongodb://localhost:27017"),
        serverSelectionTimeoutMS=5_000,
    )
    db = client[os.environ.get("DB_NAME", "shoehunter_ai")]
    counts: Counter = Counter()
    try:
        await client.admin.command("ping")
        await ensure_visual_catalog_indexes(db)
        provider = configured_embedding_provider()
        counts["embedding_enabled"] = int(provider is not None)
        query = {"image": {"$exists": True, "$nin": ["", None]}}
        if store_filter:
            query["store_slug"] = {"$in": sorted(store_filter)}
        listings = await db.listings.find(query, {"_id": 0}).sort("id", 1).limit(limit).to_list(limit)
        product_ids = sorted({str(row.get("product_id")) for row in listings if row.get("product_id")})
        products = {
            row["id"]: row
            for row in await db.products.find(
                {"id": {"$in": product_ids}},
                {"_id": 0, "id": 1, "name": 1, "brand": 1, "model": 1, "identity": 1},
            ).to_list(len(product_ids) or 1)
        }
        existing_ids = set(
            await db.visual_candidate_index.distinct("metadata.record_id", {"metadata.record_id": {"$in": [
                str(row.get("id")) for row in listings if row.get("id")
            ]}})
        )
        timeout = httpx.Timeout(20.0, connect=10.0)
        headers = {"User-Agent": "ShoeHunterVisualCatalog/0.6 (+local-catalog-indexer)"}
        async with httpx.AsyncClient(timeout=timeout, headers=headers) as http:
            for listing in listings:
                counts["seen"] += 1
                if str(listing.get("id") or "") in existing_ids and not dry_run:
                    counts["already_indexed"] += 1
                    continue
                store_slug = str(listing.get("store_slug") or "").strip().lower()
                domains = IMAGE_DOMAINS_BY_STORE.get(store_slug)
                if not domains:
                    counts["skipped_store_domain"] += 1
                    continue
                try:
                    record_id = safe_record_id(listing)
                    product_id = str(listing.get("product_id") or record_id)
                    product = products.get(product_id, {})
                    title = str(listing.get("title") or product.get("name") or record_id)
                    identity = product.get("identity") if isinstance(product.get("identity"), dict) else {}
                    brand = product.get("brand") or identity.get("brand")
                    model_code = listing.get("model_code") or product.get("model")
                    metadata = VisualIndexMetadata(
                        record_id=record_id,
                        canonical_product_id=product_id,
                        category=category_from_title(title),
                        source_name=store_slug,
                        source_item_id=record_id,
                        display_name=title,
                        variant_id=record_id,
                        image_role="product",
                        brand=brand,
                        model_code=model_code,
                    )
                    if dry_run:
                        await validate_remote_url(listing["image"], domains, resolve_dns=True)
                        counts["validated"] += 1
                        continue
                    data, content_type = await fetch_verified_image(http, listing["image"], domains)
                    await upsert_visual_record(
                        db,
                        image_data=data,
                        content_type=content_type,
                        metadata=metadata,
                    )
                    counts["indexed"] += 1
                except (URLValidationError, ValueError, httpx.HTTPError) as exc:
                    counts[f"failed:{type(exc).__name__}"] += 1
                    print(f"SKIP {listing.get('id')}: {exc}", file=sys.stderr)
        return counts
    finally:
        client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Index verified ShoeHunter listing images")
    parser.add_argument("--limit", type=int, default=500, choices=range(1, 5001), metavar="1..5000")
    parser.add_argument("--store", action="append", default=[], help="Only index this store slug")
    parser.add_argument("--dry-run", action="store_true", help="Validate URLs without downloading images")
    args = parser.parse_args()
    result = asyncio.run(
        populate(
            limit=args.limit,
            store_filter={str(item).strip().lower() for item in args.store if str(item).strip()},
            dry_run=args.dry_run,
        )
    )
    print(" ".join(f"{key}={result[key]}" for key in sorted(result)))
    return 0 if not any(key.startswith("failed:") for key in result) else 2


if __name__ == "__main__":
    raise SystemExit(main())
