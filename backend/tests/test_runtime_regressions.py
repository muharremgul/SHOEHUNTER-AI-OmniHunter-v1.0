from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from database_setup import _upgrade_store_circuit_policy
from secret_store import encrypt_secret, get_secret
from store_health import record_store_result, store_circuit_open, store_circuit_status


class SecretCollection:
    def __init__(self, value):
        self.value = value

    async def find_one(self, *_args, **_kwargs):
        return {"ciphertext": encrypt_secret(self.value)}


class StoreHealthCollection:
    def __init__(self, document):
        self.document = document
        self.updates = []

    async def find_one(self, *_args, **_kwargs):
        return self.document

    async def update_one(self, *args, **kwargs):
        self.updates.append((args, kwargs))


class MutableHealthCollection:
    def __init__(self, document):
        self.document = dict(document)

    async def find_one(self, *_args, **_kwargs):
        return dict(self.document)

    async def update_one(self, _filter, update, **_kwargs):
        for key, value in (update.get("$set") or {}).items():
            self.document[key] = value
        for key, value in (update.get("$inc") or {}).items():
            self.document[key] = self.document.get(key, 0) + value
        for key in (update.get("$unset") or {}):
            self.document.pop(key, None)


class EventCollection:
    def __init__(self):
        self.rows = []

    async def insert_one(self, document):
        self.rows.append(dict(document))


class LaneHealthCollection:
    def __init__(self):
        self.documents = {}

    async def find_one(self, filters, *_args, **_kwargs):
        return self.documents.get((filters.get("store_slug"), filters.get("operation")))

    async def update_one(self, filters, update, **_kwargs):
        key = (filters.get("store_slug"), filters.get("operation"))
        document = self.documents.setdefault(
            key,
            {"store_slug": filters.get("store_slug"), "operation": filters.get("operation")},
        )
        for field, value in (update.get("$set") or {}).items():
            document[field] = value
        for field, value in (update.get("$inc") or {}).items():
            document[field] = document.get(field, 0) + value
        for field in (update.get("$unset") or {}):
            document.pop(field, None)


class AsyncRows:
    def __init__(self, rows):
        self.rows = list(rows)

    def __aiter__(self):
        self.iterator = iter(self.rows)
        return self

    async def __anext__(self):
        try:
            return next(self.iterator)
        except StopIteration as error:
            raise StopAsyncIteration from error


class MigratingHealthCollection(MutableHealthCollection):
    def find(self, *_args, **_kwargs):
        return AsyncRows([dict(self.document)])


@pytest.mark.asyncio
async def test_encrypted_secret_overrides_environment_fallback(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "stale-environment-token")
    db = SimpleNamespace(secrets=SecretCollection("new-encrypted-token"))
    assert await get_secret(db, "telegram_bot_token") == "new-encrypted-token"


@pytest.mark.asyncio
async def test_store_circuit_accepts_naive_mongodb_datetime():
    collection = StoreHealthCollection(
        {
            "store_slug": "sportive",
            "circuit_state": "open",
            "circuit_open_until": datetime.now() + timedelta(minutes=5),
        }
    )
    db = SimpleNamespace(store_health=collection)
    assert await store_circuit_open(db, "sportive") is True
    assert collection.updates == []


@pytest.mark.asyncio
async def test_missing_listing_does_not_poison_the_store_circuit():
    health = MutableHealthCollection(
        {
            "store_slug": "adidas",
            "consecutive_failures": 4,
            "total_checks": 10,
            "total_failures": 4,
        }
    )
    events = EventCollection()
    db = SimpleNamespace(store_health=health, store_health_events=events)

    await record_store_result(db, "adidas", "not_found", error="urun kaldirildi", source="product_detail")

    assert health.document["consecutive_failures"] == 4
    assert health.document["total_failures"] == 4
    assert health.document["total_neutral"] == 1
    assert health.document.get("circuit_state") != "open"
    assert events.rows[0]["neutral"] is True
    assert events.rows[0]["failure"] is False


