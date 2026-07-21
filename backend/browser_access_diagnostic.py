"""Standards-based browser access diagnostic for selected public stores.

This probe deliberately does not alter browser fingerprints, rotate identities,
use proxies, solve CAPTCHAs, or retry access-control responses.  Its output is
intended for store-engine health reports.
"""

import asyncio
import json
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from browser_runtime import shutdown_browser_pool
from engines import ENGINES, _looks_like_bot_challenge


TARGETS = {
    "decathlon": "kalenji",
    "adidas": "ultraboost",
}


def _engine(slug):
    return next(item for item in ENGINES if item.slug == slug)


async def probe(slug, query):
    engine = _engine(slug)
    url = engine.search_path.format(q=quote_plus(query))
    result = {
        "store": engine.name,
        "slug": slug,
        "url": url,
        "mode": "standard_playwright",
        "stealth": False,
        "identity_masking": False,
        "outcome": "error",
        "detail": None,
        "html_bytes": 0,
        "parsed_products": 0,
    }
    try:
        html = await engine.fetch_with_browser(url)
    except Exception as exc:
        detail = str(exc)
        result["detail"] = detail
        if any(token in detail.upper() for token in ("HTTP 401", "HTTP 403", "HTTP 429", "CAPTCHA")):
            result["outcome"] = "blocked"
        return result

    result["html_bytes"] = len(html.encode("utf-8"))
    if _looks_like_bot_challenge(html):
        result["outcome"] = "blocked"
        result["detail"] = "access_challenge"
        return result

    parsed = engine.parse_search(html, query, url)
    result["parsed_products"] = len(parsed)
    if slug == "decathlon":
        payload = engine._extract_dkt_payload(html)
        result["dkt_components"] = [
            str(item.get("type"))
            for item in engine._dkt_components(payload)
            if isinstance(item, dict)
        ]
        soup = BeautifulSoup(html, "lxml")
        result["product_link_samples"] = list(
            dict.fromkeys(
                str(anchor.get("href"))
                for anchor in soup.find_all("a", href=True)
                if "R-p-" in str(anchor.get("href"))
            )
        )[:5]
    result["outcome"] = "accessible"
    result["detail"] = "public_page_rendered"
    return result


async def probe_exact_identifier(slug, code):
    engine = _engine(slug)
    resolver = getattr(engine, "exact_identifier_candidates", None)
    if not callable(resolver):
        return {"store": engine.name, "slug": slug, "code": code, "outcome": "unsupported"}
    try:
        candidates = await resolver(code)
    except Exception as exc:
        return {
            "store": engine.name,
            "slug": slug,
            "code": code,
            "mode": "official_exact_code",
            "outcome": "error",
            "detail": str(exc)[:180],
        }
    return {
        "store": engine.name,
        "slug": slug,
        "code": code,
        "mode": "official_exact_code",
        "outcome": "accessible" if candidates else "not_found",
        "candidates": candidates,
    }


async def main():
    try:
        results = await asyncio.gather(
            *(probe(slug, query) for slug, query in TARGETS.items())
        )
        results.append(await probe_exact_identifier("adidas", "JR5220"))
        print(json.dumps(results, ensure_ascii=False, indent=2))
    finally:
        await shutdown_browser_pool()


if __name__ == "__main__":
    asyncio.run(main())
