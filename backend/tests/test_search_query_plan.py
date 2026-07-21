import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import discovery_service  # noqa: E402
from discovery_service import (  # noqa: E402
    _candidate_identity,
    _coverage_summary,
    _fallback_engine_plan,
    _search_engine_plan,
    _transport_error_status,
    _watch_identity,
)
from search_query_plan import SearchQuery, build_search_plan  # noqa: E402


def test_label_scan_plan_uses_product_code_and_barcode_before_generic_ocr_query():
    watch = {
        "raw_query": "TRAIL RUNNING JR5220",
        "model": "JR5220",
        "source_identifiers": {
            "product_code": "JR5220",
            "barcode": "4067904494690",
        },
    }

    plan = build_search_plan(watch)

    assert [(item.query, item.kind) for item in plan] == [
        ("JR5220", "product_code"),
        ("4067904494690", "barcode"),
        ("TRAIL RUNNING JR5220", "raw_query"),
    ]
    assert plan[0].exact_identifier is True
    assert plan[1].exact_identifier is True


def test_existing_watch_identity_codes_also_receive_an_exact_search_lane():
    plan = build_search_plan(
        {
            "raw_query": "TRAIL RUNNING JR5220",
            "known_model_codes": ["JR5220"],
            "identity": {"model_codes": ["JR5220"], "gtins": ["4067904494690"]},
        }
    )

    assert [(item.query, item.kind) for item in plan[:2]] == [
        ("JR5220", "product_code"),
        ("4067904494690", "barcode"),
    ]


def test_plan_is_stable_deduplicated_and_accepts_future_enriched_aliases():
    watch = {
        "raw_query": "Adidas JR5220",
        "brand": "adidas",
        "model": "JR5220",
        "source_identifiers": {"product_code": "jr5220"},
        "enriched_aliases": [
            "adidas Terrex Agravic Speed JR5220",
            "ADIDAS TERREX AGRAVIC SPEED JR5220",
        ],
    }

    first = build_search_plan(watch)
    second = build_search_plan(watch)

    assert first == second
    assert [item.query for item in first] == [
        "jr5220",
        "adidas jr5220",
        "adidas Terrex Agravic Speed JR5220",
    ]


def test_watch_identity_includes_identifiers_that_are_not_in_ocr_text():
    identity = _watch_identity(
        {
            "raw_query": "TRAIL RUNNING",
            "source_identifiers": {
                "product_code": "JR5220",
                "barcode": "4067904494690",
            },
        }
    )

    assert "JR5220" in identity.model_codes
    assert "4067904494690" in identity.gtins


def test_candidate_identity_recovers_product_code_from_official_product_url():
    identity = _candidate_identity(
        {
            "title": "Terrex Agravic Speed Arazi Kosu Ayakkabisi",
            "url": "https://www.adidas.com.tr/tr/terrex-agravic-speed-arazi-kosu-ayakkabisi/JR5220.html",
        },
        {"brand": "adidas"},
    )

    assert "JR5220" in identity.model_codes


@pytest.mark.asyncio
async def test_engine_plan_advances_to_barcode_and_records_attempt_evidence(monkeypatch):
    engine = SimpleNamespace(name="Test Store")
    plan = [
        SearchQuery("JR5220", "product_code", True),
        SearchQuery("4067904494690", "barcode", True),
    ]
    direct_search = AsyncMock(
        side_effect=[
            {"store": "Test Store", "status": "ok", "results": [], "engine": "static"},
            {
                "store": "Test Store",
                "status": "ok",
                "results": [{"title": "adidas Terrex Agravic Speed JR5220", "url": "https://test/p/1"}],
                "engine": "static",
            },
        ]
    )
    fallback = AsyncMock(return_value=[])
    monkeypatch.setattr(discovery_service, "_search_engine", direct_search)
    monkeypatch.setattr(discovery_service, "_layered_fallback", fallback)

    result = await _search_engine_plan(engine, plan)

    assert result["status"] == "ok"
    assert result["matched_query"] == "4067904494690"
    assert result["results"][0]["discovery_query_kind"] == "barcode"
    assert result["query_attempts"] == [
        {
            "query": "JR5220",
            "kind": "product_code",
                "exact_identifier": True,
                "status": "ok",
                "direct_status": "ok",
            "direct_count": 0,
            "fallback_count": 0,
            "engine": "static",
        },
        {
            "query": "4067904494690",
            "kind": "barcode",
                "exact_identifier": True,
                "status": "ok",
                "direct_status": "ok",
            "direct_count": 1,
            "fallback_count": 0,
            "engine": "static",
        },
    ]
    assert [call.args[1] for call in fallback.await_args_list] == ["JR5220"]


