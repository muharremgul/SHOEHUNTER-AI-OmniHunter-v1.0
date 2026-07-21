"""Privacy-first services for shelf-label and receipt price observations.

Physical observations are deliberately isolated from online listing prices and
``compute_total_cost``.  Two independent, recent, price-consistent pieces of
evidence may advance to moderation, but never alter payable-cost calculations
automatically.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from statistics import median
from typing import Any

from physical_price_evidence_model import (
    CorroborationResult,
    ModerationStatus,
    PhysicalPriceEvidenceInput,
)

RAW_IMAGE_MAX_BYTES = 12 * 1024 * 1024
DEFAULT_RAW_IMAGE_TTL_HOURS = 24
MAX_RAW_IMAGE_TTL_HOURS = 168
EVIDENCE_WINDOW_HOURS = 72
MIN_EVIDENCE_CONFIDENCE = 0.70
MIN_COMBINED_CONFIDENCE = 0.90
MIN_INDEPENDENT_EVIDENCE = 2
PRICE_TOLERANCE_RATIO = 0.02
PRICE_TOLERANCE_FLOOR_MINOR = 100
SANITIZED_RECORD_REVIEW_DAYS = 90

_EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
_PHONE_RE = re.compile(r"(?<!\d)(?:(?:\+?90|0)[\s.-]?)?5\d{2}(?:[\s.-]?\d{3})(?:[\s.-]?\d{2}){2}(?!\d)")
_IBAN_RE = re.compile(r"(?i)\bTR\s*(?:\d[\s-]*){24}\b")
_CARD_RE = re.compile(r"(?<!\d)(?:\d[ -]?){15}\d(?!\d)")
_LABELED_PII_RE = re.compile(
    r"(?im)^(\s*(?:ad\s*soyad|musteri|müşteri|customer|telefon|phone|adres|address|e-?posta|email)\s*[:=-]).*$"
)
_ALLOWED_IDENTITY_KEYS = {"barcode", "ean", "gtin", "model_code", "product_code", "sku", "upc"}


def utcnow():
    return datetime.now(UTC)


def _is_valid_tckn(value: str) -> bool:
    if len(value) != 11 or not value.isdigit() or value[0] == "0":
        return False
    digits = [int(item) for item in value]
    tenth = ((sum(digits[0:9:2]) * 7) - sum(digits[1:8:2])) % 10
    eleventh = sum(digits[:10]) % 10
    return digits[9] == tenth and digits[10] == eleventh


def redact_personal_data(text: str | None) -> str | None:
    """Mask common receipt PII while leaving 8/12/13/14 digit GTINs intact."""

    if not text:
        return None
    output = _LABELED_PII_RE.sub(r"\1 [MASKED]", str(text))
    output = _EMAIL_RE.sub("[MASKED_EMAIL]", output)
    output = _PHONE_RE.sub("[MASKED_PHONE]", output)
    output = _IBAN_RE.sub("[MASKED_IBAN]", output)
    output = _CARD_RE.sub("[MASKED_CARD]", output)

    def mask_tckn(match):
        value = match.group(0)
        return "[MASKED_TCKN]" if _is_valid_tckn(value) else value

    return re.sub(r"(?<!\d)\d{11}(?!\d)", mask_tckn, output)[:20_000]


def _hash_reference(value: str | None, hash_key: str | bytes | None, purpose: str) -> str | None:
    if not value:
        return None
    if not hash_key:
        raise ValueError("Kisisel referanslari guvenle ozetlemek icin hash_key gerekli")
    key = hash_key.encode("utf-8") if isinstance(hash_key, str) else hash_key
    return hmac.new(key, f"{purpose}:{value}".encode(), hashlib.sha256).hexdigest()


def _clean_identity_evidence(values: dict[str, Any]) -> dict[str, str]:
    output = {}
    for key, value in (values or {}).items():
        normalized_key = str(key).strip().casefold()
        normalized_value = str(value or "").strip()
        if normalized_key in _ALLOWED_IDENTITY_KEYS and normalized_value:
            output[normalized_key] = normalized_value[:120]
    return output


def _coarse_location(payload: PhysicalPriceEvidenceInput) -> dict[str, Any] | None:
    if not payload.location or not payload.retain_coarse_location:
        return None
    # Two decimals is intentionally approximate (roughly kilometre-scale) and
    # exact device coordinates are discarded immediately after this function.
    return {
        "latitude": round(payload.location.latitude, 2),
        "longitude": round(payload.location.longitude, 2),
        "precision": "coarse_2_decimal",
    }


def build_evidence_document(
    value: PhysicalPriceEvidenceInput | dict[str, Any],
    *,
    hash_key: str | bytes | None = None,
    raw_image_bytes: bytes | None = None,
    now: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Build a sanitized evidence record and optional short-lived raw asset."""

    payload = value if isinstance(value, PhysicalPriceEvidenceInput) else PhysicalPriceEvidenceInput(**value)
    now = (now or utcnow()).astimezone(UTC)
    if raw_image_bytes is not None and len(raw_image_bytes) > RAW_IMAGE_MAX_BYTES:
        raise ValueError("Ham gorsel 12 MB sinirini asti")

    content_fingerprint = payload.content_sha256
    if raw_image_bytes is not None:
        content_fingerprint = hashlib.sha256(raw_image_bytes).hexdigest()

    evidence_id = str(uuid.uuid4())
    raw_asset = None
    raw_asset_id = None
    raw_expires_at = None
    if raw_image_bytes is not None and payload.retain_raw_image:
        ttl_hours = min(MAX_RAW_IMAGE_TTL_HOURS, payload.raw_image_ttl_hours or DEFAULT_RAW_IMAGE_TTL_HOURS)
        raw_asset_id = str(uuid.uuid4())
        raw_expires_at = now + timedelta(hours=ttl_hours)
        raw_asset = {
            "id": raw_asset_id,
            "evidence_id": evidence_id,
            "content": bytes(raw_image_bytes),
            "content_sha256": content_fingerprint,
            "created_at": now,
            "expires_at": raw_expires_at,
            "retention_policy": "hard_delete_at_ttl",
        }

    document = {
        "id": evidence_id,
        "schema_version": 1,
        "product_id": payload.product_id,
        "variant_id": payload.variant_id,
        "variant_resolution": "resolved" if payload.variant_id else "unresolved",
        "store": {
            "id": payload.store_id,
            "name": payload.store_name,
            "branch_name": payload.branch_name,
        },
        "observed_price": {"amount_minor": payload.price_minor, "currency": payload.currency},
        "observed_at": payload.observed_at,
        "source_type": payload.source_type,
        "evidence_confidence": round(payload.evidence_confidence, 4),
        "confidence_components": payload.confidence_components,
        "identity_evidence": _clean_identity_evidence(payload.identity_evidence),
        "sanitized_ocr_text": redact_personal_data(payload.raw_ocr_text),
        "independence": {
            "content_fingerprint": content_fingerprint,
            "submitter_hash": _hash_reference(payload.submitter_reference, hash_key, "submitter"),
            "capture_session_hash": _hash_reference(
                payload.capture_session_reference, hash_key, "capture_session"
            ),
        },
        "moderation": {
            "status": ModerationStatus.PENDING.value,
            "reason_codes": ["requires_two_independent_evidence"],
            "updated_at": now,
        },
        "privacy": {
            "raw_image_retained": bool(raw_asset),
            "raw_asset_id": raw_asset_id,
            "raw_image_expires_at": raw_expires_at,
            "raw_image_policy": "opt_in_ttl" if raw_asset else "transient_not_persisted",
            "coarse_location": _coarse_location(payload),
            "exact_location_retained": False,
            "ocr_personal_data_masked": True,
        },
        "pricing_use": {
            "scope": "physical_store_evidence_only",
            "eligible_for_total_cost": False,
            "eligible_for_online_listing_price": False,
            "reason": "Fiziksel magaza kaniti cevrim ici siparisin odenebilir toplam maliyeti degildir",
        },
        "retention": {
            "sanitized_record_review_at": now + timedelta(days=SANITIZED_RECORD_REVIEW_DAYS),
            "raw_asset_hard_delete_at": raw_expires_at,
        },
        "created_at": now,
        "updated_at": now,
    }
    return document, raw_asset


