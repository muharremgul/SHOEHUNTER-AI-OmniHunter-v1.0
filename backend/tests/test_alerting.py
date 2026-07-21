import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from alerting import create_alert, telegram_alert_message


class FakeAlerts:
    def __init__(self):
        self.doc = None

    async def find_one(self, query, projection=None):
        if self.doc and self.doc.get("deduplication_key") == query.get("deduplication_key"):
            return dict(self.doc)
        return None

    async def insert_one(self, document):
        self.doc = dict(document)

    async def update_one(self, query, update):
        for key, value in update.get("$set", {}).items():
            self.doc[key] = value
        for key, value in update.get("$inc", {}).items():
            self.doc[key] = self.doc.get(key, 0) + value


class FakeDb:
    def __init__(self):
        self.alerts = FakeAlerts()


def test_universal_alert_is_unread_and_deduplicated():
    async def run():
        db = FakeDb()
        first = await create_alert(
            db,
            alert_type="new_listing",
            title="Yeni ilan",
            product_id="product-1",
            listing_id="listing-1",
            product_name="Adizero Evo SL",
        )
        assert first["is_read"] is False
        assert first["notification_status"] == "pending"
        second = await create_alert(
            db,
            alert_type="new_listing",
            title="Yeni ilan",
            product_id="product-1",
            listing_id="listing-1",
            product_name="Adizero Evo SL",
        )
        assert second is None
        assert db.alerts.doc["occurrence_count"] == 2

    asyncio.run(run())


def test_telegram_html_is_escaped_and_unsafe_url_is_omitted():
    message = telegram_alert_message(
        {
            "title": "<b>Sahte</b>",
            "product_name": "A&B",
            "store": "<script>alert(1)</script>",
            "price": 1000,
            "url": "javascript:alert(1)",
        }
    )
    assert "<script>" not in message
    assert "&lt;script&gt;" in message
    assert "javascript:" not in message
    assert "A&amp;B" in message
    assert "Beden / numara" in message
    assert "doğrulanamadı" in message


def test_telegram_alert_always_includes_sizes_and_family_audience():
    message = telegram_alert_message(
        {
            "title": "Numaran yeniden stokta",
            "product_name": "Pegasus 41",
            "store": "Sportive",
            "price": 3999,
            "sizes": ["42", "43"],
            "size_label": "Numara",
            "audience": ["Ali", "Ayşe"],
        }
    )
    assert "<b>Numara:</b> 42, 43" in message
    assert "<b>Kimin icin:</b> Ali, Ayşe" in message
