import os
import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

TEST_DB_NAME = f"shoehunter_pytest_{os.getpid()}"
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
os.environ["DB_NAME"] = TEST_DB_NAME
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "TestYonetici2026"
os.environ["EMBEDDED_SCHEDULER"] = "false"
os.environ["CORS_ORIGINS"] = "http://localhost:3000"
os.environ["GEMINI_API_KEY"] = ""
os.environ["GROQ_API_KEY"] = ""
os.environ["OPENAI_API_KEY"] = ""
os.environ["EMERGENT_LLM_KEY"] = ""

from server import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    mongo = MongoClient(MONGO_URL, serverSelectionTimeoutMS=2000)
    try:
        mongo.admin.command("ping")
    except Exception:
        pytest.skip("MongoDB integration test icin kullanilabilir degil")
    mongo.drop_database(TEST_DB_NAME)
    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "TestYonetici2026"},
        )
        assert response.status_code == 200
        yield test_client
    mongo.drop_database(TEST_DB_NAME)
    mongo.close()


def csrf_headers(client):
    return {"X-CSRF-Token": client.cookies.get("shoehunter_csrf")}


def test_login_required(client):
    saved = dict(client.cookies)
    client.cookies.clear()
    response = client.get("/api/products")
    assert response.status_code == 401
    client.cookies.update(saved)


def test_secret_not_returned(client):
    response = client.get("/api/settings")
    assert response.status_code == 200
    telegram = response.json()["telegram"]
    assert "bot_token" not in telegram
    assert "configured" in telegram


def test_csrf_required_for_mutation(client):
    response = client.post("/api/products", json={"name": "CSRF Test Urunu"})
    assert response.status_code == 403


def test_ssrf_localhost_rejected(client):
    response = client.post(
        "/api/track/quick",
        json={"url": "http://127.0.0.1:8000/api/health"},
        headers=csrf_headers(client),
    )
    assert response.status_code == 400


def test_create_watch_query(client):
    query = f"Adidas Adizero Evo SL {uuid.uuid4().hex[:8]}"
    response = client.post(
        "/api/watches",
        json={
            "raw_query": query,
            "desired_sizes": ["43 1/3", "44"],
            "target_price": 5500,
            "color_policy": "any",
            "store_scope": ["adidas", "intersport"],
        },
        headers=csrf_headers(client),
    )
    assert response.status_code == 200
    watch_id = response.json()["id"]
    detail = client.get(f"/api/watches/{watch_id}")
    assert detail.status_code == 200
    assert detail.json()["watch"]["desired_sizes"] == ["43 1/3", "44"]
    deleted = client.delete(f"/api/watches/{watch_id}", headers=csrf_headers(client))
    assert deleted.status_code == 200


def test_product_delete_cascade(client):
    response = client.post(
        "/api/products",
        json={"name": f"Cascade Test {uuid.uuid4().hex[:8]}"},
        headers=csrf_headers(client),
    )
    assert response.status_code == 200
    product_id = response.json()["id"]
    mongo = MongoClient(MONGO_URL)
    database = mongo[TEST_DB_NAME]
    database.alerts.insert_one(
        {
            "id": uuid.uuid4().hex,
            "product_id": product_id,
            "is_read": False,
            "created_at": "2026-07-12T00:00:00+00:00",
        }
    )
    deleted = client.delete(f"/api/products/{product_id}", headers=csrf_headers(client))
    assert deleted.status_code == 200
    assert database.alerts.count_documents({"product_id": product_id}) == 0
    mongo.close()


def test_exact_cors_origin(client):
    response = client.options(
        "/api/products",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_products_best_price_ignores_out_of_stock_listing(client):
    product_id = uuid.uuid4().hex
    mongo = MongoClient(MONGO_URL)
    database = mongo[TEST_DB_NAME]
    database.products.insert_one(
        {
            "id": product_id,
            "name": "Stok Fiyati Test Urunu",
            "active": True,
            "created_at": "2026-07-13T00:00:00+00:00",
        }
    )
    database.listings.insert_many(
        [
            {
                "id": uuid.uuid4().hex,
                "product_id": product_id,
                "store": "Intersport",
                "url": "https://www.intersport.com.tr/urun/test/out",
                "active": True,
                "last_price": 1000.0,
                "last_stock_status": "out_of_stock",
                "last_in_stock": False,
                "last_sizes": [],
            },
            {
                "id": uuid.uuid4().hex,
                "product_id": product_id,
                "store": "Intersport",
                "url": "https://www.intersport.com.tr/urun/test/in",
                "active": True,
                "last_price": 2500.0,
                "last_stock_status": "in_stock",
                "last_in_stock": True,
                "last_sizes": [],
            },
        ]
    )
    try:
        response = client.get("/api/products")
        assert response.status_code == 200
        product = next(item for item in response.json() if item["id"] == product_id)
        assert product["best_price"] == 2500.0
    finally:
        database.listings.delete_many({"product_id": product_id})
        database.products.delete_one({"id": product_id})
        mongo.close()