async def ensure_physical_evidence_indexes(db):
    await db.physical_price_evidence.create_index(
        [("id", 1)], unique=True, name="uq_physical_evidence_id"
    )
    await db.physical_price_evidence.create_index(
        [("product_id", 1), ("variant_id", 1), ("store.id", 1), ("observed_at", -1)],
        name="ix_physical_evidence_product_store_time",
    )
    await db.physical_price_evidence.create_index(
        [("moderation.status", 1), ("moderation.updated_at", -1)],
        name="ix_physical_evidence_moderation_queue",
    )
    await db.physical_price_evidence.create_index(
        [("privacy.raw_image_expires_at", 1)],
        name="ix_physical_evidence_raw_expiry_reconciliation",
    )
    await db.physical_price_evidence.create_index(
        [("retention.sanitized_record_review_at", 1)],
        name="ix_physical_evidence_retention_review",
    )
    await db.physical_price_raw_assets.create_index(
        [("expires_at", 1)], expireAfterSeconds=0, name="ttl_physical_raw_assets"
    )
    await db.physical_price_raw_assets.create_index(
        [("id", 1)], unique=True, name="uq_physical_raw_asset_id"
    )
    await db.physical_price_raw_assets.create_index(
        [("evidence_id", 1)], name="ix_physical_raw_asset_evidence_id"
    )


