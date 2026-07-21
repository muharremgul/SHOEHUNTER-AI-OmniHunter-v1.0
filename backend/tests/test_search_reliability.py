import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from browser_search import rendered_search_batch  # noqa: E402
from discovery_service import _run_fair_store_searches  # noqa: E402
from stores.amazon import AmazonEngine  # noqa: E402
from stores.marketplaces import N11Engine  # noqa: E402
from stores.trendyol import TrendyolEngine  # noqa: E402

from stores.decathlon import DecathlonEngine  # noqa: E402


class FakeBrowserEngine:
    def __init__(self, name, delay):
        self.name = name
        self.delay = delay

    async def fetch_with_browser(self, _url):
        await asyncio.sleep(self.delay)
        return "<html>ok</html>"

    def parse_search(self, _html, _query, url):
        return [{"title": self.name, "url": url, "score": 100}]


@pytest.mark.asyncio
async def test_browser_batch_preserves_completed_stores_when_deadline_expires():
    fast_one = FakeBrowserEngine("fast-one", 0.01)
    slow = FakeBrowserEngine("slow", 0.2)
    fast_two = FakeBrowserEngine("fast-two", 0.01)

    results = await rendered_search_batch(
        [
            (fast_one, "https://example.test/1", "x"),
            (slow, "https://example.test/2", "x"),
            (fast_two, "https://example.test/3", "x"),
        ],
        overall_timeout_seconds=0.08,
    )

    assert [item["store"] for item in results] == ["fast-one", "slow", "fast-two"]
    assert results[0]["status"] == "ok"
    assert results[1]["status"] == "capacity_timeout"
    assert results[2]["status"] == "ok"


@pytest.mark.asyncio
async def test_browser_store_queue_preserves_order_and_limits_concurrency():
    class QueueEngine:
        def __init__(self, slug, requires_browser):
            self.slug = slug
            self.name = slug
            self._requires_browser = requires_browser

        def capabilities(self):
            return {"requires_browser": self._requires_browser}

    engines = [
        QueueEngine("browser-1", True),
        QueueEngine("static-1", False),
        QueueEngine("browser-2", True),
        QueueEngine("browser-3", True),
        QueueEngine("browser-4", True),
    ]
    active_browser = 0
    max_active_browser = 0

    async def search_one(engine):
        nonlocal active_browser, max_active_browser
        if engine._requires_browser:
            active_browser += 1
            max_active_browser = max(max_active_browser, active_browser)
        await asyncio.sleep(0.01)
        if engine._requires_browser:
            active_browser -= 1
        return engine, {"status": "ok"}

    results = await _run_fair_store_searches(engines, search_one)

    assert [engine.slug for engine, _ in results] == [engine.slug for engine in engines]
    assert max_active_browser <= 3


@pytest.mark.asyncio
async def test_n11_search_uses_static_html_before_browser_fallback():
    engine = N11Engine()
    engine.fetch = AsyncMock(
        return_value="""
        <li class="column">
          <a href="/urun/nike-zegama-trail-2-siyah-123456" title="Nike Zegama Trail 2 Siyah">
            Nike Zegama Trail 2 Siyah
          </a>
        </li>
        """
    )
    engine.fetch_with_browser = AsyncMock(return_value="browser should not be used")

    results = await engine.search("Nike Zegama 2")

    assert engine.js_search is False
    assert engine.search_browser_fallback is True
    assert len(results) == 1
    assert "zegama trail 2" in results[0]["title"].lower()
    engine.fetch_with_browser.assert_not_awaited()


def test_n11_duplicate_card_titles_are_recovered_from_each_product_url():
    engine = N11Engine()
    html = """
    <ul>
      <li class="column">
        <a href="/urun/nike-zegama-trail-2-siyah-123456" title="Nike Zegama Trail 2 Ortak Baslik">
          Nike Zegama Trail 2 Ortak Baslik
        </a>
      </li>
      <li class="column">
        <a href="/urun/nike-zegama-trail-2-mavi-123457" title="Nike Zegama Trail 2 Ortak Baslik">
          Nike Zegama Trail 2 Ortak Baslik
        </a>
      </li>
    </ul>
    """

    results = engine.parse_search(html, "Nike Zegama 2", "https://www.n11.com/arama?q=zegama")

    assert len(results) == 2
    assert {item["title"] for item in results} == {
        "nike zegama trail 2 siyah",
        "nike zegama trail 2 mavi",
    }


