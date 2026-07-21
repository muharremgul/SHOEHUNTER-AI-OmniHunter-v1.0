import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import browser_access_diagnostic as diagnostic  # noqa: E402


class FakeEngine:
    name = "Test Store"
    slug = "test"
    search_path = "https://example.test/search?q={q}"

    def __init__(self, html="", error=None):
        self.html = html
        self.error = error
        self.fetch_with_browser = AsyncMock(side_effect=error, return_value=html)

    def parse_search(self, _html, _query, _url):
        return [{"title": "Example"}]


@pytest.mark.asyncio
async def test_probe_reports_accessible_page_without_stealth(monkeypatch):
    engine = FakeEngine("<html><body>public product page</body></html>")
    monkeypatch.setattr(diagnostic, "_engine", lambda _slug: engine)

    result = await diagnostic.probe("test", "shoe")

    assert result["outcome"] == "accessible"
    assert result["parsed_products"] == 1
    assert result["stealth"] is False
    assert result["identity_masking"] is False


@pytest.mark.asyncio
async def test_probe_reports_403_as_blocked_without_retry(monkeypatch):
    engine = FakeEngine(error=RuntimeError("HTTP 403"))
    monkeypatch.setattr(diagnostic, "_engine", lambda _slug: engine)

    result = await diagnostic.probe("test", "shoe")

    assert result["outcome"] == "blocked"
    assert result["detail"] == "HTTP 403"
    engine.fetch_with_browser.assert_awaited_once()


@pytest.mark.asyncio
async def test_probe_reports_challenge_page_as_blocked(monkeypatch):
    engine = FakeEngine("<html><div id='sec-if-cpt-container'>captcha</div></html>")
    monkeypatch.setattr(diagnostic, "_engine", lambda _slug: engine)

    result = await diagnostic.probe("test", "shoe")

    assert result["outcome"] == "blocked"
    assert result["detail"] == "access_challenge"
    assert result["parsed_products"] == 0
