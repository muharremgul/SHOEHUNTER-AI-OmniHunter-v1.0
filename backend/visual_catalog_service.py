"""Persistent, network-free visual candidate catalog.

Only user-supplied encoded image bytes enter this service. Source URLs and
filesystem paths are deliberately excluded from the stored contract. Visual
similarity produces review candidates; it never asserts an exact SKU.
"""

from __future__ import annotations

import hashlib
import os
import threading
from pathlib import Path
from typing import Any

from onnx_clip_provider import VerifiedOnnxClipProvider
from visual_candidates import (
    INDEX_SCHEMA_VERSION,
    MAX_INDEX_RECORDS,
    EmbeddingDescriptor,
    EmbeddingProviderUnavailable,
    IndexedVisual,
    PreloadedOpenClipProvider,
    VisualCandidateError,
    VisualIndexMetadata,
    fingerprint_image,
    rank_visual_candidates,
)

_provider_lock = threading.Lock()
_configured_provider = None
_provider_initialized = False

STANDARD_ONNX_MODEL_PATH = Path(__file__).parent / ".models" / "qdrant-clip-vit-b32-vision.onnx"
STANDARD_ONNX_MODEL_SHA256 = "c68d3d9a200ddd2a8c8a5510b576d4c94d1ae383bf8b36dd8c084f94e1fb4d63"
STANDARD_ONNX_MODEL_LICENSE = "MIT"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def configured_embedding_provider():
    """Load one verified local embedding provider once.

    The standard CPU path is the locally installed Qdrant CLIP ViT-B/32 ONNX
    artifact.  It has a pinned SHA-256 and MIT model-card license.  OpenCLIP
    remains available for deployments that explicitly provide a compatible
    local checkpoint.  Neither path downloads weights.
    """

    global _configured_provider, _provider_initialized
    if _provider_initialized:
        return _configured_provider
    with _provider_lock:
        if _provider_initialized:
            return _configured_provider
        selected = os.environ.get("VISUAL_EMBEDDING_PROVIDER", "").strip().lower()
        if selected in {"disabled", "none", "off"}:
            _provider_initialized = True
            return None
        onnx_path = os.environ.get("CLIP_ONNX_MODEL_PATH", "").strip()
        if not selected and (onnx_path or STANDARD_ONNX_MODEL_PATH.is_file()):
            selected = "onnx_clip"
        model_name = os.environ.get("OPENCLIP_MODEL_NAME", "").strip()
        checkpoint = os.environ.get("OPENCLIP_CHECKPOINT_PATH", "").strip()
        expected_hash = os.environ.get("OPENCLIP_WEIGHTS_SHA256", "").strip().lower()
        license_id = os.environ.get("OPENCLIP_LICENSE_ID", "").strip()
        if not selected and any((model_name, checkpoint, expected_hash, license_id)):
            selected = "openclip"
        if not selected:
            _provider_initialized = True
            return None
        if selected == "onnx_clip":
            path = Path(onnx_path).expanduser().resolve() if onnx_path else STANDARD_ONNX_MODEL_PATH.resolve()
            custom_path = bool(onnx_path)
            onnx_hash = os.environ.get("CLIP_ONNX_MODEL_SHA256", "").strip().lower()
            onnx_license = os.environ.get("CLIP_ONNX_LICENSE_ID", "").strip()
            onnx_model_name = os.environ.get(
                "CLIP_ONNX_MODEL_ID", "Qdrant-clip-ViT-B-32-vision"
            ).strip()
            if custom_path and not all((onnx_hash, onnx_license, onnx_model_name)):
                raise EmbeddingProviderUnavailable("Özel CLIP ONNX yapılandırması eksik")
            _configured_provider = VerifiedOnnxClipProvider(
                model_path=path,
                expected_sha256=onnx_hash or STANDARD_ONNX_MODEL_SHA256,
                license_id=onnx_license or STANDARD_ONNX_MODEL_LICENSE,
                model_name=onnx_model_name,
                weights_id=path.name.replace(" ", "-")[:128],
                dimensions=512,
            )
            _provider_initialized = True
            return _configured_provider
        if selected != "openclip":
            raise EmbeddingProviderUnavailable("VISUAL_EMBEDDING_PROVIDER desteklenmiyor")
        if not any((model_name, checkpoint, expected_hash, license_id)):
            _provider_initialized = True
            return None
        if not all((model_name, checkpoint, expected_hash, license_id)):
            raise EmbeddingProviderUnavailable("OpenCLIP yapılandırması eksik")
        path = Path(checkpoint).expanduser().resolve()
        if not path.is_file():
            raise EmbeddingProviderUnavailable("OpenCLIP checkpoint dosyası bulunamadı")
        actual_hash = _sha256_file(path)
        if actual_hash != expected_hash:
            raise EmbeddingProviderUnavailable("OpenCLIP checkpoint SHA-256 doğrulaması başarısız")
        try:
            import open_clip
        except ImportError as exc:
            raise EmbeddingProviderUnavailable("open_clip_torch kurulu değil") from exc
        model, _, preprocess = open_clip.create_model_and_transforms(
            model_name,
            pretrained=str(path),
            device="cpu",
        )
        model.eval()
        dimensions = int(getattr(getattr(model, "visual", None), "output_dim", 0) or 512)
        descriptor = EmbeddingDescriptor(
            provider="openclip",
            model_name=model_name.replace("/", "-")[:128],
            weights_id=path.stem.replace(" ", "-")[:128],
            weights_sha256=actual_hash,
            license_id=license_id,
            dimensions=dimensions,
        )
        _configured_provider = PreloadedOpenClipProvider(
            model=model,
            preprocess=preprocess,
            descriptor=descriptor,
            device="cpu",
        )
        _provider_initialized = True
        return _configured_provider


