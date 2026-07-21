from copy import deepcopy
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from physical_price_evidence_model import PhysicalPriceEvidenceInput
from physical_price_evidence_service import (
    build_evidence_document,
    create_physical_price_evidence,
    ensure_physical_evidence_indexes,
    evaluate_two_evidence_threshold,
    list_physical_price_evidence,
    moderate_physical_price_evidence,
    physical_price_projection,
    purge_expired_raw_assets,
    redact_personal_data,
)
from pydantic import ValidationError


def payload(**overrides):
    base = {
        "product_id": "product-jr5220",
        "variant_id": "jr5220-green-42",
        "store_id": "store-ankara-1",
        "store_name": "Ornek Spor",
        "branch_name": "Ankara",
        "price_minor": 439_900,
        "currency": "TRY",
        "observed_at": datetime.now(UTC) - timedelta(minutes=10),
        "source_type": "shelf_label",
        "evidence_confidence": 0.86,
        "confidence_components": {"ocr": 0.9, "price_region": 0.82},
        "identity_evidence": {"product_code": "JR5220", "gtin": "4067904494690"},
        "content_sha256": "a" * 64,
        "submitter_reference": "family-user-1",
        "capture_session_reference": "session-1",
    }
    base.update(overrides)
    return base


def _get_nested(document, path):
    value = document
    for part in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _set_nested(document, path, value):
    target = document
    parts = path.split(".")
    for part in parts[:-1]:
        target = target.setdefault(part, {})
    target[parts[-1]] = value


def _unset_nested(document, path):
    target = document
    parts = path.split(".")
    for part in parts[:-1]:
        target = target.get(part, {})
    target.pop(parts[-1], None)


def _matches(document, query):
    for path, expected in query.items():
        actual = _get_nested(document, path)
        if isinstance(expected, dict) and "$in" in expected:
            if actual not in expected["$in"]:
                return False
        elif isinstance(expected, dict) and "$lte" in expected:
            if actual is None or actual > expected["$lte"]:
                return False
        elif actual != expected:
            return False
    return True


class Cursor:
    def __init__(self, rows):
        self.rows = rows

    def sort(self, path, direction):
        self.rows.sort(key=lambda item: _get_nested(item, path), reverse=direction < 0)
        return self

    async def to_list(self, limit):
        return [deepcopy(item) for item in self.rows[:limit]]


class Collection:
    def __init__(self):
        self.rows = []
        self.indexes = []

    async def insert_one(self, document):
        self.rows.append(deepcopy(document))

    def find(self, query, _projection=None):
        return Cursor([item for item in self.rows if _matches(item, query)])

    async def update_many(self, query, update):
        for item in self.rows:
            if not _matches(item, query):
                continue
            for path, value in (update.get("$set") or {}).items():
                _set_nested(item, path, value)
            for path in (update.get("$unset") or {}):
                _unset_nested(item, path)

    async def delete_one(self, query):
        self.rows = [item for item in self.rows if not _matches(item, query)]

    async def delete_many(self, query):
        self.rows = [item for item in self.rows if not _matches(item, query)]

    async def create_index(self, fields, **options):
        self.indexes.append((fields, options))


def fake_db():
    return SimpleNamespace(
        physical_price_evidence=Collection(),
        physical_price_raw_assets=Collection(),
    )


def test_input_requires_timezone_and_rejects_future_capture():
    with pytest.raises(ValidationError):
        PhysicalPriceEvidenceInput(**payload(observed_at=datetime.now()))
    with pytest.raises(ValidationError):
        PhysicalPriceEvidenceInput(
            **payload(observed_at=datetime.now(UTC) + timedelta(minutes=10))
        )


def test_personal_data_is_masked_but_gtin_is_preserved():
    text = (
        "Müşteri: Ayşe Test\n"
        "Telefon: 0532 123 45 67\n"
        "E-posta: ayse@example.com\n"
        "TCKN 10000000146\n"
        "Kart 4111 1111 1111 1111\n"
        "Barkod 4067904494690"
    )

    redacted = redact_personal_data(text)

    assert "Ayşe Test" not in redacted
    assert "0532 123 45 67" not in redacted
    assert "ayse@example.com" not in redacted
    assert "10000000146" not in redacted
    assert "4111 1111 1111 1111" not in redacted
    assert "4067904494690" in redacted


