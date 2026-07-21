import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from engines import ENGINES  # noqa: E402
from services import _event_alerts, telegram_feedback_keyboard  # noqa: E402
from store_health import health_snapshot  # noqa: E402


def engine(slug):
    return next(item for item in ENGINES if item.slug == slug)


def test_adidas_reads_product_group_inside_graph():
    html = """
    <script type="application/ld+json">
    {"@graph":[{"@type":"ProductGroup","hasVariant":[
      {"@type":"Product","size":"42","sku":"SKU42","offers":{"price":"6799","availability":"https://schema.org/InStock"}},
      {"@type":"Product","size":"43","sku":"SKU43","offers":{"price":"6799","availability":"https://schema.org/OutOfStock"}}
    ]}]}
    </script>
    """
    result = engine("adidas").parse(html, "https://www.adidas.com.tr/test/JQ1616.html")
    assert result["current_price"] == 6799
    assert result["stock_count"] == 1
    assert result["confidence"] == 0.9


def test_adidas_fallbacks_are_explicit_and_do_not_invent_sizes():
    product_html = """
    <script type="application/ld+json">
    {"@type":"Product","name":"Adizero","offers":{"price":"10199","availability":"https://schema.org/InStock"}}
    </script>
    """
    product = engine("adidas").parse(product_html, "https://www.adidas.com.tr/test/JH6206.html")
    assert product["current_price"] == 10199
    assert product["confidence"] == 0.6
    assert product["sizes"] == []

    dom = engine("adidas").parse(
        '<div data-testid="price-value">Price10.199 TL</div>',
        "https://www.adidas.com.tr/test/JH6206.html",
    )
    assert dom["current_price"] == 10199
    assert dom["price_source"] == "dom_text:adidas_price_label"
    assert dom["confidence"] == 0.55
    assert dom["sizes"] == []


def test_trendyol_accepts_real_product_url_and_reads_embedded_data():
    adapter = engine("trendyol")
    url = "https://www.trendyol.com/nike/air-max-90-p-123456"
    assert adapter.is_product_link(url) is True
    data = {
        "props": {
            "pageProps": {
                "product": {
                    "id": 123456,
                    "name": "Nike Air Max 90",
                    "discountedPrice": 4299,
                    "originalPrice": 4999,
                    "merchantName": "Ornek Magaza",
                    "variants": [
                        {"attributeTypeName": "Beden", "attributeValue": "42", "outOfStock": False},
                        {"attributeTypeName": "Beden", "attributeValue": "43", "outOfStock": True},
                    ],
                }
            }
        }
    }
    html = f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script>'
    result = adapter.parse(html, url)
    assert result["current_price"] == 4299
    assert result["old_price"] == 4999
    assert result["seller"] == "Ornek Magaza"
    assert result["stock_count"] == 1


class NeverWatchCollection:
    def find(self, *_args, **_kwargs):
        raise AssertionError("low confidence data must not query alert watches")


class EmptyHistory:
    async def find_one(self, *_args, **_kwargs):
        return None


@pytest.mark.asyncio
async def test_low_confidence_price_drop_is_safely_skipped():
    db = SimpleNamespace(watch_queries=NeverWatchCollection(), price_history=EmptyHistory())
    listing = {
        "id": "listing-1",
        "product_id": "product-1",
        "url": "https://www.adidas.com.tr/test/JH6206.html",
        "title": "Adizero",
        "last_price": 12000,
        "last_stock_status": "in_stock",
    }
    data = {
        "title": "Adizero",
        "current_price": 10000,
        "confidence": 0.55,
        "price_source": "dom_text:adidas_price_label",
        "sizes": [],
    }
    alerts = await _event_alerts(db, listing, data, "in_stock", engine("adidas"))
    assert alerts == []


def test_telegram_feedback_keyboard_uses_only_supported_codes():
    keyboard = telegram_feedback_keyboard("alert-1")
    values = [button["callback_data"] for button in keyboard["inline_keyboard"][0]]
    assert values == [
        "feedback:alert-1:bought",
        "feedback:alert-1:no_size",
        "feedback:alert-1:wrong",
    ]


class AsyncRows:
    def __init__(self, rows):
        self.rows = rows

    def sort(self, *_args, **_kwargs):
        return self

    async def to_list(self, _limit):
        return [dict(row) for row in self.rows]


class HealthCollection:
    def __init__(self, rows):
        self.rows = rows

    def find(self, *_args, **_kwargs):
        return AsyncRows(self.rows)


class HealthEvents:
    def __init__(self, rows):
        self.rows = rows

    def aggregate(self, _pipeline):
        return AsyncRows(self.rows)


@pytest.mark.asyncio
async def test_health_snapshot_exposes_consistent_24h_metrics_and_circuit_state():
    db = SimpleNamespace(
        store_health=HealthCollection(
            [
                {
                    "store_slug": "adidas",
                    "total_checks": 100,
                    "total_success": 50,
                    "circuit_state": "open",
                    "circuit_open_until": datetime.now(timezone.utc) + timedelta(minutes=5),
                }
            ]
        ),
        store_health_events=HealthEvents(
            [
                {
                    "_id": "adidas",
                    "checks": 10,
                    "successes": 8,
                    "failures": 2,
                    "neutral": 0,
                    "blocked": 2,
                    "average_latency_ms": 125.4,
                }
            ]
        ),
    )
    result = (await health_snapshot(db))[0]
    assert result["checks_24h"] == 10
    assert result["success_count_24h"] == 8
    assert result["failure_count_24h"] == 2
    assert result["neutral_count_24h"] == 0
    assert result["blocked_count_24h"] == 2
    assert result["success_rate_24h"] == 0.8
    assert result["circuit_open"] is True
