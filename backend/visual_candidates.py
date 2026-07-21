"""Deterministic, local-only visual candidate generation.

This module deliberately does *not* decide that two images are the same SKU.
It produces reviewable candidates from inexpensive visual signals and keeps the
evidence required by a later product-identity stage.

Security boundary:

* callers provide encoded image bytes; paths and URLs are never accepted;
* images are decoded in memory with byte, pixel, edge and frame limits;
* no network or filesystem access is performed;
* the optional embedding provider must already be loaded by the caller.

The deterministic fingerprint is intended as an offline MVP and as a fallback
when no licensed embedding model is configured.  It is not a biometric or
cryptographic image identity mechanism.
"""

from __future__ import annotations

import hashlib
import math
import re
import threading
import warnings
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from io import BytesIO
from typing import Any, Protocol

from PIL import Image, ImageOps, UnidentifiedImageError

FINGERPRINT_SCHEMA_VERSION = "shoehunter.visual-fingerprint.v1"
INDEX_SCHEMA_VERSION = "shoehunter.visual-index.v1"
SEARCH_SCHEMA_VERSION = "shoehunter.visual-search.v1"

MAX_IMAGE_BYTES = 12 * 1024 * 1024
MAX_IMAGE_PIXELS = 32_000_000
MAX_IMAGE_EDGE = 12_000
MAX_EMBEDDING_DIMENSIONS = 8_192
MAX_INDEX_RECORDS = 100_000
MAX_RESULTS = 100

SUPPORTED_CONTENT_TYPES = {
    "image/jpeg": "JPEG",
    "image/png": "PNG",
    "image/webp": "WEBP",
}
FORMAT_CONTENT_TYPES = {value: key for key, value in SUPPORTED_CONTENT_TYPES.items()}

_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_CATEGORY_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_IMAGE_ROLES = {"product", "package", "label", "detail", "lifestyle", "unknown"}
_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")


class VisualCandidateError(ValueError):
    """Safe validation or feature-generation failure."""


class EmbeddingProviderUnavailable(RuntimeError):
    """The explicitly configured optional embedding runtime is unavailable."""


def _validated_identifier(field_name: str, value: str | None, *, required: bool = True) -> str | None:
    clean = str(value or "").strip()
    if not clean:
        if required:
            raise VisualCandidateError(f"{field_name} is required")
        return None
    if not _IDENTIFIER_RE.fullmatch(clean):
        raise VisualCandidateError(f"{field_name} contains unsupported characters")
    return clean


def _validated_text(field_name: str, value: str | None, *, max_length: int, required: bool = False) -> str | None:
    clean = re.sub(r"\s+", " ", str(value or "")).strip()
    if not clean:
        if required:
            raise VisualCandidateError(f"{field_name} is required")
        return None
    if len(clean) > max_length or any(ord(char) < 32 for char in clean):
        raise VisualCandidateError(f"{field_name} is invalid")
    return clean


def _validated_category(value: str) -> str:
    clean = str(value or "").strip().lower()
    if not _CATEGORY_RE.fullmatch(clean):
        raise VisualCandidateError("category must be a lowercase slug")
    return clean