async def save_physical_price_evidence(
    db,
    value: PhysicalPriceEvidenceInput | dict[str, Any],
    *,
    hash_key: str | bytes | None = None,
    raw_image_bytes: bytes | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    document, raw_asset = build_evidence_document(
        value, hash_key=hash_key, raw_image_bytes=raw_image_bytes, now=now
    )
    if raw_asset:
        await db.physical_price_raw_assets.insert_one(dict(raw_asset))
    try:
        await db.physical_price_evidence.insert_one(dict(document))
    except Exception:
        if raw_asset:
            await db.physical_price_raw_assets.delete_one({"id": raw_asset["id"]})
        raise
    return document


def validate_physical_price_evidence(
    value: PhysicalPriceEvidenceInput | dict[str, Any],
) -> PhysicalPriceEvidenceInput:
    """Validate the public create contract without retaining input data."""

    return value if isinstance(value, PhysicalPriceEvidenceInput) else PhysicalPriceEvidenceInput(**value)


async def list_physical_price_evidence(
    db,
    *,
    product_id: str,
    variant_id: str | None = None,
    store_id: str | None = None,
    moderation_status: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """List sanitized evidence metadata; raw image bytes are never joined."""

    if not str(product_id or "").strip():
        raise ValueError("product_id gerekli")
    query: dict[str, Any] = {"product_id": str(product_id).strip()}
    if variant_id is not None:
        query["variant_id"] = variant_id
    if store_id is not None:
        query["store.id"] = store_id
    if moderation_status is not None:
        query["moderation.status"] = moderation_status
    return await db.physical_price_evidence.find(query, {"_id": 0}).sort(
        "observed_at", -1
    ).to_list(max(1, min(200, int(limit))))


async def create_physical_price_evidence(
    db,
    value: PhysicalPriceEvidenceInput | dict[str, Any],
    *,
    hash_key: str | bytes | None = None,
    raw_image_bytes: bytes | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Create evidence, then run the explainable two-evidence gate."""

    payload = validate_physical_price_evidence(value)
    document = await save_physical_price_evidence(
        db,
        payload,
        hash_key=hash_key,
        raw_image_bytes=raw_image_bytes,
        now=now,
    )
    recent = await list_physical_price_evidence(
        db,
        product_id=payload.product_id,
        variant_id=payload.variant_id,
        store_id=payload.store_id,
        limit=100,
    )
    # ``variant_id=None`` means no filter in the public list contract. Creation
    # must still compare an unresolved observation only with other unresolved
    # observations, never with a known variant returned by that broad query.
    recent = [item for item in recent if item.get("variant_id") == payload.variant_id]
    result = evaluate_two_evidence_threshold(
        recent,
        now=now,
        anchor_evidence_id=document["id"],
    )
    status = result.status
    reason_codes = result.reasons
    await db.physical_price_evidence.update_many(
        {"id": {"$in": result.evidence_ids or [document["id"]]}},
        {
            "$set": {
                "moderation.status": status,
                "moderation.reason_codes": reason_codes,
                "moderation.updated_at": (now or utcnow()).astimezone(UTC),
                "updated_at": (now or utcnow()).astimezone(UTC),
            }
        },
    )
    document["moderation"] = {
        **document["moderation"],
        "status": status,
        "reason_codes": reason_codes,
        "updated_at": (now or utcnow()).astimezone(UTC),
    }
    return {"evidence": document, "corroboration": result.model_dump(mode="json")}


def _as_utc(value):
    if not isinstance(value, datetime):
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _independent(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_meta = left.get("independence") or {}
    right_meta = right.get("independence") or {}
    left_fingerprint = left_meta.get("content_fingerprint") or left.get("id")
    right_fingerprint = right_meta.get("content_fingerprint") or right.get("id")
    if not left_fingerprint or left_fingerprint == right_fingerprint:
        return False
    left_submitter = left_meta.get("submitter_hash")
    right_submitter = right_meta.get("submitter_hash")
    if left_submitter and right_submitter and left_submitter != right_submitter:
        return True
    return left.get("source_type") != right.get("source_type")


def evaluate_two_evidence_threshold(
    records: Iterable[dict[str, Any]],
    *,
    now: datetime | None = None,
    anchor_evidence_id: str | None = None,
) -> CorroborationResult:
    """Require two independent, recent, confident, price-consistent records.

    ``anchor_evidence_id`` makes a create-time decision specific to the newly
    submitted record. Without an anchor (for moderation), every independent
    pair is considered and the strongest price-consistent pair is selected.
    """

    rows = list(records)
    now = (now or utcnow()).astimezone(UTC)
    if not rows:
        return CorroborationResult(
            status=ModerationStatus.AWAITING_SECOND_EVIDENCE,
            eligible_for_moderation=False,
            reasons=["no_evidence"],
        )

    first = next(
        (item for item in rows if str(item.get("id")) == str(anchor_evidence_id)),
        rows[0],
    )
    first_price = first.get("observed_price") or {}
    group_key = (
        first.get("product_id"),
        first.get("variant_id"),
        (first.get("store") or {}).get("id"),
        first_price.get("currency"),
    )
    eligible = []
    reasons = []
    for row in rows:
        moderation = (row.get("moderation") or {}).get("status")
        observed_at = _as_utc(row.get("observed_at"))
        price = row.get("observed_price") or {}
        row_key = (
            row.get("product_id"),
            row.get("variant_id"),
            (row.get("store") or {}).get("id"),
            price.get("currency"),
        )
        if row_key != group_key:
            reasons.append("group_mismatch_excluded")
            continue
        if moderation in {ModerationStatus.REJECTED.value, ModerationStatus.EXPIRED.value}:
            reasons.append("moderation_excluded")
            continue
        if not observed_at or now - observed_at > timedelta(hours=EVIDENCE_WINDOW_HOURS):
            reasons.append("stale_evidence_excluded")
            continue
        if float(row.get("evidence_confidence") or 0) < MIN_EVIDENCE_CONFIDENCE:
            reasons.append("low_confidence_excluded")
            continue
        if not isinstance(price.get("amount_minor"), int) or price["amount_minor"] <= 0:
            reasons.append("invalid_price_excluded")
            continue
        eligible.append(row)

    pairs = []
    for index, left in enumerate(eligible):
        for right in eligible[index + 1 :]:
            if anchor_evidence_id and str(anchor_evidence_id) not in {
                str(left.get("id")),
                str(right.get("id")),
            }:
                continue
            if _independent(left, right):
                pairs.append((left, right))
    if not pairs:
        return CorroborationResult(
            status=ModerationStatus.AWAITING_SECOND_EVIDENCE,
            eligible_for_moderation=False,
            evidence_ids=[str(item.get("id")) for item in eligible if item.get("id")],
            independent_evidence_count=min(1, len(eligible)),
            reasons=list(dict.fromkeys(reasons + ["two_independent_evidence_required"])),
        )

    compatible_pairs = []
    for pair in pairs:
        prices = [item["observed_price"]["amount_minor"] for item in pair]
        center = int(round(median(prices)))
        tolerance = max(PRICE_TOLERANCE_FLOOR_MINOR, round(center * PRICE_TOLERANCE_RATIO))
        if any(abs(price - center) > tolerance for price in prices):
            continue
        confidences = [float(item.get("evidence_confidence") or 0) for item in pair]
        combined = round(1 - ((1 - confidences[0]) * (1 - confidences[1])), 4)
        compatible_pairs.append((combined, center, tolerance, pair))

    if not compatible_pairs:
        pair = pairs[0]
        prices = [item["observed_price"]["amount_minor"] for item in pair]
        center = int(round(median(prices)))
        tolerance = max(PRICE_TOLERANCE_FLOOR_MINOR, round(center * PRICE_TOLERANCE_RATIO))
        return CorroborationResult(
            status=ModerationStatus.PRICE_CONFLICT,
            eligible_for_moderation=False,
            evidence_ids=[str(item.get("id")) for item in pair if item.get("id")],
            independent_evidence_count=MIN_INDEPENDENT_EVIDENCE,
            currency=group_key[3],
            reasons=["price_values_outside_tolerance", f"tolerance_minor={tolerance}"],
        )

    combined, center, _tolerance, pair = max(compatible_pairs, key=lambda item: item[0])
    if combined < MIN_COMBINED_CONFIDENCE:
        return CorroborationResult(
            status=ModerationStatus.AWAITING_SECOND_EVIDENCE,
            eligible_for_moderation=False,
            evidence_ids=[str(item.get("id")) for item in pair if item.get("id")],
            independent_evidence_count=MIN_INDEPENDENT_EVIDENCE,
            combined_confidence=combined,
            currency=group_key[3],
            reasons=["combined_confidence_below_threshold"],
        )

    return CorroborationResult(
        status=ModerationStatus.CORROBORATED,
        eligible_for_moderation=True,
        eligible_for_total_cost=False,
        verified_price_minor=center,
        currency=group_key[3],
        evidence_ids=[str(item.get("id")) for item in pair if item.get("id")],
        independent_evidence_count=MIN_INDEPENDENT_EVIDENCE,
        combined_confidence=combined,
        reasons=[
            "two_independent_evidence_matched",
            "price_values_within_tolerance",
            "manual_moderation_still_required",
            "excluded_from_online_total_cost",
        ],
    )


def physical_price_projection(result: CorroborationResult | dict[str, Any]) -> dict[str, Any]:
    value = result if isinstance(result, CorroborationResult) else CorroborationResult(**result)
    return {
        "source": "physical_store_evidence",
        "amount_minor": value.verified_price_minor,
        "currency": value.currency,
        "moderation_status": value.status,
        "evidence_count": value.independent_evidence_count,
        "confidence": value.combined_confidence,
        "eligible_for_total_cost": False,
        "separate_from_online_offer": True,
        "disclaimer": "Fiziksel magaza gozlemidir; cevrim ici siparis toplam maliyetine uygulanmaz.",
    }


async def moderate_physical_price_evidence(
    db,
    *,
    evidence_ids: list[str],
    decision: str,
    moderator_reference: str,
    hash_key: str | bytes,
    note: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Approve corroborated evidence or reject submitted evidence explicitly."""

    ids = list(dict.fromkeys(str(item).strip() for item in evidence_ids if str(item).strip()))
    if not ids:
        raise ValueError("En az bir evidence_id gerekli")
    if decision not in {ModerationStatus.APPROVED.value, ModerationStatus.REJECTED.value}:
        raise ValueError("decision approved veya rejected olmali")
    rows = await db.physical_price_evidence.find(
        {"id": {"$in": ids}}, {"_id": 0}
    ).to_list(200)
    if len(rows) != len(ids):
        raise ValueError("Bir veya daha fazla fiziksel fiyat kaniti bulunamadi")

    corroboration = evaluate_two_evidence_threshold(rows, now=now)
    if decision == ModerationStatus.APPROVED.value and not corroboration.eligible_for_moderation:
        raise ValueError("Onay icin iki bagimsiz ve fiyat-uyumlu kanit gerekli")

    timestamp = (now or utcnow()).astimezone(UTC)
    moderator_hash = _hash_reference(moderator_reference, hash_key, "moderator")
    safe_note = redact_personal_data(note)[:500] if note else None
    await db.physical_price_evidence.update_many(
        {"id": {"$in": ids}},
        {
            "$set": {
                "moderation.status": decision,
                "moderation.moderator_hash": moderator_hash,
                "moderation.note": safe_note,
                "moderation.updated_at": timestamp,
                "updated_at": timestamp,
                "pricing_use.eligible_for_total_cost": False,
                "pricing_use.eligible_for_online_listing_price": False,
            }
        },
    )
    return {
        "status": decision,
        "evidence_ids": ids,
        "moderator_hash": moderator_hash,
        "corroboration": corroboration.model_dump(mode="json"),
        "eligible_for_total_cost": False,
    }


async def purge_expired_raw_assets(db, *, now: datetime | None = None) -> int:
    """Delete expired photos and scrub references even if Mongo TTL ran first."""

    now = (now or utcnow()).astimezone(UTC)
    expired = await db.physical_price_raw_assets.find(
        {"expires_at": {"$lte": now}}, {"_id": 0, "id": 1}
    ).to_list(10_000)
    expired_references = await db.physical_price_evidence.find(
        {"privacy.raw_image_expires_at": {"$lte": now}},
        {"_id": 0, "privacy.raw_asset_id": 1},
    ).to_list(10_000)
    asset_ids = list(
        dict.fromkeys(
            [item["id"] for item in expired if item.get("id")]
            + [
                (item.get("privacy") or {}).get("raw_asset_id")
                for item in expired_references
                if (item.get("privacy") or {}).get("raw_asset_id")
            ]
        )
    )
    if not asset_ids:
        return 0
    await db.physical_price_raw_assets.delete_many({"expires_at": {"$lte": now}})
    await db.physical_price_evidence.update_many(
        {"privacy.raw_image_expires_at": {"$lte": now}},
        {
            "$set": {
                "privacy.raw_image_retained": False,
                "privacy.raw_image_deleted_at": now,
                "privacy.raw_image_policy": "ttl_hard_deleted",
                "updated_at": now,
            },
            "$unset": {
                "privacy.raw_asset_id": "",
                "privacy.raw_image_expires_at": "",
                "retention.raw_asset_hard_delete_at": "",
            },
        },
    )
    return len(asset_ids)