def test_photo_and_exact_location_are_not_persisted_by_default():
    document, raw_asset = build_evidence_document(
        payload(
            raw_ocr_text="Müşteri: Test Kişi\nFiyat 4.399 TL",
            location={"latitude": 39.925533, "longitude": 32.866287},
        ),
        hash_key="test-secret",
        raw_image_bytes=b"private-photo",
    )

    assert raw_asset is None
    assert document["privacy"]["raw_image_retained"] is False
    assert document["privacy"]["raw_image_policy"] == "transient_not_persisted"
    assert document["privacy"]["coarse_location"] is None
    assert document["privacy"]["exact_location_retained"] is False
    assert b"private-photo" not in repr(document).encode()
    assert "Test Kişi" not in document["sanitized_ocr_text"]


def test_opt_in_raw_photo_has_a_hard_capped_ttl_and_separate_asset():
    fixed_now = datetime.now(UTC)
    document, raw_asset = build_evidence_document(
        payload(retain_raw_image=True, raw_image_ttl_hours=168),
        hash_key="test-secret",
        raw_image_bytes=b"temporary-photo",
        now=fixed_now,
    )

    assert raw_asset["expires_at"] == fixed_now + timedelta(hours=168)
    assert raw_asset["retention_policy"] == "hard_delete_at_ttl"
    assert document["privacy"]["raw_asset_id"] == raw_asset["id"]
    assert document["pricing_use"]["eligible_for_total_cost"] is False
    assert "content" not in document


def test_same_photo_or_same_submitter_and_source_does_not_satisfy_two_evidence_gate():
    first, _ = build_evidence_document(payload(), hash_key="secret")
    second, _ = build_evidence_document(
        payload(content_sha256="b" * 64, capture_session_reference="session-2"),
        hash_key="secret",
    )

    result = evaluate_two_evidence_threshold([first, second])

    assert result.status == "awaiting_second_evidence"
    assert result.eligible_for_moderation is False
    assert result.eligible_for_total_cost is False


def test_shelf_label_and_receipt_can_corroborate_for_same_user_but_not_total_cost():
    first, _ = build_evidence_document(payload(), hash_key="secret")
    second, _ = build_evidence_document(
        payload(
            source_type="receipt",
            price_minor=440_000,
            content_sha256="b" * 64,
            capture_session_reference="session-2",
            evidence_confidence=0.84,
        ),
        hash_key="secret",
    )

    result = evaluate_two_evidence_threshold([first, second])
    projection = physical_price_projection(result)

    assert result.status == "corroborated"
    assert result.eligible_for_moderation is True
    assert result.verified_price_minor == 439_950
    assert result.combined_confidence >= 0.9
    assert projection["eligible_for_total_cost"] is False
    assert projection["separate_from_online_offer"] is True


def test_two_independent_prices_outside_tolerance_require_review_as_conflict():
    first, _ = build_evidence_document(payload(price_minor=400_000), hash_key="secret")
    second, _ = build_evidence_document(
        payload(
            source_type="receipt",
            price_minor=500_000,
            content_sha256="b" * 64,
            capture_session_reference="session-2",
        ),
        hash_key="secret",
    )

    result = evaluate_two_evidence_threshold([first, second])

    assert result.status == "price_conflict"
    assert result.eligible_for_moderation is False
    assert result.verified_price_minor is None


def test_gate_checks_every_pair_and_selects_strongest_compatible_evidence():
    conflicting, _ = build_evidence_document(
        payload(
            price_minor=700_000,
            source_type="manual_observation",
            content_sha256="c" * 64,
            submitter_reference="family-user-3",
        ),
        hash_key="secret",
    )
    first, _ = build_evidence_document(payload(), hash_key="secret")
    second, _ = build_evidence_document(
        payload(
            source_type="receipt",
            price_minor=440_000,
            content_sha256="b" * 64,
            capture_session_reference="session-2",
        ),
        hash_key="secret",
    )

    result = evaluate_two_evidence_threshold([conflicting, first, second])

    assert result.status == "corroborated"
    assert set(result.evidence_ids) == {first["id"], second["id"]}


def test_anchor_prevents_a_new_conflict_from_reusing_an_older_matching_pair():
    first, _ = build_evidence_document(payload(), hash_key="secret")
    second, _ = build_evidence_document(
        payload(
            source_type="receipt",
            price_minor=440_000,
            content_sha256="b" * 64,
            capture_session_reference="session-2",
        ),
        hash_key="secret",
    )
    newest, _ = build_evidence_document(
        payload(
            source_type="manual_observation",
            price_minor=700_000,
            content_sha256="c" * 64,
            submitter_reference="family-user-3",
        ),
        hash_key="secret",
    )

    result = evaluate_two_evidence_threshold(
        [first, second, newest], anchor_evidence_id=newest["id"]
    )

    assert result.status == "price_conflict"
    assert newest["id"] in result.evidence_ids