@dataclass(frozen=True)
class VisualIndexMetadata:
    """Bounded, URL-free metadata stored beside a visual fingerprint.

    `canonical_product_id` identifies a product family.  `variant_id` may carry
    a size/colour variant known by the caller, but visual similarity never
    asserts or changes it.  `source_item_id` is an opaque retailer/database ID,
    not a URL.
    """

    record_id: str
    canonical_product_id: str
    category: str
    source_name: str
    source_item_id: str
    display_name: str
    variant_id: str | None = None
    image_role: str = "product"
    brand: str | None = None
    model_code: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "record_id", _validated_identifier("record_id", self.record_id))
        object.__setattr__(
            self,
            "canonical_product_id",
            _validated_identifier("canonical_product_id", self.canonical_product_id),
        )
        object.__setattr__(self, "category", _validated_category(self.category))
        object.__setattr__(self, "source_name", _validated_identifier("source_name", self.source_name))
        object.__setattr__(
            self,
            "source_item_id",
            _validated_identifier("source_item_id", self.source_item_id),
        )
        object.__setattr__(
            self,
            "variant_id",
            _validated_identifier("variant_id", self.variant_id, required=False),
        )
        object.__setattr__(
            self,
            "display_name",
            _validated_text("display_name", self.display_name, max_length=240, required=True),
        )
        object.__setattr__(self, "brand", _validated_text("brand", self.brand, max_length=80))
        object.__setattr__(self, "model_code", _validated_text("model_code", self.model_code, max_length=80))
        role = str(self.image_role or "").strip().lower()
        if role not in _IMAGE_ROLES:
            raise VisualCandidateError("image_role is not supported")
        object.__setattr__(self, "image_role", role)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EmbeddingDescriptor:
    """Audit data for an optional, locally loaded embedding model."""

    provider: str
    model_name: str
    weights_id: str
    weights_sha256: str
    license_id: str
    dimensions: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider", _validated_identifier("provider", self.provider))
        object.__setattr__(self, "model_name", _validated_identifier("model_name", self.model_name))
        object.__setattr__(self, "weights_id", _validated_identifier("weights_id", self.weights_id))
        digest = str(self.weights_sha256 or "").strip().lower()
        if not _SHA256_RE.fullmatch(digest):
            raise VisualCandidateError("weights_sha256 must be a full SHA-256 digest")
        object.__setattr__(self, "weights_sha256", digest)
        object.__setattr__(
            self,
            "license_id",
            _validated_text("license_id", self.license_id, max_length=120, required=True),
        )
        if not 1 <= int(self.dimensions) <= MAX_EMBEDDING_DIMENSIONS:
            raise VisualCandidateError("embedding dimensions are outside the safe range")
        object.__setattr__(self, "dimensions", int(self.dimensions))

    @property
    def identity(self) -> str:
        return f"{self.provider}:{self.model_name}:{self.weights_id}:{self.weights_sha256[:12]}"

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["identity"] = self.identity
        return result

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> EmbeddingDescriptor:
        if not isinstance(value, Mapping):
            raise VisualCandidateError("embedding_descriptor must be an object")
        required = {
            "provider",
            "model_name",
            "weights_id",
            "weights_sha256",
            "license_id",
            "dimensions",
        }
        unknown = set(value) - required - {"identity"}
        if unknown or not required.issubset(value):
            raise VisualCandidateError("embedding_descriptor schema is invalid")
        descriptor = cls(**{key: value[key] for key in required})
        stored_identity = value.get("identity")
        if stored_identity is not None and stored_identity != descriptor.identity:
            raise VisualCandidateError("embedding_descriptor identity does not match its evidence")
        return descriptor


class ImageEmbeddingProvider(Protocol):
    """Minimal provider contract; implementations must not download at embed time."""

    @property
    def descriptor(self) -> EmbeddingDescriptor: ...

    def embed(self, image: Image.Image) -> Sequence[float]: ...


class PreloadedOpenClipProvider:
    """Adapter for an OpenCLIP model that the application already loaded locally.

    No model name is resolved and no checkpoint is downloaded here.  The caller
    must verify the checkpoint license, hash the local weights and pass both as
    descriptor evidence before constructing this adapter.
    """

    def __init__(
        self,
        *,
        model: Any,
        preprocess: Callable[[Image.Image], Any],
        descriptor: EmbeddingDescriptor,
        device: str = "cpu",
    ) -> None:
        if descriptor.provider.lower() != "openclip":
            raise VisualCandidateError("OpenCLIP adapter requires provider='openclip'")
        if not callable(preprocess) or not callable(getattr(model, "encode_image", None)):
            raise VisualCandidateError("a preloaded OpenCLIP model and preprocess callable are required")
        self._model = model
        self._preprocess = preprocess
        self._descriptor = descriptor
        self._device = str(device or "cpu")

    @property
    def descriptor(self) -> EmbeddingDescriptor:
        return self._descriptor

    def embed(self, image: Image.Image) -> Sequence[float]:
        try:
            import torch
        except ImportError as exc:  # pragma: no cover - optional deployment path
            raise EmbeddingProviderUnavailable("PyTorch is not installed for the optional OpenCLIP provider") from exc

        try:
            tensor = self._preprocess(image.copy()).unsqueeze(0).to(self._device)
            with torch.inference_mode():
                encoded = self._model.encode_image(tensor)
            return encoded[0].detach().cpu().tolist()
        except Exception as exc:  # pragma: no cover - depends on optional runtime
            raise EmbeddingProviderUnavailable("The preloaded OpenCLIP provider could not encode the image") from exc


