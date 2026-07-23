from fcm_service import alert_data_payload, alert_notification_body


def test_fcm_payload_keeps_size_price_and_link_context():
    alert = {
        "id": "alert-1",
        "alert_type": "tracked_size_price_drop",
        "title": "Fiyat düştü ve numaran mevcut",
        "product_name": "Nike Zegama Trail",
        "store": "Örnek Mağaza",
        "sizes": ["42.5", "43"],
        "audience": ["Baba"],
        "price": 3499.9,
        "url": "https://example.com/product",
    }

    payload = alert_data_payload(alert)

    assert payload["alert_id"] == "alert-1"
    assert payload["sizes"] == '["42.5", "43"]'
    assert payload["url"] == "https://example.com/product"
    assert "42.5" in payload["notification_body"]
    assert "3,499.90 TL" in payload["notification_body"]
    assert all(isinstance(value, str) for value in payload.values())


def test_fcm_body_survives_missing_optional_fields():
    assert alert_notification_body({"product_name": "Ürün"}) == "Ürün · Mağaza"