def configured_openclip_provider():
    """Backward-compatible alias for the configured local embedding provider."""

    return configured_embedding_provider()


async def ensure_visual_catalog_indexes(db) -> None:
    collection = db.visual_candidate_index
    await collection.create_index("metadata.record_id", unique=True, name="uq_visual_record_id")
    await collection.create_index("metadata.canonical_product_id", name="ix_visual_product")
    await collection.create_index("metadata.category", name="ix_visual_category")
    await collection.create_index("fingerprint.content_sha256", name="ix_visual_content_hash")


async def upsert_visual_record(
    db,
    *,
    image_data: bytes,
    content_type: str | None,
    metadata: VisualIndexMetadata | dict[str, Any],
) -> dict[str, Any]:
    validated_metadata = (
        metadata if isinstance(metadata, VisualIndexMetadata) else VisualIndexMetadata(**metadata)
    )
    fingerprint = fingerprint_image(
        image_data,
        content_type=content_type,
        embedding_provider=configured_embedding_provider(),
    )
    record = IndexedVisual(validated_metadata, fingerprint)
    document = record.to_index_document()
    await db.visual_candidate_index.replace_one(
        {"metadata.record_id": validated_metadata.record_id},
        document,
        upsert=True,
    )
    return document


async def search_visual_records(
    db,
    *,
    image_data: bytes,
    content_type: str | None,
    category: str | None = None,
    include_cross_category: bool = False,
    minimum_score: float = 0.0,
    limit: int = 10,
    model_code_hint: str | None = None,
    brand_hint: str | None = None,
) -> dict[str, Any]:
    query: dict[str, Any] = {"schema_version": INDEX_SCHEMA_VERSION}
    if category and not include_cross_category:
        query["metadata.category"] = category
    rows = await db.visual_candidate_index.find(query).to_list(MAX_INDEX_RECORDS + 1)
    if len(rows) > MAX_INDEX_RECORDS:
        raise VisualCandidateError("visual catalog exceeds the safe in-process ranking limit")

    records = []
    invalid_records = 0
    for row in rows:
        try:
            records.append(IndexedVisual.from_index_document(row))
        except VisualCandidateError:
            invalid_records += 1

    query_fingerprint = fingerprint_image(
        image_data,
        content_type=content_type,
        embedding_provider=configured_embedding_provider(),
    )
    result = rank_visual_candidates(
        query_fingerprint,
        records,
        category=category,
        include_cross_category=include_cross_category,
        minimum_score=minimum_score,
        limit=limit,
        model_code_hint=model_code_hint,
        brand_hint=brand_hint,
    ).to_dict()
    result["catalog_records_considered"] = len(records)
    result["invalid_catalog_records_skipped"] = invalid_records
    return result


async def visual_catalog_stats(db) -> dict[str, Any]:
    collection = db.visual_candidate_index
    total = await collection.count_documents({"schema_version": INDEX_SCHEMA_VERSION})
    categories = await collection.distinct("metadata.category")
    sources = await collection.distinct("metadata.source_name")
    embedded = await collection.count_documents({"fingerprint.embedding": {"$ne": None}})
    return {
        "schema_version": INDEX_SCHEMA_VERSION,
        "total_records": total,
        "categories": sorted(item for item in categories if item),
        "sources": sorted(item for item in sources if item),
        "records_with_embedding": embedded,
        "ranking_mode": "embedding_plus_fingerprint" if embedded else "deterministic_fingerprint",
        "vector_storage": "mongodb_bounded_in_process_ranking",
        "vector_migration_threshold_records": MAX_INDEX_RECORDS,
        "vector_migration_recommended": total > MAX_INDEX_RECORDS,
        "capacity_remaining_before_migration": max(0, MAX_INDEX_RECORDS - total),
        "exact_sku_decisions": False,
    }
