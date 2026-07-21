import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import label_scan  # noqa: E402
from label_scan import _gtin_valid, _normalize_ocr_geometry, _read_text, parse_label_text  # noqa: E402


def blocks(*texts):
    return [{"text": text, "confidence": 0.98} for text in texts]


def test_ocr_geometry_is_normalized_for_the_original_image():
    rows = [{"text": "JR5220", "confidence": 0.99, "box": [[20, 10], [60, 10], [60, 30], [20, 30]]}]

    normalized = _normalize_ocr_geometry(rows, 0, 100, 50)

    assert normalized[0]["polygon_norm"] == [[0.2, 0.2], [0.6, 0.2], [0.6, 0.6], [0.2, 0.6]]


def test_rotated_ocr_geometry_is_mapped_back_before_the_ui_draws_it():
    rows = [{"text": "JR5220", "confidence": 0.99, "box": [[10, 20], [30, 20], [30, 60], [10, 60]]}]

    clockwise_source = _normalize_ocr_geometry(rows, 90, 100, 50)
    counterclockwise_source = _normalize_ocr_geometry(rows, 270, 100, 50)

    assert clockwise_source[0]["polygon_norm"] == [[0.8, 0.2], [0.8, 0.6], [0.4, 0.6], [0.4, 0.2]]
    assert counterclockwise_source[0]["polygon_norm"] == [[0.2, 0.8], [0.2, 0.4], [0.6, 0.4], [0.6, 0.8]]


def test_upside_down_ocr_geometry_is_mapped_back_before_the_ui_draws_it():
    rows = [{"text": "JR5220", "confidence": 0.99, "box": [[20, 10], [60, 10], [60, 30], [20, 30]]}]

    normalized = _normalize_ocr_geometry(rows, 180, 100, 50)

    assert normalized[0]["polygon_norm"] == [[0.8, 0.8], [0.4, 0.8], [0.4, 0.4], [0.8, 0.4]]


def test_ocr_fallback_includes_an_upside_down_pass(monkeypatch):
    attempts = iter(
        [
            [{"text": "noise", "confidence": 0.1}],
            [{"text": "side", "confidence": 0.2}],
            [{"text": "JR5220", "confidence": 0.99}],
            [{"text": "other", "confidence": 0.3}],
        ]
    )
    monkeypatch.setattr(label_scan, "_ocr_once", lambda _image: next(attempts))
    monkeypatch.setattr(
        label_scan,
        "_text_quality",
        lambda rows: float(rows[0]["confidence"]),
    )

    rows, rotation = _read_text(label_scan.Image.new("RGB", (100, 50)))

    assert rotation == 180
    assert rows[0]["text"] == "JR5220"


def test_adidas_shoe_box_becomes_exact_code_radar_query():
    result = parse_label_text(
        blocks("adizero EVO SL M", "JH6206", "US 10", "UK 9 1/2", "F 44", "RUNNING"),
        [{"value": "4067903745960", "format": "EAN-13"}],
    )
    assert result["brand"] == "Adidas"
    assert result["product_codes"][0] == "JH6206"
    assert result["sizes"] == ["44"]
    assert result["suggested_watch"]["raw_query"] == "Adidas adizero EVO SL M RUNNING JH6206"
    assert result["suggested_watch"]["source_identifiers"]["barcode"] == "4067903745960"


def test_nike_tongue_code_and_eu_size_are_extracted():
    result = parse_label_text(blocks("NIKE", "HV8113-200", "EUR 42.5", "NIKE ACG ZEGAMA TRAIL"))
    assert result["brand"] == "Nike"
    assert result["product_codes"][0] == "HV8113-200"
    assert result["category"] == "shoes"
    assert result["sizes"] == ["42.5"]
    assert "ZEGAMA TRAIL" in result["suggested_watch"]["raw_query"]


def test_under_armour_code_and_size_are_extracted():
    result = parse_label_text(blocks("UNDER ARMOUR", "Art: 3027000-107", "EUR 43", "CM 27.5"))
    assert result["brand"] == "Under Armour"
    assert result["product_codes"][0] == "3027000-107"
    assert result["sizes"] == ["43"]


def test_store_price_label_uses_latest_visible_price_as_target():
    result = parse_label_text(blocks("TV 65\"", "Q65NM1105 QLED", "NORDMENDE", "27.499TL", "24.999TL"))
    assert result["brand"] == "Nordmende"
    assert result["prices"] == [27499.0, 24999.0]
    assert result["suggested_watch"]["target_price"] == 24999.0
    assert "Q65NM1105" in result["suggested_watch"]["raw_query"]


def test_ocr_digit_groups_can_rebuild_a_valid_ean13():
    result = parse_label_text(blocks("ADIDAS.COM", "JF2443", "4", "067896", "537221"))
    assert _gtin_valid("4067896537221")
    assert result["barcodes"][0]["value"] == "4067896537221"
    assert "barcode" not in result["suggested_watch"]["source_identifiers"]


def test_other_products_do_not_receive_false_clothing_sizes():
    result = parse_label_text(blocks("TV 65", "Q65NM1105 QLED", "NORDMENDE", "S"))
    assert result["category"] == "other"
    assert result["sizes"] == []


def test_price_reader_tolerates_tl_where_ocr_drops_the_t():
    result = parse_label_text(blocks("NORDMENDE", "27.499L", "24.999πL"))
    assert result["prices"] == [27499.0, 24999.0]


def test_split_tv_model_code_is_rejoined():
    result = parse_label_text(blocks("TV 65", "HL65QUMLN-", "W02S UHD QLED", "28.999πL"))
    assert result["product_codes"][0] == "HL65QUMLN-W02S"
    assert result["suggested_watch"]["model"] == "HL65QUMLN-W02S"
    assert result["suggested_watch"]["target_price"] == 28999.0
