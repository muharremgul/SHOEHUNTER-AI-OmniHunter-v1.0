import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import discovery_sources  # noqa: E402
from discovery_sources import (  # noqa: E402
    _sitemap_candidate_title,
    _title_from_product_url,
    catalog_candidates,
    layered_url_discovery,
    official_exact_candidates,
)
from product_identity import identity_from_title, match_identities  # noqa: E402
from stores.outdoor import ColumbiaEngine  # noqa: E402

from stores.adidas import AdidasEngine  # noqa: E402


def test_sitemap_title_keeps_adidas_product_slug_and_model_code():
    url = "https://www.adidas.com.tr/tr/adizero-evo-sl-ayakkabi/JH6206.html"

    title = _title_from_product_url(url)

    assert title == "adizero evo sl ayakkabi"


def test_adidas_sitemap_title_matches_evo_sl_watch():
    expected = identity_from_title("adidas adizero evo sl", brand="adidas")
    candidate = identity_from_title(
        _sitemap_candidate_title(
            SimpleNamespace(sitemap_title_prefix="adidas"),
            "https://www.adidas.com.tr/tr/adizero-evo-sl-ayakkabi/JH6206.html",
        ),
        brand="adidas",
    )

    match = match_identities(expected, candidate)

    assert match["decision"] == "auto"
    assert match["confidence"] >= 0.9


@pytest.mark.asyncio
async def test_verified_official_catalog_seed_returns_price_and_image(monkeypatch):
    engine = ColumbiaEngine()
    engine.fetch = AsyncMock(
        return_value="""
        <article class="product-card">
          <a href="/siyah-firecamp-iii-waterproof-erkek-ayakkabi-p-42159"
             title="Firecamp III Waterproof Erkek Ayakkabi">
            <img src="/images/firecamp.jpg" alt="Firecamp III Waterproof Erkek Ayakkabi">
            <span class="product-price">8.999,90 TL</span>
          </a>
        </article>
        """
    )

    async def allow_robots(_engine, _url):
        return True, []

    async def skip_dns(_url, _domains):
        return None

    monkeypatch.setattr(discovery_sources, "robots_policy", allow_robots)
    monkeypatch.setattr(discovery_sources, "validate_remote_url", skip_dns)
    discovery_sources._catalog_cache.clear()

    results = await catalog_candidates(engine, "Firecamp III", limit=1)

    assert results == [
        {
            "url": "https://www.columbia.com.tr/siyah-firecamp-iii-waterproof-erkek-ayakkabi-p-42159",
            "title": "Firecamp III Waterproof Erkek Ayakkabi",
            "source": "official_catalog",
            "image": "https://www.columbia.com.tr/images/firecamp.jpg",
            "price": 8999.9,
        }
    ]
    engine.fetch.assert_awaited_once()


@pytest.mark.asyncio
async def test_official_catalog_seed_stops_when_robots_disallows(monkeypatch):
    engine = ColumbiaEngine()
    engine.fetch = AsyncMock(return_value="should not be fetched")

    async def deny_robots(_engine, _url):
        return False, []

    async def skip_dns(_url, _domains):
        return None

    monkeypatch.setattr(discovery_sources, "robots_policy", deny_robots)
    monkeypatch.setattr(discovery_sources, "validate_remote_url", skip_dns)
    discovery_sources._catalog_cache.clear()

    assert await catalog_candidates(engine, "Firecamp III", limit=1) == []
    engine.fetch.assert_not_awaited()


@pytest.mark.asyncio
async def test_adidas_exact_style_code_uses_verified_public_redirect(monkeypatch):
    engine = AdidasEngine()
    engine.fetch_with_browser = AsyncMock(
        return_value='''
        <html><head>
          <meta property="og:title" content="Terrex Agravic Speed Trail Running Shoes">
          <meta property="product:price:amount" content="4399">
        </head><body>Product code: JR5220</body></html>
        '''
    )

    async def skip_dns(_url, _domains, **_kwargs):
        return None

    monkeypatch.setattr(discovery_sources, "validate_remote_url", skip_dns)
    results = await official_exact_candidates(engine, "JR5220")

    assert results[0]["url"] == "https://www.adidas.com.tr/en/JR5220.html"
    assert results[0]["title"] == "Terrex Agravic Speed Trail Running Shoes"
    assert results[0]["source"] == "official_exact_code"
    engine.fetch_with_browser.assert_awaited_once()


@pytest.mark.asyncio
async def test_adidas_exact_style_code_keeps_a_reviewable_official_route_on_403(monkeypatch):
    engine = AdidasEngine()
    engine.fetch_with_browser = AsyncMock(side_effect=RuntimeError("HTTP 403"))

    async def skip_dns(_url, _domains, **_kwargs):
        return None

    monkeypatch.setattr(discovery_sources, "validate_remote_url", skip_dns)
    results = await official_exact_candidates(engine, "JR5220")

    assert results == [
        {
            "title": "adidas JR5220",
            "url": "https://www.adidas.com.tr/en/JR5220.html",
            "price": None,
            "image": None,
            "source": "official_exact_code",
            "verification_required": True,
        }
    ]


@pytest.mark.asyncio
async def test_layered_discovery_preserves_fast_source_when_another_source_fails(monkeypatch):
    engine = AdidasEngine()
    monkeypatch.setattr(
        discovery_sources,
        "official_exact_candidates",
        AsyncMock(
            return_value=[
                {
                    "title": "adidas JR5220",
                    "url": "https://www.adidas.com.tr/en/JR5220.html",
                    "source": "official_exact_code",
                }
            ]
        ),
    )
    monkeypatch.setattr(
        discovery_sources,
        "sitemap_candidates",
        AsyncMock(side_effect=RuntimeError("broken sitemap")),
    )
    monkeypatch.setattr(discovery_sources, "brave_candidates", AsyncMock(return_value=[]))
    monkeypatch.setattr(discovery_sources, "catalog_candidates", AsyncMock(return_value=[]))

    results = await layered_url_discovery(engine, "JR5220")

    assert [item["url"] for item in results] == ["https://www.adidas.com.tr/en/JR5220.html"]
