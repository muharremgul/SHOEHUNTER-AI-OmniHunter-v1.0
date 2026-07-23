"""Visual similarity search service — catalog management and query API.

This service stores per-listing CLIP embeddings in MongoDB and provides a
brute-force cosine-similarity search over them.  The catalog is populated
lazily: when a listing with an image URL is first encountered, its embedding
is computed and cached.

The brute-force approach is intentional for the current catalog size (<50k).
When the catalog grows beyond 100k a FAISS IVF index should be introduced.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from visual_search_index import (
    compute_embedding_from_bytes,
    cosine_similarity,
    image_hash,
)

logger = logging.getLogger("shoehunter.visual_search")

SIMILARITY_THRESHOLD_SAME = 0.92
SIMILARITY_THRESHOLD_SIMILAR = 0.75
MAX_RESULTS = 20


async def ensure_visual_search_indexes(db) -> None:
    """Create MongoDB indexes for the visual_embeddings collection."""
    collection = db.visual_embeddings
    await collection.create_index("image_sha256", unique=True)
    await collection.create_index("listing_url")
    await collection.create_index("product_id")
    await collection.create_index("store")


async def index_listing_image(
    db,
    *,
    listing_url: str,
    image_url: str,
    image_data: bytes,
    product_id: str | None = None,
    store: str | None = None,
    title: str | None = None,
) -> dict[str, Any] | None:
    """Embed caller-supplied bytes and store listing metadata; never fetch a URL."""
    if not image_url or not image_data:
        return None

    # Check if already indexed by image URL
    existing = await db.visual_embeddings.find_one(
        {"image_url": image_url}, {"_id": 0, "image_sha256": 1}
    )
    if existing:
        return existing

    sha = image_hash(image_data)
    # Dedup by content hash
    existing = await db.visual_embeddings.find_one({"image_sha256": sha}, {"_id": 0})
    if existing:
        return existing

    try:
        embedding = compute_embedding_from_bytes(image_data)
    except Exception as exc:
        logger.warning("Embedding hesaplanamadi %s: %s", image_url, exc)
        return None

    document = {
        "image_sha256": sha,
        "image_url": image_url,
        "listing_url": listing_url,
        "product_id": product_id,
        "store": store,
        "title": title or "",
        "embedding": embedding,
        "created_at": datetime.now(UTC),
    }
    try:
        await db.visual_embeddings.insert_one(document)
    except Exception:
        pass  # Duplicate key — race condition is fine
    document.pop("_id", None)
    return document


async def search_by_image(
    db,
    image_data: bytes,
    *,
    limit: int = MAX_RESULTS,
    threshold: float = SIMILARITY_THRESHOLD_SIMILAR,
) -> list[dict[str, Any]]:
    """Find visually similar catalog images by uploading a query image."""
    query_embedding = compute_embedding_from_bytes(image_data)

    # Brute-force scan — acceptable for <50k documents
    cursor = db.visual_embeddings.find(
        {},
        {"_id": 0, "embedding": 1, "listing_url": 1, "image_url": 1,
         "product_id": 1, "store": 1, "title": 1},
    )
    results = []
    async for doc in cursor:
        doc_embedding = doc.get("embedding")
        if not doc_embedding:
            continue
        similarity = cosine_similarity(query_embedding, doc_embedding)
        if similarity >= threshold:
            results.append({
                "listing_url": doc.get("listing_url"),
                "image_url": doc.get("image_url"),
                "product_id": doc.get("product_id"),
                "store": doc.get("store"),
                "title": doc.get("title"),
                "similarity": round(similarity, 4),
                "match_type": "same" if similarity >= SIMILARITY_THRESHOLD_SAME else "similar",
            })

    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:limit]


async def catalog_stats(db) -> dict[str, Any]:
    """Return basic catalog statistics."""
    total = await db.visual_embeddings.count_documents({})
    stores = await db.visual_embeddings.distinct("store")
    return {
        "total_embeddings": total,
        "stores": sorted(s for s in stores if s),
    }