@dataclass(frozen=True)
class VisualFingerprint:
    schema_version: str
    content_sha256: str
    content_type: str
    width: int
    height: int
    difference_hash: str
    average_hash: str
    color_histogram: tuple[float, ...]
    embedding: tuple[float, ...] | None = None
    embedding_descriptor: EmbeddingDescriptor | None = None

    def __post_init__(self) -> None:
        if self.schema_version != FINGERPRINT_SCHEMA_VERSION:
            raise VisualCandidateError("fingerprint schema version is not supported")
        digest = str(self.content_sha256 or "").strip().lower()
        if not _SHA256_RE.fullmatch(digest):
            raise VisualCandidateError("fingerprint content_sha256 is invalid")
        object.__setattr__(self, "content_sha256", digest)
        content_type = str(self.content_type or "").strip().lower()
        if content_type not in SUPPORTED_CONTENT_TYPES:
            raise VisualCandidateError("fingerprint content_type is invalid")
        object.__setattr__(self, "content_type", content_type)
        if isinstance(self.width, bool) or isinstance(self.height, bool):
            raise VisualCandidateError("fingerprint dimensions are invalid")
        width, height = int(self.width), int(self.height)
        if width < 1 or height < 1 or width * height > MAX_IMAGE_PIXELS or max(width, height) > MAX_IMAGE_EDGE:
            raise VisualCandidateError("fingerprint dimensions exceed the safety limit")
        object.__setattr__(self, "width", width)
        object.__setattr__(self, "height", height)
        for field_name in ("difference_hash", "average_hash"):
            value = str(getattr(self, field_name) or "").strip().lower()
            if not re.fullmatch(r"[a-f0-9]{16}", value):
                raise VisualCandidateError(f"fingerprint {field_name} is invalid")
            object.__setattr__(self, field_name, value)
        try:
            histogram = tuple(float(value) for value in self.color_histogram)
        except (TypeError, ValueError) as exc:
            raise VisualCandidateError("fingerprint color_histogram is invalid") from exc
        if (
            len(histogram) != 48
            or any(not math.isfinite(value) or value < 0.0 or value > 1.0 for value in histogram)
            or not 0.99 <= sum(histogram) <= 1.01
        ):
            raise VisualCandidateError("fingerprint color_histogram is invalid")
        object.__setattr__(self, "color_histogram", histogram)

        if (self.embedding is None) != (self.embedding_descriptor is None):
            raise VisualCandidateError("embedding vector and descriptor must be stored together")
        if self.embedding_descriptor is not None:
            if not isinstance(self.embedding_descriptor, EmbeddingDescriptor):
                raise VisualCandidateError("embedding_descriptor is invalid")
            try:
                embedding = tuple(float(value) for value in self.embedding or ())
            except (TypeError, ValueError) as exc:
                raise VisualCandidateError("fingerprint embedding is invalid") from exc
            if len(embedding) != self.embedding_descriptor.dimensions:
                raise VisualCandidateError("fingerprint embedding dimensions do not match its descriptor")
            if any(not math.isfinite(value) for value in embedding):
                raise VisualCandidateError("fingerprint embedding is invalid")
            norm = math.sqrt(sum(value * value for value in embedding))
            if not 0.999 <= norm <= 1.001:
                raise VisualCandidateError("fingerprint embedding must be normalized")
            object.__setattr__(self, "embedding", embedding)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "content_sha256": self.content_sha256,
            "content_type": self.content_type,
            "width": self.width,
            "height": self.height,
            "difference_hash": self.difference_hash,
            "average_hash": self.average_hash,
            "color_histogram": list(self.color_histogram),
            "embedding": list(self.embedding) if self.embedding is not None else None,
            "embedding_descriptor": (
                self.embedding_descriptor.to_dict() if self.embedding_descriptor is not None else None
            ),
        }