@pytest.mark.asyncio
async def test_create_list_and_moderate_contract_requires_corroboration():
    db = fake_db()
    first = await create_physical_price_evidence(
        db, payload(), hash_key="secret", now=datetime.now(UTC)
    )
    assert first["corroboration"]["status"] == "awaiting_second_evidence"

    with pytest.raises(ValueError, match="iki bagimsiz"):
        await moderate_physical_price_evidence(
            db,
            evidence_ids=[first["evidence"]["id"]],
            decision="approved",
            moderator_reference="admin-1",
            hash_key="secret",
        )

    second = await create_physical_price_evidence(
        db,
        payload(
            source_type="receipt",
            content_sha256="b" * 64,
            capture_session_reference="session-2",
            price_minor=440_000,
        ),
        hash_key="secret",
        now=datetime.now(UTC),
    )
    assert second["corroboration"]["status"] == "corroborated"
    rows = await list_physical_price_evidence(db, product_id="product-jr5220")
    result = await moderate_physical_price_evidence(
        db,
        evidence_ids=[item["id"] for item in rows],
        decision="approved",
        moderator_reference="admin-1",
        hash_key="secret",
        note="Onaylayan: admin@example.com",
    )

    assert result["status"] == "approved"
    assert result["eligible_for_total_cost"] is False
    assert "admin-1" not in result["moderator_hash"]
    assert all(item["pricing_use"]["eligible_for_total_cost"] is False for item in db.physical_price_evidence.rows)


@pytest.mark.asyncio
async def test_unresolved_variant_does_not_borrow_evidence_from_known_variant():
    db = fake_db()
    await create_physical_price_evidence(
        db,
        payload(),
        hash_key="secret",
        now=datetime.now(UTC),
    )

    unresolved = await create_physical_price_evidence(
        db,
        payload(
            variant_id=None,
            source_type="receipt",
            content_sha256="b" * 64,
            capture_session_reference="session-2",
        ),
        hash_key="secret",
        now=datetime.now(UTC),
    )

    assert unresolved["corroboration"]["status"] == "awaiting_second_evidence"


@pytest.mark.asyncio
async def test_expired_raw_assets_are_hard_deleted_and_evidence_is_sanitized():
    db = fake_db()
    now = datetime.now(UTC)
    db.physical_price_raw_assets.rows.append(
        {"id": "asset-expired", "content": b"private", "expires_at": now - timedelta(seconds=1)}
    )
    db.physical_price_evidence.rows.append(
        {
            "id": "e1",
            "privacy": {
                "raw_asset_id": "asset-expired",
                "raw_image_retained": True,
                "raw_image_expires_at": now - timedelta(seconds=1),
            },
            "retention": {"raw_asset_hard_delete_at": now - timedelta(seconds=1)},
        }
    )

    deleted = await purge_expired_raw_assets(db, now=now)

    assert deleted == 1
    assert db.physical_price_raw_assets.rows == []
    privacy = db.physical_price_evidence.rows[0]["privacy"]
    assert privacy["raw_image_retained"] is False
    assert privacy["raw_image_policy"] == "ttl_hard_deleted"
    assert "raw_asset_id" not in privacy


@pytest.mark.asyncio
async def test_expired_reference_is_scrubbed_after_mongo_ttl_already_deleted_asset():
    db = fake_db()
    now = datetime.now(UTC)
    db.physical_price_evidence.rows.append(
        {
            "id": "e1",
            "privacy": {
                "raw_asset_id": "asset-already-deleted",
                "raw_image_retained": True,
                "raw_image_expires_at": now - timedelta(seconds=1),
            },
            "retention": {"raw_asset_hard_delete_at": now - timedelta(seconds=1)},
        }
    )

    deleted = await purge_expired_raw_assets(db, now=now)

    assert deleted == 1
    privacy = db.physical_price_evidence.rows[0]["privacy"]
    assert privacy["raw_image_retained"] is False
    assert "raw_asset_id" not in privacy


@pytest.mark.asyncio
async def test_indexes_keep_raw_asset_ttl_separate_from_sanitized_evidence():
    db = fake_db()

    await ensure_physical_evidence_indexes(db)

    raw_options = [options for _fields, options in db.physical_price_raw_assets.indexes]
    evidence_options = [options for _fields, options in db.physical_price_evidence.indexes]
    assert any(item.get("expireAfterSeconds") == 0 for item in raw_options)
    assert all("expireAfterSeconds" not in item for item in evidence_options)