@pytest.mark.asyncio
async def test_engine_plan_uses_same_exact_query_for_layered_fallback(monkeypatch):
    engine = SimpleNamespace(name="Test Store")
    direct_search = AsyncMock(
        return_value={"store": "Test Store", "status": "blocked", "results": [], "engine": "static"}
    )
    fallback = AsyncMock(
        return_value=[{"title": "JR5220", "url": "https://test/p/jr5220", "discovery_source": "sitemap"}]
    )
    monkeypatch.setattr(discovery_service, "_search_engine", direct_search)
    monkeypatch.setattr(discovery_service, "_layered_fallback", fallback)

    result = await _search_engine_plan(engine, [SearchQuery("JR5220", "product_code", True)])

    fallback.assert_awaited_once_with(engine, "JR5220")
    assert result["status"] == "ok"
    assert result["fallback"] is True
    assert result["query_attempts"][0]["fallback_count"] == 1


@pytest.mark.asyncio
async def test_open_circuit_still_allows_safe_exact_identifier_fallback(monkeypatch):
    engine = SimpleNamespace(name="Test Store")
    fallback = AsyncMock(
        return_value=[
            {
                "title": "Terrex Agravic Speed JR5220",
                "url": "https://test/p/JR5220.html",
                "discovery_source": "sitemap",
            }
        ]
    )
    monkeypatch.setattr(discovery_service, "_layered_fallback", fallback)

    result = await _fallback_engine_plan(
        engine,
        [SearchQuery("JR5220", "product_code", True)],
        circuit={"retry_at": None, "last_error": "HTTP 429"},
    )

    fallback.assert_awaited_once_with(engine, "JR5220")
    assert result["status"] == "ok"
    assert result["circuit_fallback"] is True
    assert result["results"][0]["discovery_query_kind"] == "product_code"


def test_coverage_summary_never_calls_a_mostly_deferred_run_completed():
    result = _coverage_summary(
        [
            {"status": "ok"},
            {"status": "ok"},
            *[{"status": "deferred"} for _ in range(25)],
        ]
    )

    assert result == {
        "status": "partial",
        "selected_store_count": 27,
        "searched_store_count": 2,
        "successful_store_count": 2,
        "not_found_store_count": 0,
        "completed_store_count": 2,
        "deferred_store_count": 25,
        "failed_store_count": 0,
        "coverage_percent": 7.4,
        "attempted_percent": 7.4,
    }


def test_coverage_does_not_call_an_all_blocked_run_covered():
    result = _coverage_summary([{"status": "blocked"} for _ in range(27)])

    assert result["status"] == "failed"
    assert result["coverage_percent"] == 0.0
    assert result["attempted_percent"] == 100.0


def test_definitive_not_found_is_a_completed_store_outcome():
    result = _coverage_summary([{"status": "not_found"}, {"status": "ok"}])

    assert result["status"] == "completed"
    assert result["completed_store_count"] == 2
    assert result["not_found_store_count"] == 1
    assert result["coverage_percent"] == 100.0


def test_local_runtime_and_network_failures_are_not_mislabeled_as_store_blocks():
    assert _transport_error_status("[WinError 5] Access denied") == "runtime_error"
    assert _transport_error_status("All connection attempts failed") == "network_error"
    assert _transport_error_status("HTTP 403") == "blocked"


@pytest.mark.asyncio
async def test_engine_plan_does_not_repeat_direct_requests_after_access_block(monkeypatch):
    engine = SimpleNamespace(name="Protected Store")
    direct_search = AsyncMock(
        return_value={"store": engine.name, "status": "blocked", "results": [], "engine": "static"}
    )
    fallback = AsyncMock(return_value=[])
    monkeypatch.setattr(discovery_service, "_search_engine", direct_search)
    monkeypatch.setattr(discovery_service, "_layered_fallback", fallback)
    plan = [
        SearchQuery("JR5220", "product_code", True),
        SearchQuery("4067904494690", "barcode", True),
    ]

    result = await _search_engine_plan(engine, plan)

    assert direct_search.await_count == 1
    assert fallback.await_count == 2
    assert result["status"] == "blocked"
    assert result["query_attempts"][1]["engine"] == "layered_only"
    assert result["query_attempts"][1]["direct_skipped_reason"] == "blocked"


@pytest.mark.asyncio
async def test_engine_plan_does_not_repeat_direct_requests_after_capacity_timeout(monkeypatch):
    engine = SimpleNamespace(name="Busy Browser Store")
    direct_search = AsyncMock(
        return_value={
            "store": engine.name,
            "status": "capacity_timeout",
            "results": [],
            "engine": "browser_pool",
        }
    )
    fallback = AsyncMock(return_value=[])
    monkeypatch.setattr(discovery_service, "_search_engine", direct_search)
    monkeypatch.setattr(discovery_service, "_layered_fallback", fallback)

    result = await _search_engine_plan(
        engine,
        [
            SearchQuery("JR5220", "product_code", True),
            SearchQuery("4067904494690", "barcode", True),
        ],
    )

    assert direct_search.await_count == 1
    assert fallback.await_count == 2
    assert result["status"] == "capacity_timeout"
    assert result["query_attempts"][1]["direct_skipped_reason"] == "capacity_timeout"