def test_amazon_search_deduplicates_ref_paths_by_asin():
    engine = AmazonEngine()
    html = """
    <div data-component-type="s-search-result" data-asin="B097NQRKVK">
      <h2><a class="a-link-normal" href="/Nike-Zegama/dp/B097NQRKVK/ref=sr_1_2"><span>Nike Zegama Trail 2</span></a></h2>
    </div>
    <div data-component-type="s-search-result" data-asin="B097NQRKVK">
      <h2><a class="a-link-normal" href="/Nike-Zegama/dp/B097NQRKVK/ref=sr_1_7"><span>Nike Zegama Trail 2</span></a></h2>
    </div>
    """

    results = engine.parse_search(html, "Nike Zegama 2", "https://www.amazon.com.tr/s?k=zegama")

    assert len(results) == 1
    assert results[0]["url"] == "https://www.amazon.com.tr/dp/B097NQRKVK"
    assert engine.search_browser_fallback is True
    assert engine.search_timeout_seconds >= 55


def test_amazon_uses_product_slug_when_visible_title_is_only_the_brand():
    engine = AmazonEngine()
    html = """
    <div data-component-type="s-search-result" data-asin="B097NQRKVK">
      <h2><a class="a-link-normal" href="/Nike-Zegama-Trail-2/dp/B097NQRKVK/ref=sr_1_2"><span>Nike</span></a></h2>
    </div>
    <div data-component-type="s-search-result" data-asin="B012345678">
      <h2><a class="a-link-normal" href="/Nike-Initiator-2/dp/B012345678/ref=sr_1_3"><span>Nike</span></a></h2>
    </div>
    """

    results = engine.parse_search(html, "Nike Zegama 2", "https://www.amazon.com.tr/s?k=zegama")

    assert len(results) == 1
    assert results[0]["url"] == "https://www.amazon.com.tr/dp/B097NQRKVK"
    assert "Zegama Trail 2" in results[0]["title"]


@pytest.mark.asyncio
async def test_amazon_empty_static_search_gets_one_browser_render_fallback():
    engine = AmazonEngine()
    engine.fetch = AsyncMock(return_value="<html><body>empty static shell</body></html>")
    engine.fetch_with_browser = AsyncMock(
        return_value="""
        <div data-component-type="s-search-result" data-asin="B097NQRKVK">
          <h2><a class="a-link-normal" href="/Nike-Zegama-Trail-2/dp/B097NQRKVK/ref=sr_1_2">
            <span>Nike Zegama Trail 2</span>
          </a></h2>
        </div>
        """
    )

    results = await engine.search("Nike Zegama 2")

    assert len(results) == 1
    assert results[0]["url"] == "https://www.amazon.com.tr/dp/B097NQRKVK"
    engine.fetch_with_browser.assert_awaited_once()


@pytest.mark.asyncio
async def test_decathlon_search_uses_standard_browser_queue():
    engine = DecathlonEngine()
    engine.fetch_with_browser = AsyncMock(
        return_value="""
        <article class="product-card">
          <a href="/p/kadin-kosu-ayakkabisi-run-100/_/R-p-123456" title="Kalenji Run 100">
            <h2>Kalenji Run 100</h2>
            <span class="product-price">1.299,99 TL</span>
          </a>
        </article>
        """
    )

    batch = await rendered_search_batch(
        [(engine, engine.search_path.format(q="Kalenji+Run+100"), "Kalenji Run 100")]
    )
    results = batch[0]["results"]

    assert engine.js_search is True
    assert engine.use_browser is True
    assert engine.search_browser_fallback is False
    assert engine.capabilities()["discovery_method"] == "browser+sitemap"
    assert len(results) == 1
    assert results[0]["url"].startswith("https://www.decathlon.com.tr/")
    engine.fetch_with_browser.assert_awaited_once()


@pytest.mark.asyncio
async def test_decathlon_browser_challenge_is_reported_without_retry():
    engine = DecathlonEngine()
    engine.fetch_with_browser = AsyncMock(
        return_value="<html><body><div id='sec-if-cpt-container'>captcha</div></body></html>"
    )

    batch = await rendered_search_batch(
        [(engine, engine.search_path.format(q="Kalenji+Run+100"), "Kalenji Run 100")]
    )

    assert batch[0]["status"] == "blocked"
    assert batch[0]["results"] == []
    engine.fetch_with_browser.assert_awaited_once()


def test_trendyol_recovers_each_title_from_distinct_product_slug():
    engine = TrendyolEngine()
    html = """
    <div class="p-card-wrppr">
      <a href="/nike/zoom-x-zegama-trail-2-siyah-p-111" title="Nike Zegama Trail 2 Ortak Baslik"></a>
    </div>
    <div class="p-card-wrppr">
      <a href="/nike/zoom-x-zegama-trail-2-beyaz-p-222" title="Nike Zegama Trail 2 Ortak Baslik"></a>
    </div>
    """

    results = engine.parse_search(html, "Nike Zegama 2", "https://www.trendyol.com/sr?q=zegama")

    assert len(results) == 2
    assert {item["title"] for item in results} == {
        "zoom x zegama trail 2 siyah",
        "zoom x zegama trail 2 beyaz",
    }