@dataclass(frozen=True)
class IndexedVisual:
    metadata: VisualIndexMetadata
    fingerprint: VisualFingerprint

    def to_index_document(self) -> dict[str, Any]:
        return {
            "schema_version": INDEX_SCHEMA_VERSION,
            "metadata": self.metadata.to_dict(),
            "fingerprint": self.fingerprint.to_dict(),
        }

    @classmethod
    def from_index_document(cls, document: Mapping[str, Any]) -> IndexedVisual:
        """Validate an untrusted persisted document before it enters ranking."""

        if not isinstance(document, Mapping):
            raise VisualCandidateError("index document must be an object")
        required = {"schema_version", "metadata", "fingerprint"}
        unknown = set(document) - required - {"_id"}
        if unknown or not required.issubset(document):
            raise VisualCandidateError("index document schema is invalid")
        if document.get("schema_version") != INDEX_SCHEMA_VERSION:
            raise VisualCandidateError("index document schema version is not supported")

        metadata_value = document.get("metadata")
        if not isinstance(metadata_value, Mapping):
            raise VisualCandidateError("index metadata must be an object")
        metadata_fields = {
            "record_id",
            "canonical_product_id",
            "category",
            "source_name",
            "source_item_id",
            "display_name",
            "variant_id",
            "image_role",
            "brand",
            "model_code",
        }
        if set(metadata_value) != metadata_fields:
            raise VisualCandidateError("index metadata schema is invalid")
        metadata = VisualIndexMetadata(**{key: metadata_value[key] for key in metadata_fields})

        fingerprint_value = document.get("fingerprint")
        if not isinstance(fingerprint_value, Mapping):
            raise VisualCandidateError("index fingerprint must be an object")
        fingerprint_fields = {
            "schema_version",
            "content_sha256",
            "content_type",
            "width",
            "height",
            "difference_hash",
            "average_hash",
            "color_histogram",
            "embedding",
            "embedding_descriptor",
        }
        if set(fingerprint_value) != fingerprint_fields:
            raise VisualCandidateError("index fingerprint schema is invalid")
        histogram = fingerprint_value.get("color_histogram")
        embedding = fingerprint_value.get("embedding")
        if not isinstance(histogram, (list, tuple)):
            raise VisualCandidateError("index color_histogram must be an array")
        if embedding is not None and not isinstance(embedding, (list, tuple)):
            raise VisualCandidateError("index embedding must be an array")
        descriptor_value = fingerprint_value.get("embedding_descriptor")
        descriptor = EmbeddingDescriptor.from_dict(descriptor_value) if descriptor_value is not None else None
        fingerprint = VisualFingerprint(
            schema_version=fingerprint_value["schema_version"],
            content_sha256=fingerprint_value["content_sha256"],
            content_type=fingerprint_value["content_type"],
            width=fingerprint_value["width"],
            height=fingerprint_value["height"],
            difference_hash=fingerprint_value["difference_hash"],
            average_hash=fingerprint_value["average_hash"],
            color_histogram=tuple(histogram),
            embedding=tuple(embedding) if embedding is not None else None,
            embedding_descriptor=descriptor,
        )
        return cls(metadata=metadata, fingerprint=fingerprint)


@dataclass(frozen=True)
class VisualCandidate:
    metadata: VisualIndexMetadata
    similarity_score: float
    evidence: Mapping[str, Any]
    candidate_only: bool = True
    exact_sku_decision: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata": self.metadata.to_dict(),
            "similarity_score": self.similarity_score,
            "candidate_only": self.candidate_only,
            "exact_sku_decision": self.exact_sku_decision,
            "evidence": dict(self.evidence),
        }


@dataclass(frozen=True)
class VisualSearchResult:
    query_fingerprint: VisualFingerprint
    requested_category: str | None
    candidates: tuple[VisualCandidate, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SEARCH_SCHEMA_VERSION,
            "interpretation": "candidate_generation_only",
            "query": self.query_fingerprint.to_dict(),
            "requested_category": self.requested_category,
            "candidate_count": len(self.candidates),
            "visual_candidates": [candidate.to_dict() for candidate in self.candidates],
            "safety": {
                "exact_sku_decision_made": False,
                "source_image_stored": False,
                "network_used": False,
            },
        }


def _safe_image_bytes(data: bytes | bytearray | memoryview) -> bytes:
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise VisualCandidateError("image input must be encoded bytes; paths and URLs are not accepted")
    if isinstance(data, memoryview):
        size = data.nbytes
    else:
        size = len(data)
    if size == 0:
        raise VisualCandidateError("image input is empty")
    if size > MAX_IMAGE_BYTES:
        raise VisualCandidateError("image input exceeds the byte limit")
    return bytes(data)


