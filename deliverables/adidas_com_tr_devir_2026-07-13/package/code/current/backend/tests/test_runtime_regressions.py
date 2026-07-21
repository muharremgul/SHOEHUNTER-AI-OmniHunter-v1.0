from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from secret_store import encrypt_secret, get_secret
from store_health import store_circuit_open


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
