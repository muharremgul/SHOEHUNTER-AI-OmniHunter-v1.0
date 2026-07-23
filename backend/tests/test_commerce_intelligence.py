from commerce_intelligence import (
    build_gs1_digital_link,
    canonical_product_projection,
    compute_seller_trust,
    compute_total_cost,
    parse_gs1_digital_link,
    parse_gs1_element_string,
)


def test_total_cost_adds_explicit_shipping_and_uses_unconditional_cart_price():
    result = compute_total_cost(
        {
            "last_price": 1000,
            "last_cart_price": 900,
            "last_cart_price_conditions": [],
            "shipping": "Kargo 39,90 TL",
        }
    )
    assert result["amount"] == 939.9
    assert result["complete"] is True
    assert result["price_kind"] == "cart"


def test_total_cost_does_not_apply_conditional_cart_price_or_invent_shipping():
    result = compute_total_cost(
        {
            "last_price": 1000,
            "last_cart_price": 800,
            "last_cart_price_conditions": ["üyelik gerekir"],
            "shipping": "Yarın teslimat",
        }
    )
    assert result["amount"] == 1000
    assert result["complete"] is False
    assert result["conditions"] == ["üyelik gerekir"]
    assert result["missing"] == ["shipping_cost"]


def test_seller_trust_marks_marketplace_unknown_seller_as_low_evidence():
    result = compute_seller_trust({"store_slug": "n11", "last_stock_status": "in_stock", "last_checked_at": "now"})
    assert result["marketplace"] is True
    assert result["score"] < 60
    assert result["risks"]


def test_official_seller_with_rating_is_high_trust_but_not_a_guarantee():
    result = compute_seller_trust(
        {
            "store_slug": "trendyol",
            "seller": "Resmi Marka",
            "seller_rating": 9.7,
            "official_seller": True,
            "last_stock_status": "in_stock",
            "last_checked_at": "now",
        }
    )
    assert result["band"] == "high"
    assert "garantisi değildir" in result["disclaimer"]


def test_gs1_digital_link_parses_common_identifiers_without_network_access():
    result = parse_gs1_digital_link("https://id.gs1.org/01/09506000134352/10/LOT7?21=SER42")
    assert result["is_gs1_digital_link"] is True
    assert result["identifiers"]["gtin"] == "09506000134352"
    assert result["identifiers"]["batch_lot"] == "LOT7"
    assert result["identifiers"]["serial"] == "SER42"
    assert result["warnings"] == []


def test_gs1_element_string_and_digital_link_round_trip():
    parsed = parse_gs1_element_string(
        "(01)09506000134352(10)LOT 7(17)271231(21)SER/42"
    )
    assert parsed["is_gs1_element_string"] is True
    assert parsed["identifiers"]["gtin"] == "09506000134352"
    assert parsed["identifiers"]["batch_lot"] == "LOT 7"

    url = build_gs1_digital_link(parsed["identifiers"])
    assert url == (
        "https://id.gs1.org/01/09506000134352/10/LOT%207/21/SER%2F42?17=271231"
    )
    reparsed = parse_gs1_digital_link(url)
    assert reparsed["identifiers"] == parsed["identifiers"]


def test_gs1_builder_rejects_invalid_gtin_and_non_https_resolver():
    import pytest

    with pytest.raises(ValueError, match="14 haneli"):
        build_gs1_digital_link({"gtin": "123"})
    with pytest.raises(ValueError, match="HTTPS"):
        build_gs1_digital_link({"gtin": "09506000134352"}, resolver_base="http://id.gs1.org")


def test_canonical_projection_separates_product_variant_and_identifiers():
    result = canonical_product_projection(
        {
            "id": "p1",
            "name": "Adidas Trail Running",
            "brand": "Adidas",
            "model": "JR5220",
            "canonical_key": "adidas:jr5220",
            "family_key": "adidas:trail-running",
            "category": "shoes",
            "attributes": {"color": "black"},
            "identity": {"brand": "adidas", "model_code": "JR5220"},
            "identity_version": 2,
        },
        [{"id": "l1", "store_slug": "adidas", "model_code": "JR5220"}],
    )
    assert result["canonical_product"]["canonical_key"] == "adidas:jr5220"
    assert result["product_variant"]["attributes"]["color"] == "black"
    assert result["product_identifiers"][0]["type"] == "mpn"
