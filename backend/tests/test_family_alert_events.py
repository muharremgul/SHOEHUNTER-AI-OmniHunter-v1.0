import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services import _event_alerts


class ListCursor:
    def __init__(self, rows):
        self.rows = rows

    async def to_list(self, _limit):
        return [dict(row) for row in self.rows]


class WatchCollection:
    def __init__(self, rows):
        self.rows = rows

    def find(self, *_args, **_kwargs):
        return ListCursor(self.rows)


class PriceHistoryCollection:
    async def find_one(self, *_args, **_kwargs):
        return None


class AlertsCollection:
    def __init__(self):
        self.rows = []

    async def find_one(self, query, projection=None):
        return next((dict(row) for row in self.rows if row.get("deduplication_key") == query.get("deduplication_key")), None)

    async def insert_one(self, document):
        self.rows.append(dict(document))

    async def update_one(self, query, update):
        row = next(item for item in self.rows if item.get("deduplication_key") == query.get("deduplication_key"))
        row.update(update.get("$set", {}))
        for key, value in update.get("$inc", {}).items():
            row[key] = row.get(key, 0) + value


@pytest.mark.asyncio
async def test_tracked_last_size_returns_at_discounted_price_with_family_context():
    watch = {
        "id": "watch-1",
        "product_id": "product-1",
        "active": True,
        "category": "shoes",
        "size_label": "Numara",
        "desired_sizes": ["42", "43"],
        "size_preferences": [
            {
                "member_name": "Ali",
                "category": "shoes",
                "sizes": ["42", "43"],
            }
        ],
    }
    db = SimpleNamespace(
        watch_queries=WatchCollection([watch]),
        price_history=PriceHistoryCollection(),
        alerts=AlertsCollection(),
    )
    listing = {
        "id": "listing-1",
        "product_id": "product-1",
        "url": "https://example.com/product",
        "title": "Test Ayakkabi",
        "last_checked_at": "2026-07-18T00:00:00+00:00",
        "last_price": 4000.0,
        "last_stock_status": "out_of_stock",
        "last_in_stock": False,
        "last_sizes": [{"name": "43", "in_stock": False}],
    }
    data = {
        "title": "Test Ayakkabi",
        "current_price": 4000.0,
        "old_price": 6000.0,
        "cart_price": None,
        "confidence": 0.9,
        "sizes": [{"name": "43", "in_stock": True}],
    }

    alerts = await _event_alerts(db, listing, data, "in_stock", SimpleNamespace(name="Test Store"))
    by_type = {alert["alert_type"]: alert for alert in alerts}

    assert by_type["discounted_restock"]["sizes"] == ["43"]
    assert by_type["discounted_restock"]["audience"] == ["Ali"]
    assert by_type["last_size_deal"]["size_label"] == "Numara"
    assert by_type["last_size_deal"]["price"] == 4000.0


def event_db(watches=None):
    return SimpleNamespace(
        watch_queries=WatchCollection(watches or []),
        price_history=PriceHistoryCollection(),
        alerts=AlertsCollection(),
    )


@pytest.mark.asyncio
async def test_three_percent_drop_with_tracked_size_uses_specific_alert_class():
    watch = {
        "id": "watch-drop",
        "product_id": "product-1",
        "active": True,
        "category": "shoes",
        "desired_sizes": ["43"],
        "minimum_drop_percent": 0,
        "minimum_drop_amount": 0,
    }
    listing = {
        "id": "listing-drop",
        "product_id": "product-1",
        "url": "https://example.com/drop",
        "last_price": 1000.0,
        "last_stock_status": "in_stock",
        "last_in_stock": True,
        "last_sizes": [{"name": "43", "in_stock": True}],
    }
    data = {
        "title": "Test Ayakkabi",
        "current_price": 970.0,
        "confidence": 0.9,
        "sizes": [{"name": "43", "in_stock": True}],
    }
    alerts = await _event_alerts(event_db([watch]), listing, data, "in_stock", SimpleNamespace(name="Store"))
    tracked = next(alert for alert in alerts if alert["alert_type"] == "tracked_size_price_drop")
    assert tracked["sizes"] == ["43"]
    assert "%3" in tracked["title"]


@pytest.mark.asyncio
async def test_unchanged_cart_offer_creates_continuation_alert():
    listing = {
        "id": "listing-cart",
        "product_id": "product-1",
        "url": "https://example.com/cart",
        "last_price": 1000.0,
        "last_cart_price": 800.0,
        "last_checked_at": "2026-07-18T00:00:00+00:00",
        "last_stock_status": "in_stock",
        "last_in_stock": True,
        "last_sizes": [],
    }
    data = {
        "title": "Test Urun",
        "current_price": 1000.0,
        "cart_price": 800.0,
        "cart_price_conditions": [],
        "confidence": 0.9,
        "sizes": [],
    }
    alerts = await _event_alerts(event_db(), listing, data, "in_stock", SimpleNamespace(name="Store"))
    assert any(alert["alert_type"] == "cart_price_continues" for alert in alerts)


@pytest.mark.asyncio
async def test_inventory_shrinking_to_one_size_creates_critical_stock_alert_for_link_product():
    listing = {
        "id": "listing-critical",
        "product_id": "product-link",
        "url": "https://example.com/critical",
        "last_price": 2000.0,
        "last_checked_at": "2026-07-18T00:00:00+00:00",
        "last_stock_status": "in_stock",
        "last_in_stock": True,
        "last_sizes": [
            {"name": "42", "in_stock": True},
            {"name": "43", "in_stock": True},
            {"name": "44", "in_stock": True},
        ],
    }
    data = {
        "title": "Test Ayakkabi",
        "current_price": 2000.0,
        "confidence": 0.9,
        "sizes": [
            {"name": "42", "in_stock": False},
            {"name": "43", "in_stock": True},
            {"name": "44", "in_stock": False},
        ],
    }
    alerts = await _event_alerts(event_db(), listing, data, "in_stock", SimpleNamespace(name="Store"))
    critical = next(alert for alert in alerts if alert["alert_type"] == "critical_stock")
    assert critical["sizes"] == ["43"]


@pytest.mark.asyncio
async def test_single_color_single_size_restock_is_classified_separately():
    listing = {
        "id": "listing-single",
        "product_id": "product-link",
        "url": "https://example.com/single",
        "last_price": 2500.0,
        "last_checked_at": "2026-07-18T00:00:00+00:00",
        "last_stock_status": "out_of_stock",
        "last_in_stock": False,
        "last_sizes": [{"name": "42", "in_stock": False}],
    }
    data = {
        "title": "Siyah Test Ayakkabi",
        "current_price": 2500.0,
        "confidence": 0.9,
        "sizes": [{"name": "42", "in_stock": True}],
    }
    alerts = await _event_alerts(event_db(), listing, data, "in_stock", SimpleNamespace(name="Store"))
    assert any(alert["alert_type"] == "single_variant_restock" for alert in alerts)
