import sys
from copy import deepcopy
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageStat

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import visual_candidates  # noqa: E402
from visual_candidates import (  # noqa: E402
    EmbeddingDescriptor,
    IndexedVisual,
    LocalVisualCandidateIndex,
    VisualCandidateError,
    VisualIndexMetadata,
    fingerprint_image,
    generate_visual_candidates,
    rank_visual_candidates,
)


def image_bytes(
    background: tuple[int, int, int],
    *,
    accent: tuple[int, int, int] = (255, 255, 255),
    image_format: str = "PNG",
) -> bytes:
    image = Image.new("RGB", (160, 120), background)
    draw = ImageDraw.Draw(image)
    draw.rectangle((18, 18, 72, 102), fill=accent)
    draw.polygon(((85, 15), (148, 60), (85, 105)), fill=(20, 20, 20))
    output = BytesIO()
    image.save(output, format=image_format, quality=92)
    return output.getvalue()


def metadata(
    record_id: str,
    *,
    category: str = "shoes",
    product_id: str | None = None,
) -> VisualIndexMetadata:
    return VisualIndexMetadata(
        record_id=record_id,
        canonical_product_id=product_id or f"product:{record_id}",
        category=category,
        source_name="catalog",
        source_item_id=f"item:{record_id}",
        display_name=f"Candidate {record_id}",
        variant_id=f"variant:{record_id}",
        brand="Example",
        model_code=record_id.upper(),
    )


def indexed(record_id: str, image: bytes, *, category: str = "shoes") -> IndexedVisual:
    return IndexedVisual(metadata(record_id, category=category), fingerprint_image(image, content_type="image/png"))


def test_fingerprint_is_deterministic_and_carries_content_evidence_without_source_bytes():
    data = image_bytes((210, 30, 40))

    first = fingerprint_image(data, content_type="image/png")
    second = fingerprint_image(data, content_type="image/png")
    document = first.to_dict()

    assert first == second
    assert first.content_sha256 == visual_candidates.hashlib.sha256(data).hexdigest()
    assert document["schema_version"] == "shoehunter.visual-fingerprint.v1"
    assert len(document["difference_hash"]) == 16
    assert len(document["average_hash"]) == 16
    assert len(document["color_histogram"]) == 48
    assert "image_bytes" not in document


def test_identical_content_is_still_only_a_visual_candidate_and_never_an_exact_sku_decision():
    data = image_bytes((210, 30, 40))
    record = indexed("red-shoe", data)

    result = generate_visual_candidates(data, [record], content_type="image/png", category="shoes")
    payload = result.to_dict()

    assert result.candidates[0].similarity_score == 1.0
    assert result.candidates[0].candidate_only is True
    assert result.candidates[0].exact_sku_decision is False
    assert result.candidates[0].evidence["content_hash_equal"] is True
    assert result.candidates[0].evidence["interpretation"] == "visual_candidate_not_exact_sku"
    assert payload["interpretation"] == "candidate_generation_only"
    assert payload["safety"]["exact_sku_decision_made"] is False
    assert payload["visual_candidates"][0]["exact_sku_decision"] is False


def test_deterministic_ranking_prefers_the_visually_closest_candidate():
    red_png = image_bytes((210, 30, 40))
    red_jpeg = image_bytes((210, 30, 40), image_format="JPEG")
    blue_png = image_bytes((25, 45, 220), accent=(250, 220, 20))
    records = [indexed("blue", blue_png), indexed("red", red_png)]

    result = generate_visual_candidates(red_jpeg, records, content_type="image/jpeg", category="shoes")

    assert [candidate.metadata.record_id for candidate in result.candidates] == ["red", "blue"]
    assert result.candidates[0].similarity_score > result.candidates[1].similarity_score
    assert result.candidates[0].evidence["scoring_profile"] == "deterministic-v1"


