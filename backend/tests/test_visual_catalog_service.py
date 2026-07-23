import sys
from copy import deepcopy
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from visual_catalog_service import (  # noqa: E402
    configured_openclip_provider,
    search_visual_records,
    upsert_visual_record,
    visual_catalog_stats,
)


@pytest.fixture(autouse=True)
def isolated_embedding_provider(monkeypatch):
    import visual_catalog_service

    monkeypatch.setenv("VISUAL_EMBEDDING_PROVIDER", "disabled")
    monkeypatch.setattr(visual_catalog_service, "_provider_initialized", False)
    monkeypatch.setattr(visual_catalog_service, "_configured_provider", None)
    yield
    visual_catalog_service._provider_initialized = False
    visual_catalog_service._configured_provider = None


def image_bytes(color):
    image = Image.new("RGB", (128, 96), color)
    draw = ImageDraw.Draw(image)
    draw.rectangle((15, 15, 70, 80), fill=(255, 255, 255))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def nested(document, path):
    value = document
    for part in path.split("."):
        value = value.get(part) if isinstance(value, dict) else None
    return value


class Cursor:
    def __init__(self, rows):
        self.rows = rows

    async def to_list(self, limit):
        return deepcopy(self.rows[:limit])


class Collection:
    def __init__(self):
        self.rows = []

    async def replace_one(self, query, document, upsert=False):
        record_id = query["metadata.record_id"]
        self.rows = [row for row in self.rows if nested(row, "metadata.record_id") != record_id]
        self.rows.append(deepcopy(document))

    def find(self, query):
        rows = [
            row for row in self.rows
            if all(nested(row, key) == value for key, value in query.items())
        ]
        return Cursor(rows)

    async def count_documents(self, query):
        if not query:
            return len(self.rows)
        count = 0
        for row in self.rows:
            matched = True
            for key, expected in query.items():
                actual = nested(row, key)
                if isinstance(expected, dict) and "$ne" in expected:
                    matched = matched and actual != expected["$ne"]
                else:
                    matched = matched and actual == expected
            count += int(matched)
        return count

    async def distinct(self, path):
        return list({nested(row, path) for row in self.rows})


class FakeDb:
    def __init__(self):
        self.visual_candidate_index = Collection()


def metadata(record_id, category="shoes"):
    return {
        "record_id": record_id,
        "canonical_product_id": f"product:{record_id}",
        "category": category,
        "source_name": "catalog",
        "source_item_id": f"item:{record_id}",
        "display_name": f"Candidate {record_id}",
        "variant_id": f"variant:{record_id}",
        "image_role": "product",
        "brand": "Example",
        "model_code": record_id.upper(),
    }


def test_openclip_is_opt_in_and_never_downloaded_by_default(monkeypatch):
    import visual_catalog_service

    for name in (
        "VISUAL_EMBEDDING_PROVIDER",
        "CLIP_ONNX_MODEL_PATH",
        "CLIP_ONNX_MODEL_SHA256",
        "CLIP_ONNX_LICENSE_ID",
        "CLIP_ONNX_MODEL_ID",
        "OPENCLIP_MODEL_NAME",
        "OPENCLIP_CHECKPOINT_PATH",
        "OPENCLIP_WEIGHTS_SHA256",
        "OPENCLIP_LICENSE_ID",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("VISUAL_EMBEDDING_PROVIDER", "disabled")
    monkeypatch.setattr(visual_catalog_service, "_provider_initialized", False)
    monkeypatch.setattr(visual_catalog_service, "_configured_provider", None)

    assert configured_openclip_provider() is None


def test_verified_standard_onnx_model_produces_a_normalized_embedding(monkeypatch):
    import math

    import visual_catalog_service

    model_path = visual_catalog_service.STANDARD_ONNX_MODEL_PATH
    if not model_path.is_file():
        pytest.skip("optional verified ONNX model is not installed")
    monkeypatch.setenv("VISUAL_EMBEDDING_PROVIDER", "onnx_clip")
    monkeypatch.delenv("CLIP_ONNX_MODEL_PATH", raising=False)
    monkeypatch.setattr(visual_catalog_service, "_provider_initialized", False)
    monkeypatch.setattr(visual_catalog_service, "_configured_provider", None)

    provider = visual_catalog_service.configured_embedding_provider()
    vector = provider.embed(Image.new("RGB", (320, 240), (20, 80, 180)))

    assert provider.descriptor.provider == "onnxruntime"
    assert provider.descriptor.license_id == "MIT"
    assert provider.descriptor.weights_sha256 == visual_catalog_service.STANDARD_ONNX_MODEL_SHA256
    assert len(vector) == 512
    assert math.isclose(math.sqrt(sum(value * value for value in vector)), 1.0, rel_tol=1e-5)


@pytest.mark.asyncio
async def test_uploaded_visual_catalog_round_trip_is_network_free_and_candidate_only():
    db = FakeDb()
    red = image_bytes((210, 30, 40))
    blue = image_bytes((20, 40, 220))
    await upsert_visual_record(
        db, image_data=red, content_type="image/png", metadata=metadata("red")
    )
    await upsert_visual_record(
        db, image_data=blue, content_type="image/png", metadata=metadata("blue")
    )

    result = await search_visual_records(
        db,
        image_data=red,
        content_type="image/png",
        category="shoes",
        limit=5,
    )

    assert result["visual_candidates"][0]["metadata"]["record_id"] == "red"
    assert result["visual_candidates"][0]["candidate_only"] is True
    assert result["visual_candidates"][0]["exact_sku_decision"] is False
    assert result["safety"]["network_used"] is False
    assert result["catalog_records_considered"] == 2

    stats = await visual_catalog_stats(db)
    assert stats["total_records"] == 2
    assert stats["ranking_mode"] == "deterministic_fingerprint"


@pytest.mark.asyncio
async def test_category_filter_keeps_outerwear_out_of_shoe_search():
    db = FakeDb()
    data = image_bytes((40, 150, 80))
    await upsert_visual_record(
        db, image_data=data, content_type="image/png", metadata=metadata("shoe", "shoes")
    )
    await upsert_visual_record(
        db, image_data=data, content_type="image/png", metadata=metadata("coat", "outerwear")
    )

    result = await search_visual_records(
        db, image_data=data, content_type="image/png", category="shoes", limit=10
    )

    assert [item["metadata"]["record_id"] for item in result["visual_candidates"]] == ["shoe"]