def _decode_image(
    data: bytes | bytearray | memoryview,
    content_type: str | None,
) -> tuple[Image.Image, str, str]:
    raw = _safe_image_bytes(data)
    declared_type = str(content_type or "").split(";", 1)[0].strip().lower() or None
    if declared_type is not None and declared_type not in SUPPORTED_CONTENT_TYPES:
        raise VisualCandidateError("only JPEG, PNG and WebP images are supported")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as source:
                detected_format = str(source.format or "").upper()
                if detected_format not in FORMAT_CONTENT_TYPES:
                    raise VisualCandidateError("the decoded image format is not supported")
                detected_type = FORMAT_CONTENT_TYPES[detected_format]
                if declared_type is not None and SUPPORTED_CONTENT_TYPES[declared_type] != detected_format:
                    raise VisualCandidateError("declared content type does not match the image")
                width, height = source.size
                if width < 1 or height < 1:
                    raise VisualCandidateError("image dimensions are invalid")
                if width * height > MAX_IMAGE_PIXELS or max(width, height) > MAX_IMAGE_EDGE:
                    raise VisualCandidateError("image dimensions exceed the safety limit")
                if int(getattr(source, "n_frames", 1)) != 1:
                    raise VisualCandidateError("animated or multi-frame images are not supported")
                source.load()
                normalized = ImageOps.exif_transpose(source)
                if "A" in normalized.getbands():
                    rgba = normalized.convert("RGBA")
                    background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
                    image = Image.alpha_composite(background, rgba).convert("RGB")
                else:
                    image = normalized.convert("RGB")
    except VisualCandidateError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning, UnidentifiedImageError, OSError) as exc:
        raise VisualCandidateError("image bytes could not be decoded safely") from exc

    if image.width * image.height > MAX_IMAGE_PIXELS or max(image.size) > MAX_IMAGE_EDGE:
        raise VisualCandidateError("normalized image dimensions exceed the safety limit")
    return image, hashlib.sha256(raw).hexdigest(), detected_type


def _hash_bits(bits: Sequence[bool]) -> str:
    value = 0
    for bit in bits:
        value = (value << 1) | int(bool(bit))
    return f"{value:0{max(1, len(bits) // 4)}x}"


def _difference_hash(image: Image.Image, size: int = 8) -> str:
    pixels = list(
        ImageOps.grayscale(image)
        .resize((size + 1, size), Image.Resampling.LANCZOS)
        .get_flattened_data()
    )
    bits = [
        pixels[row * (size + 1) + column] > pixels[row * (size + 1) + column + 1]
        for row in range(size)
        for column in range(size)
    ]
    return _hash_bits(bits)


def _average_hash(image: Image.Image, size: int = 8) -> str:
    pixels = list(
        ImageOps.grayscale(image)
        .resize((size, size), Image.Resampling.LANCZOS)
        .get_flattened_data()
    )
    mean = sum(pixels) / len(pixels)
    return _hash_bits([pixel >= mean for pixel in pixels])


def _color_histogram(image: Image.Image, bins_per_channel: int = 16) -> tuple[float, ...]:
    sample = image.resize((64, 64), Image.Resampling.BILINEAR)
    pixels_per_channel = sample.width * sample.height
    values: list[float] = []
    bucket_width = 256 // bins_per_channel
    for channel in sample.split():
        histogram = channel.histogram()
        for start in range(0, 256, bucket_width):
            count = sum(histogram[start : start + bucket_width])
            values.append(count / pixels_per_channel / 3.0)
    return tuple(round(value, 8) for value in values)


def _normalized_embedding(provider: ImageEmbeddingProvider, image: Image.Image) -> tuple[float, ...]:
    descriptor = provider.descriptor
    if not isinstance(descriptor, EmbeddingDescriptor):
        raise VisualCandidateError("embedding provider descriptor is invalid")
    raw_values = provider.embed(image.copy())
    if not isinstance(raw_values, Sequence):
        raise VisualCandidateError("embedding provider returned an invalid vector")
    if len(raw_values) != descriptor.dimensions:
        raise VisualCandidateError("embedding vector dimensions do not match the descriptor")
    try:
        values = tuple(float(value) for value in raw_values)
    except (TypeError, ValueError) as exc:
        raise VisualCandidateError("embedding vector contains non-numeric values") from exc
    if not values or any(not math.isfinite(value) for value in values):
        raise VisualCandidateError("embedding vector contains invalid values")
    norm = math.sqrt(sum(value * value for value in values))
    if norm <= 1e-12:
        raise VisualCandidateError("embedding vector has zero magnitude")
    return tuple(round(value / norm, 10) for value in values)