def test_category_filtering_is_safe_by_default_and_cross_category_is_explicit():
    data = image_bytes((30, 160, 80))
    records = [
        indexed("shoe", data, category="shoes"),
        indexed("jacket", data, category="outerwear"),
    ]
    query = fingerprint_image(data, content_type="image/png")

    filtered = rank_visual_candidates(query, records, category="shoes")
    cross_category = rank_visual_candidates(query, records, category="shoes", include_cross_category=True)

    assert [candidate.metadata.record_id for candidate in filtered.candidates] == ["shoe"]
    assert [candidate.metadata.record_id for candidate in cross_category.candidates] == ["shoe", "jacket"]
    assert cross_category.candidates[1].similarity_score == 0.85
    assert cross_category.candidates[1].evidence["category_match"] is False
    assert cross_category.candidates[1].evidence["category_penalty"] == 0.85


def test_model_code_hint_reranks_candidates_but_never_makes_an_exact_sku_decision():
    query_image = image_bytes((80, 80, 80))
    visually_close = indexed("OTHER100", query_image)
    code_match = indexed("JF2443", image_bytes((180, 30, 30)))
    query = fingerprint_image(query_image, content_type="image/png")

    result = rank_visual_candidates(
        query,
        [visually_close, code_match],
        category="shoes",
        model_code_hint="JF-2443",
    )

    assert result.candidates[0].metadata.record_id == "JF2443"
    assert result.candidates[0].evidence["model_code_hint_match"] is True
    assert result.candidates[0].evidence["identity_fusion"] == "user_or_ocr_hint_candidate_rerank"
    assert result.candidates[0].candidate_only is True
    assert result.candidates[0].exact_sku_decision is False


def test_index_document_has_a_bounded_metadata_contract_and_no_fetchable_locator():
    data = image_bytes((70, 80, 90))
    index = LocalVisualCandidateIndex()

    record = index.upsert(metadata("safe-record"), data, content_type="image/png")
    document = record.to_index_document()

    assert document["schema_version"] == "shoehunter.visual-index.v1"
    assert set(document["metadata"]) == {
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
    assert "url" not in document["metadata"]
    assert "path" not in document["metadata"]
    assert document == index.documents()[0]


def test_persisted_index_document_round_trips_through_strict_validation():
    data = image_bytes((70, 80, 90))
    original = IndexedVisual(metadata("persisted"), fingerprint_image(data, content_type="image/png"))
    mongo_document = original.to_index_document()
    mongo_document["_id"] = "mongo-envelope-is-allowed"

    restored = IndexedVisual.from_index_document(mongo_document)

    assert restored == original
    assert restored.to_index_document() == original.to_index_document()


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda doc: doc.update(schema_version="shoehunter.visual-index.v999"), "schema version"),
        (lambda doc: doc["metadata"].update(source_url="https://internal.example"), "metadata schema"),
        (lambda doc: doc["fingerprint"].update(width=100_000), "dimensions"),
        (lambda doc: doc["fingerprint"].update(color_histogram=[1.0]), "color_histogram"),
    ],
)
def test_persisted_index_document_rejects_unknown_schema_and_unbounded_features(mutation, message):
    original = IndexedVisual(
        metadata("persisted"),
        fingerprint_image(image_bytes((70, 80, 90)), content_type="image/png"),
    ).to_index_document()
    tampered = deepcopy(original)
    mutation(tampered)

    with pytest.raises(VisualCandidateError, match=message):
        IndexedVisual.from_index_document(tampered)


def test_metadata_rejects_url_or_path_shaped_identifiers():
    with pytest.raises(VisualCandidateError, match="source_item_id"):
        VisualIndexMetadata(
            record_id="unsafe",
            canonical_product_id="product:unsafe",
            category="shoes",
            source_name="catalog",
            source_item_id="https://internal.example/image.png",
            display_name="Unsafe URL",
        )

    with pytest.raises(VisualCandidateError, match="record_id"):
        metadata("../outside")


