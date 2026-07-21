"""Typed field model for privacy-preserving physical-store price evidence."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EvidenceSourceType(str, Enum):
    SHELF_LABEL = "shelf_label"
    RECEIPT = "receipt"
    BARCODE_PRODUCT_LABEL = "barcode_product_label"
    MANUAL_OBSERVATION = "manual_observation"


class ModerationStatus(str, Enum):
    PENDING = "pending"
    AWAITING_SECOND_EVIDENCE = "awaiting_second_evidence"
    CORROBORATED = "corroborated"
    PRICE_CONFLICT = "price_conflict"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class CaptureLocation(BaseModel):
    """Ephemeral device location input; exact coordinates are never persisted."""

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class PhysicalPriceEvidenceInput(BaseModel):
    """Validated input before privacy filtering and persistence."""

    model_config = ConfigDict(str_strip_whitespace=True, use_enum_values=True)

    product_id: str = Field(min_length=1, max_length=120)
    variant_id: str | None = Field(default=None, max_length=120)
    store_id: str = Field(min_length=1, max_length=120)
    store_name: str = Field(min_length=1, max_length=180)
    branch_name: str | None = Field(default=None, max_length=180)
    price_minor: int = Field(gt=0, le=1_000_000_000)
    currency: str = Field(default="TRY", pattern=r"^[A-Z]{3}$")
    observed_at: datetime
    source_type: EvidenceSourceType
    evidence_confidence: float = Field(ge=0, le=1)
    confidence_components: dict[str, float] = Field(default_factory=dict)
    identity_evidence: dict[str, str] = Field(default_factory=dict)
    raw_ocr_text: str | None = Field(default=None, max_length=20_000)
    content_sha256: str | None = Field(default=None, pattern=r"^[a-fA-F0-9]{64}$")
    submitter_reference: str | None = Field(default=None, max_length=240)
    capture_session_reference: str | None = Field(default=None, max_length=240)
    location: CaptureLocation | None = None
    retain_coarse_location: bool = False
    retain_raw_image: bool = False
    raw_image_ttl_hours: int = Field(default=24, ge=1, le=168)

    @field_validator("observed_at")
    @classmethod
    def validate_observed_at(cls, value):
        if value.tzinfo is None:
            raise ValueError("observed_at timezone bilgisi icermeli")
        normalized = value.astimezone(UTC)
        now = datetime.now(UTC)
        if normalized > now + timedelta(minutes=5):
            raise ValueError("observed_at gelecekte olamaz")
        if normalized < now - timedelta(days=30):
            raise ValueError("fiziksel fiyat kaniti en fazla 30 gunluk olabilir")
        return normalized

    @field_validator("confidence_components")
    @classmethod
    def validate_confidence_components(cls, value):
        cleaned = {}
        for key, score in value.items():
            text = str(key).strip()[:80]
            number = float(score)
            if not 0 <= number <= 1:
                raise ValueError("confidence_components 0 ile 1 arasinda olmali")
            if text:
                cleaned[text] = round(number, 4)
        return cleaned


class CorroborationResult(BaseModel):
    """Explainable result of the two-independent-evidence gate."""

    model_config = ConfigDict(use_enum_values=True)

    status: ModerationStatus
    eligible_for_moderation: bool
    eligible_for_total_cost: bool = False
    verified_price_minor: int | None = None
    currency: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    independent_evidence_count: int = 0
    combined_confidence: float = 0.0
    reasons: list[str] = Field(default_factory=list)