@pytest.mark.asyncio
async def test_real_store_failure_opens_a_bounded_circuit_and_keeps_error_evidence():
    health = MutableHealthCollection(
        {
            "store_slug": "adidas",
            "consecutive_failures": 4,
            "total_checks": 10,
            "total_failures": 4,
        }
    )
    events = EventCollection()
    db = SimpleNamespace(store_health=health, store_health_events=events)

    before = datetime.now().astimezone()
    await record_store_result(db, "adidas", "blocked", error="HTTP 429", source="store_search")

    assert health.document["consecutive_failures"] == 5
    assert health.document["total_failures"] == 5
    assert health.document["circuit_state"] == "open"
    assert health.document["circuit_open_until"] > before
    assert health.document["last_error"] == "HTTP 429"
    assert events.rows[0]["failure"] is True
    assert events.rows[0]["error"] == "HTTP 429"


@pytest.mark.asyncio
async def test_success_clears_stale_error_without_conflicting_mongodb_updates():
    health = MutableHealthCollection(
        {
            "store_slug": "decathlon",
            "consecutive_failures": 2,
            "last_error": "onceki dogrudan deneme",
        }
    )
    events = EventCollection()

    await record_store_result(
        SimpleNamespace(store_health=health, store_health_events=events),
        "decathlon",
        "ok",
        error="fallback oncesi hata kaniti",
        source="circuit_safe_fallback",
    )

    assert health.document["circuit_state"] == "closed"
    assert health.document["consecutive_failures"] == 0
    assert "last_error" not in health.document


@pytest.mark.asyncio
async def test_legacy_deferred_circuit_is_released_during_database_upgrade():
    health = MigratingHealthCollection(
        {
            "store_slug": "adidas",
            "last_status": "deferred",
            "consecutive_failures": 25,
            "circuit_state": "open",
            "circuit_open_until": datetime.now() + timedelta(hours=6),
        }
    )

    await _upgrade_store_circuit_policy(SimpleNamespace(store_health=health))

    assert health.document["circuit_policy_version"] == 4
    assert health.document["circuit_state"] == "closed"
    assert health.document["consecutive_failures"] == 0
    assert "circuit_open_until" not in health.document


@pytest.mark.asyncio
async def test_product_detail_failures_cannot_open_the_discovery_circuit():
    aggregate = MutableHealthCollection({"store_slug": "hepsiburada"})
    lanes = LaneHealthCollection()
    db = SimpleNamespace(
        store_health=aggregate,
        store_health_events=EventCollection(),
        store_circuit_health=lanes,
    )

    for _ in range(5):
        await record_store_result(
            db,
            "hepsiburada",
            "blocked",
            error="HTTP 403 product page",
            source="product_detail",
            operation="product_detail",
        )

    assert await store_circuit_open(db, "hepsiburada", operation="product_detail") is True
    discovery = await store_circuit_status(db, "hepsiburada", operation="discovery")
    assert discovery["open"] is False
    assert discovery["state"] == "closed"


@pytest.mark.asyncio
async def test_safe_fallback_success_does_not_prematurely_close_direct_search_circuit():
    aggregate = MutableHealthCollection({"store_slug": "adidas"})
    lanes = LaneHealthCollection()
    db = SimpleNamespace(
        store_health=aggregate,
        store_health_events=EventCollection(),
        store_circuit_health=lanes,
    )

    for _ in range(5):
        await record_store_result(
            db,
            "adidas",
            "ok",
            error="HTTP 403 direct search; sitemap found result",
            source="discovery_plan",
            operation="discovery",
            circuit_status="blocked",
        )
    assert await store_circuit_open(db, "adidas", operation="discovery") is True

    await record_store_result(
        db,
        "adidas",
        "ok",
        source="circuit_safe_fallback",
        operation="discovery",
        affects_circuit=False,
    )

    assert await store_circuit_open(db, "adidas", operation="discovery") is True


@pytest.mark.asyncio
async def test_neutral_runtime_failure_schedules_retry_without_opening_circuit():
    aggregate = MutableHealthCollection({"store_slug": "decathlon"})
    lanes = LaneHealthCollection()
    db = SimpleNamespace(
        store_health=aggregate,
        store_health_events=EventCollection(),
        store_circuit_health=lanes,
    )

    result = await record_store_result(
        db,
        "decathlon",
        "runtime_error",
        error="[WinError 5] Access denied",
        source="discovery_plan",
        operation="discovery",
    )

    assert result["retry_at"] is not None
    assert await store_circuit_open(db, "decathlon", operation="discovery") is False
    assert lanes.documents[("decathlon", "discovery")].get("consecutive_failures") is None