@pytest.mark.parametrize("unsafe_input", ["https://example.com/image.jpg", Path("image.jpg")])
def test_image_api_rejects_paths_and_urls_so_it_cannot_trigger_ssrf_or_file_reads(unsafe_input):
    with pytest.raises(VisualCandidateError, match="encoded bytes"):
        fingerprint_image(unsafe_input)  # type: ignore[arg-type]


def test_image_validation_rejects_size_content_type_and_invalid_bytes(monkeypatch):
    data = image_bytes((20, 30, 40))

    with pytest.raises(VisualCandidateError, match="does not match"):
        fingerprint_image(data, content_type="image/jpeg")
    with pytest.raises(VisualCandidateError, match="could not be decoded"):
        fingerprint_image(b"not-an-image", content_type="image/png")

    monkeypatch.setattr(visual_candidates, "MAX_IMAGE_BYTES", len(data) - 1)
    with pytest.raises(VisualCandidateError, match="byte limit"):
        fingerprint_image(data, content_type="image/png")


def test_image_validation_checks_dimensions_before_feature_extraction(monkeypatch):
    data = image_bytes((20, 30, 40))
    monkeypatch.setattr(visual_candidates, "MAX_IMAGE_PIXELS", 100)

    with pytest.raises(VisualCandidateError, match="dimensions"):
        fingerprint_image(data, content_type="image/png")


class LocalMeanColorEmbedding:
    descriptor = EmbeddingDescriptor(
        provider="testprovider",
        model_name="mean-color",
        weights_id="fixture-v1",
        weights_sha256="1" * 64,
        license_id="test-only",
        dimensions=3,
    )

    def embed(self, image: Image.Image):
        return ImageStat.Stat(image).mean


def test_optional_preloaded_embedding_adds_auditable_evidence_without_changing_candidate_semantics():
    provider = LocalMeanColorEmbedding()
    red = image_bytes((210, 30, 40))
    blue = image_bytes((25, 45, 220))
    index = LocalVisualCandidateIndex(embedding_provider=provider)
    index.upsert(metadata("red"), red, content_type="image/png")
    index.upsert(metadata("blue"), blue, content_type="image/png")

    result = index.search(red, content_type="image/png", category="shoes")
    winner = result.candidates[0]

    assert winner.metadata.record_id == "red"
    assert winner.candidate_only is True
    assert winner.exact_sku_decision is False
    assert winner.evidence["scoring_profile"] == "deterministic-plus-embedding-v1"
    assert winner.evidence["embedding_model"]["weights_sha256"] == "1" * 64
    assert winner.evidence["embedding_model"]["license_id"] == "test-only"

    persisted = index.documents()[0]
    persisted["fingerprint"]["embedding_descriptor"]["identity"] = "tampered:model:evidence"
    with pytest.raises(VisualCandidateError, match="identity"):
        IndexedVisual.from_index_document(persisted)


class BrokenEmbedding:
    descriptor = EmbeddingDescriptor(
        provider="testprovider",
        model_name="broken",
        weights_id="fixture-v1",
        weights_sha256="2" * 64,
        license_id="test-only",
        dimensions=3,
    )

    def embed(self, image: Image.Image):
        return [1.0, 2.0]


def test_embedding_dimension_mismatch_fails_closed():
    with pytest.raises(VisualCandidateError, match="dimensions"):
        fingerprint_image(
            image_bytes((20, 30, 40)),
            content_type="image/png",
            embedding_provider=BrokenEmbedding(),
        )


def test_index_upsert_is_stable_and_limits_are_validated():
    data = image_bytes((40, 50, 60))
    index = LocalVisualCandidateIndex()
    index.upsert(metadata("one"), data, content_type="image/png")
    index.upsert(metadata("one"), data, content_type="image/png")

    assert len(index) == 1
    with pytest.raises(VisualCandidateError, match="limit"):
        index.search(data, content_type="image/png", limit=0)
    with pytest.raises(VisualCandidateError, match="minimum_score"):
        index.search(data, content_type="image/png", minimum_score=1.1)