def fingerprint_image(
    data: bytes | bytearray | memoryview,
    *,
    content_type: str | None = None,
    embedding_provider: ImageEmbeddingProvider | None = None,
) -> VisualFingerprint:
    """Create a serializable fingerprint without storing the source image."""

    image, content_sha256, detected_type = _decode_image(data, content_type)
    embedding = None
    descriptor = None
    if embedding_provider is not None:
        descriptor = embedding_provider.descriptor
        embedding = _normalized_embedding(embedding_provider, image)
    return VisualFingerprint(
        schema_version=FINGERPRINT_SCHEMA_VERSION,
        content_sha256=content_sha256,
        content_type=detected_type,
        width=image.width,
        height=image.height,
        difference_hash=_difference_hash(image),
        average_hash=_average_hash(image),
        color_histogram=_color_histogram(image),
        embedding=embedding,
        embedding_descriptor=descriptor,
    )


def _hash_similarity(left: str, right: str) -> float:
    if len(left) != len(right):
        return 0.0
    bits = len(left) * 4
    distance = (int(left, 16) ^ int(right, 16)).bit_count()
    return max(0.0, 1.0 - distance / bits)


def _histogram_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    # Both RGB histograms have total mass one, so L1 distance is at most two.
    distance = sum(abs(a - b) for a, b in zip(left, right, strict=True))
    return max(0.0, min(1.0, 1.0 - distance / 2.0))


def _embedding_similarity(left: VisualFingerprint, right: VisualFingerprint) -> float | None:
    if left.embedding is None or right.embedding is None:
        return None
    if left.embedding_descriptor is None or right.embedding_descriptor is None:
        return None
    if left.embedding_descriptor.identity != right.embedding_descriptor.identity:
        return None
    if len(left.embedding) != len(right.embedding):
        return None
    cosine = sum(a * b for a, b in zip(left.embedding, right.embedding, strict=True))
    return max(0.0, min(1.0, (cosine + 1.0) / 2.0))


def _score_fingerprints(query: VisualFingerprint, indexed: VisualFingerprint) -> tuple[float, dict[str, Any]]:
    difference = _hash_similarity(query.difference_hash, indexed.difference_hash)
    average = _hash_similarity(query.average_hash, indexed.average_hash)
    color = _histogram_similarity(query.color_histogram, indexed.color_histogram)
    embedding = _embedding_similarity(query, indexed)

    if embedding is None:
        score = difference * 0.55 + average * 0.15 + color * 0.30
        scoring_profile = "deterministic-v1"
    else:
        score = difference * 0.25 + average * 0.05 + color * 0.15 + embedding * 0.55
        scoring_profile = "deterministic-plus-embedding-v1"

    evidence: dict[str, Any] = {
        "scoring_profile": scoring_profile,
        "difference_hash_similarity": round(difference, 6),
        "average_hash_similarity": round(average, 6),
        "color_histogram_similarity": round(color, 6),
        "content_hash_equal": query.content_sha256 == indexed.content_sha256,
        "interpretation": "visual_candidate_not_exact_sku",
    }
    if embedding is not None and query.embedding_descriptor is not None:
        evidence["embedding_similarity"] = round(embedding, 6)
        evidence["embedding_model"] = query.embedding_descriptor.to_dict()
    elif query.embedding is not None or indexed.embedding is not None:
        evidence["embedding_skipped"] = "missing_or_incompatible_model_evidence"
    return round(max(0.0, min(1.0, score)), 6), evidence


