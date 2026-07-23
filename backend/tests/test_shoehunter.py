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

import server as server_module  # noqa: E402
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


def test_https_reverse_proxy_login_sets_secure_cookies(client):
    saved = dict(client.cookies)
    client.cookies.clear()
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "TestYonetici2026"},
        headers={"X-Forwarded-Proto": "https"},
    )
    assert response.status_code == 200
    cookies = response.headers.get_list("set-cookie")
    assert len(cookies) == 2
    assert all("Secure" in value for value in cookies)
    client.cookies.clear()
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


def test_mobile_fcm_fid_registration_uses_revocable_device_token(client):
    device_id = f"android-{uuid.uuid4()}"
    first_fcm_fid = "a" * 22
    registration = client.post(
        "/api/mobile/device/register",
        json={
            "device_id": device_id,
            "platform": "android",
            "app_version": "0.1.0-test",
            "fcm_fid": first_fcm_fid,
        },
        headers=csrf_headers(client),
    )
    assert registration.status_code == 200
    device_token = registration.json()["device_token"]

    replacement = "b" * 22
    updated = client.post(
        "/api/mobile/device/push-registration",
        json={"installation_id": replacement},
        headers={"Authorization": f"Bearer {device_token}"},
    )
    assert updated.status_code == 200
    assert updated.json()["ok"] is True

    mongo = MongoClient(MONGO_URL)
    try:
        row = mongo[TEST_DB_NAME].mobile_devices.find_one({"device_id": device_id})
        assert row["fcm_fid"] == replacement
        assert row["fcm_fid_hash"] != replacement
    finally:
        mongo.close()


def test_scan_label_endpoint_accepts_authenticated_image(client, monkeypatch):
    monkeypatch.setattr(
        server_module,
        "scan_product_label",
        lambda data, content_type: {
            "confidence": 0.94,
            "suggested_watch": {
                "raw_query": "Nike Zegama Trail HV8113-200",
                "model": "HV8113-200",
                "input_origin": "label_scan",
            },
        },
    )
    response = client.post(
        "/api/radar/scan-label",
        files={"image": ("etiket.jpg", b"test-image", "image/jpeg")},
        headers=csrf_headers(client),
    )
    assert response.status_code == 200
    assert response.json()["suggested_watch"]["model"] == "HV8113-200"


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


def test_label_scan_origin_and_identifier_are_kept_on_watch(client):
    query = f"Nike Zegama Etiket {uuid.uuid4().hex[:8]}"
    response = client.post(
        "/api/watches",
        json={
            "raw_query": query,
            "input_origin": "label_scan",
            "source_identifiers": {"product_code": "HV8113-200"},
        },
        headers=csrf_headers(client),
    )
    assert response.status_code == 200
    watch = response.json()
    assert watch["input_origin"] == "label_scan"
    assert watch["source_identifiers"] == {"product_code": "HV8113-200"}
    deleted = client.delete(f"/api/watches/{watch['id']}", headers=csrf_headers(client))
    assert deleted.status_code == 200


def test_family_profile_sizes_are_merged_into_radar(client):
    profile_response = client.put(
        "/api/profile",
        json={
            "household_members": [
                {
                    "id": "member-ayse",
                    "name": "Ayse",
                    "relationship": "Aile",
                    "preferences": [
                        {
                            "id": "ayse-shoes",
                            "category": "shoes",
                            "label": "Ayakkabi",
                            "size_system": "EU",
                            "sizes": ["38", "39"],
                        }
                    ],
                }
            ]
        },
        headers=csrf_headers(client),
    )
    assert profile_response.status_code == 200

    query = f"Aile Radar Test {uuid.uuid4().hex[:8]}"
    response = client.post(
        "/api/watches",
        json={
            "raw_query": query,
            "category": "shoes",
            "desired_sizes": ["40"],
            "profile_preference_ids": ["ayse-shoes"],
            "store_scope": ["intersport"],
        },
        headers=csrf_headers(client),
    )
    assert response.status_code == 200
    watch = response.json()
    assert watch["desired_sizes"] == ["38", "39", "40"]
    assert watch["manual_desired_sizes"] == ["40"]
    assert watch["size_preferences"][0]["member_name"] == "Ayse"
    product_row = next(item for item in client.get("/api/products").json() if item["name"] == query)
    assert product_row["category"] == "shoes"
    assert product_row["radar_watch_count"] == 1
    assert "radar" in product_row["tracking_origins"]

    updated_profile = client.put(
        "/api/profile",
        json={
            "household_members": [
                {
                    "id": "member-ayse",
                    "name": "Ayse",
                    "preferences": [
                        {
                            "id": "ayse-shoes",
                            "category": "shoes",
                            "size_system": "EU",
                            "sizes": ["39", "41"],
                        }
                    ],
                }
            ]
        },
        headers=csrf_headers(client),
    )
    assert updated_profile.status_code == 200
    refreshed = client.get(f"/api/watches/{watch['id']}").json()["watch"]
    assert refreshed["desired_sizes"] == ["39", "40", "41"]
    client.delete(f"/api/watches/{watch['id']}", headers=csrf_headers(client))


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


def test_manual_product_exposes_category_and_tracking_origin(client):
    name = f"Sinif Test Tisort {uuid.uuid4().hex[:8]}"
    response = client.post(
        "/api/products",
        json={"name": name, "category": "tops"},
        headers=csrf_headers(client),
    )
    assert response.status_code == 200
    product_id = response.json()["id"]
    row = next(item for item in client.get("/api/products").json() if item["id"] == product_id)
    assert row["category"] == "tops"
    assert row["tracking_origins"] == ["manual"]
    client.delete(f"/api/products/{product_id}", headers=csrf_headers(client))