def rank_visual_candidates(
    query: VisualFingerprint,
    indexed_records: Sequence[IndexedVisual],
    *,
    category: str | None = None,
    include_cross_category: bool = False,
    minimum_score: float = 0.0,
    limit: int = 10,
) -> VisualSearchResult:
    """Pure, deterministic ranking over already-created fingerprints."""

    if not 1 <= int(limit) <= MAX_RESULTS:
        raise VisualCandidateError(f"limit must be between 1 and {MAX_RESULTS}")
    if not 0.0 <= float(minimum_score) <= 1.0:
        raise VisualCandidateError("minimum_score must be between zero and one")
    if len(indexed_records) > MAX_INDEX_RECORDS:
        raise VisualCandidateError("indexed_records exceed the safe ranking limit")
    requested_category = _validated_category(category) if category is not None else None
    candidates = []
    for record in tuple(indexed_records):
        if not isinstance(record, IndexedVisual):
            raise VisualCandidateError("indexed_records must contain IndexedVisual values")
        category_matches = requested_category is None or record.metadata.category == requested_category
        if not category_matches and not include_cross_category:
            continue
        score, evidence = _score_fingerprints(query, record.fingerprint)
        if not category_matches:
            score = round(score * 0.85, 6)
            evidence["category_penalty"] = 0.85
        evidence["category_match"] = category_matches
        if score < float(minimum_score):
            continue
        candidates.append(
            VisualCandidate(
                metadata=record.metadata,
                similarity_score=score,
                evidence=evidence,
            )
        )
    candidates.sort(key=lambda candidate: (-candidate.similarity_score, candidate.metadata.record_id))
    return VisualSearchResult(
        query_fingerprint=query,
        requested_category=requested_category,
        candidates=tuple(candidates[: int(limit)]),
    )


def generate_visual_candidates(
    image_data: bytes | bytearray | memoryview,
    indexed_records: Sequence[IndexedVisual],
    *,
    content_type: str | None = None,
    category: str | None = None,
    include_cross_category: bool = False,
    minimum_score: float = 0.0,
    limit: int = 10,
    embedding_provider: ImageEmbeddingProvider | None = None,
) -> VisualSearchResult:
    """Byte-in/result-out integration entry point with no disk or network I/O."""

    query = fingerprint_image(
        image_data,
        content_type=content_type,
        embedding_provider=embedding_provider,
    )
    return rank_visual_candidates(
        query,
        indexed_records,
        category=category,
        include_cross_category=include_cross_category,
        minimum_score=minimum_score,
        limit=limit,
    )


class LocalVisualCandidateIndex:
    """Thread-safe in-memory MVP index over bounded deterministic fingerprints."""

    def __init__(self, *, embedding_provider: ImageEmbeddingProvider | None = None) -> None:
        self._embedding_provider = embedding_provider
        self._records: dict[str, IndexedVisual] = {}
        self._lock = threading.RLock()

    def __len__(self) -> int:
        with self._lock:
            return len(self._records)

    def upsert(
        self,
        metadata: VisualIndexMetadata,
        image_data: bytes | bytearray | memoryview,
        *,
        content_type: str | None = None,
    ) -> IndexedVisual:
        fingerprint = fingerprint_image(
            image_data,
            content_type=content_type,
            embedding_provider=self._embedding_provider,
        )
        record = IndexedVisual(metadata=metadata, fingerprint=fingerprint)
        with self._lock:
            if metadata.record_id not in self._records and len(self._records) >= MAX_INDEX_RECORDS:
                raise VisualCandidateError("visual index record limit reached")
            self._records[metadata.record_id] = record
        return record

    def remove(self, record_id: str) -> bool:
        validated = _validated_identifier("record_id", record_id)
        assert validated is not None
        with self._lock:
            return self._records.pop(validated, None) is not None

    def documents(self) -> list[dict[str, Any]]:
        """Return a deterministic persistence snapshot; source image bytes are absent."""

        with self._lock:
            return [self._records[key].to_index_document() for key in sorted(self._records)]

    def search(
        self,
        image_data: bytes | bytearray | memoryview,
        *,
        content_type: str | None = None,
        category: str | None = None,
        include_cross_category: bool = False,
        minimum_score: float = 0.0,
        limit: int = 10,
    ) -> VisualSearchResult:
        with self._lock:
            records = tuple(self._records.values())
        return generate_visual_candidates(
            image_data,
            records,
            content_type=content_type,
            category=category,
            include_cross_category=include_cross_category,
            minimum_score=minimum_score,
            limit=limit,
            embedding_provider=self._embedding_provider,
        )
