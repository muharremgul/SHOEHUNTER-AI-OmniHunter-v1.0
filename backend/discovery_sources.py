import asyncio
import os
import re
import time
import urllib.robotparser
import xml.etree.ElementTree as ET
from urllib.parse import unquote, urlparse

import httpx
from engines import _looks_like_bot_challenge
from product_identity import canonicalize_product_url, tokenize
from security import validate_remote_url

_robots_cache = {}
_sitemap_cache = {}
_catalog_cache = {}
CACHE_SECONDS = 6 * 3600
EXACT_SOURCE_BUDGET_SECONDS = max(8, int(os.environ.get("EXACT_SOURCE_BUDGET_SECONDS", "35")))
SITEMAP_SOURCE_BUDGET_SECONDS = max(8, int(os.environ.get("SITEMAP_SOURCE_BUDGET_SECONDS", "30")))
CATALOG_SOURCE_BUDGET_SECONDS = max(8, int(os.environ.get("CATALOG_SOURCE_BUDGET_SECONDS", "25")))
WEB_SOURCE_BUDGET_SECONDS = max(8, int(os.environ.get("WEB_SOURCE_BUDGET_SECONDS", "20")))


async def robots_policy(engine, target_url):
    root = f"https://{urlparse(target_url).hostname}"
    cache = _robots_cache.get(root)
    if cache and time.time() - cache[0] < CACHE_SECONDS:
        parser, sitemaps = cache[1], cache[2]
        return parser.can_fetch("ShoeHunterAI", target_url), sitemaps
    robots_url = root + "/robots.txt"
    parser = urllib.robotparser.RobotFileParser()
    parser.set_url(robots_url)
    sitemaps = []
    try:
        text = await engine.fetch(robots_url, max_retries=1, timeout_seconds=10)
        parser.parse(text.splitlines())
        sitemaps = [
            line.split(":", 1)[1].strip()
            for line in text.splitlines()
            if line.lower().startswith("sitemap:") and ":" in line
        ]
    except Exception:
        parser.parse(["User-agent: *", "Allow: /"])
    _robots_cache[root] = (time.time(), parser, sitemaps)
    return parser.can_fetch("ShoeHunterAI", target_url), sitemaps


def _xml_locations(xml_text):
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return [], False
    is_index = root.tag.lower().endswith("sitemapindex")
    locations = []
    for element in root.iter():
        if element.tag.lower().endswith("loc") and element.text:
            locations.append(element.text.strip())
    return locations, is_index


def _url_matches_query(url, query):
    slug_tokens = set(tokenize(urlparse(url).path.replace("-", " ").replace("_", " ")))
    query_tokens = [token for token in tokenize(query) if len(token) > 1]
    if not query_tokens:
        return False
    required = min(2, len(query_tokens))
    return len(slug_tokens & set(query_tokens)) >= required


def _title_from_product_url(url):
    parts = [unquote(part) for part in urlparse(url).path.split("/") if part]
    if not parts:
        return ""
    last = re.sub(r"\.(?:html?|aspx?)$", "", parts[-1], flags=re.IGNORECASE)
    if len(parts) > 1 and re.fullmatch(r"(?=.*[A-Za-z])(?=.*\d)[A-Za-z0-9._-]{4,24}", last):
        last = parts[-2]
    return last.replace("-", " ").replace("_", " ").strip()


def _sitemap_candidate_title(engine, url):
    title = _title_from_product_url(url)
    prefix = str(getattr(engine, "sitemap_title_prefix", "") or "").strip()
    if prefix and not set(tokenize(prefix)).issubset(set(tokenize(title))):
        title = f"{prefix} {title}".strip()
    return title


async def sitemap_candidates(engine, query, limit=30):
    base = f"https://{engine.domains[0]}"
    allowed, listed_sitemaps = await robots_policy(engine, base + "/")
    if not allowed:
        return []
    sitemap_urls = listed_sitemaps or [base + "/sitemap.xml"]
    output = []
    visited = set()
    queue = list(sitemap_urls[:10])
    max_sitemaps = min(10, max(3, limit))
    while queue and len(visited) < max_sitemaps and len(output) < limit:
        sitemap_url = queue.pop(0)
        if sitemap_url in visited:
            continue
        visited.add(sitemap_url)
        try:
            await validate_remote_url(sitemap_url, engine.domains)
            cache = _sitemap_cache.get(sitemap_url)
            if cache and time.time() - cache[0] < CACHE_SECONDS:
                xml_text = cache[1]
            else:
                xml_text = await engine.fetch(sitemap_url, max_retries=1, timeout_seconds=15)
                _sitemap_cache[sitemap_url] = (time.time(), xml_text)
            locations, is_index = _xml_locations(xml_text)
            if is_index:
                query_tokens = tokenize(query)
                ranked = sorted(
                    locations,
                    key=lambda item: -sum(token in item.lower() for token in query_tokens),
                )
                queue.extend(ranked[:10])
                continue
            for candidate in locations:
                if len(output) >= limit:
                    break
                if not engine.supports_url(candidate) or not engine.is_product_link(candidate):
                    continue
                if _url_matches_query(candidate, query):
                    output.append(
                        {
                            "url": canonicalize_product_url(candidate),
                            "title": _sitemap_candidate_title(engine, candidate),
                            "source": "sitemap",
                        }
                    )
        except Exception:
            continue
    unique = {item["url"]: item for item in output}
    return list(unique.values())[:limit]


async def brave_candidates(engine, query, limit=10):
    api_key = os.environ.get("BRAVE_SEARCH_API_KEY", "").strip()
    if not api_key:
        return []
    search_query = f'site:{engine.domains[0]} "{query}"'
    headers = {"Accept": "application/json", "X-Subscription-Token": api_key}
    params = {"q": search_query, "country": "TR", "search_lang": "tr", "count": min(20, limit * 2)}
    try:
        async with httpx.AsyncClient(
            timeout=15,
            trust_env=os.environ.get("SHOEHUNTER_TRUST_ENV_PROXY", "false").lower()
            in {"1", "true", "yes"},
        ) as client:
            response = await client.get("https://api.search.brave.com/res/v1/web/search", headers=headers, params=params)
            response.raise_for_status()
            payload = response.json()
    except Exception:
        return []
    output = []
    for item in ((payload.get("web") or {}).get("results") or []):
        url = canonicalize_product_url(item.get("url"))
        if not url or not engine.supports_url(url) or not engine.is_product_link(url):
            continue
        try:
            await validate_remote_url(url, engine.domains, resolve_dns=False)
        except Exception:
            continue
        output.append({"url": url, "title": item.get("title") or "", "source": "brave_url_discovery"})
        if len(output) >= limit:
            break
    return output


async def catalog_candidates(engine, query, limit=12):
    """Search verified public category seeds for stores without a stable query route."""

    output = []
    for catalog_url in tuple(getattr(engine, "catalog_seed_urls", ()) or ())[:4]:
        try:
            await validate_remote_url(catalog_url, engine.domains)
            allowed, _ = await robots_policy(engine, catalog_url)
            if not allowed:
                continue
            cache = _catalog_cache.get(catalog_url)
            if cache and time.time() - cache[0] < CACHE_SECONDS:
                html = cache[1]
            else:
                html = await engine.fetch(catalog_url, max_retries=1, timeout_seconds=18)
                if _looks_like_bot_challenge(html):
                    continue
                _catalog_cache[catalog_url] = (time.time(), html)
            for item in engine.parse_search(html, query, catalog_url):
                url = canonicalize_product_url(item.get("url"))
                if not url or not engine.supports_url(url) or not engine.is_product_link(url):
                    continue
                output.append(
                    {
                        "url": url,
                        "title": item.get("title") or "",
                        "source": "official_catalog",
                        "image": item.get("image"),
                        "price": item.get("price"),
                    }
                )
                if len(output) >= limit:
                    return output
        except Exception:
            continue
    return output


async def official_exact_candidates(engine, query, limit=4):
    """Ask a dedicated adapter for its verified official code route."""
    resolver = getattr(engine, "exact_identifier_candidates", None)
    if not callable(resolver):
        return []
    try:
        results = await resolver(query)
    except Exception:
        return []
    output = []
    for item in results or []:
        url = canonicalize_product_url(item.get("url"))
        if not url or not engine.supports_url(url) or not engine.is_product_link(url):
            continue
        try:
            await validate_remote_url(url, engine.domains, resolve_dns=False)
        except Exception:
            continue
        output.append({**item, "url": url, "source": item.get("source") or "official_exact_code"})
        if len(output) >= limit:
            break
    return output


async def layered_url_discovery(engine, query, limit=30):
    async def bounded(coro, seconds):
        try:
            return await asyncio.wait_for(coro, timeout=seconds)
        except Exception:
            # Every source is optional and isolated.  A slow sitemap or an
            # unavailable optional search provider must not erase results
            # already obtained from official code routes or public catalogs.
            return []

    exact_task = asyncio.create_task(
        bounded(official_exact_candidates(engine, query, limit=min(4, limit)), EXACT_SOURCE_BUDGET_SECONDS)
    )
    sitemap_task = asyncio.create_task(
        bounded(sitemap_candidates(engine, query, limit=limit), SITEMAP_SOURCE_BUDGET_SECONDS)
    )
    brave_task = asyncio.create_task(
        bounded(brave_candidates(engine, query, limit=min(10, limit)), WEB_SOURCE_BUDGET_SECONDS)
    )
    catalog_task = asyncio.create_task(
        bounded(catalog_candidates(engine, query, limit=min(12, limit)), CATALOG_SOURCE_BUDGET_SECONDS)
    )
    exact_results, sitemap_results, brave_results, catalog_results = await asyncio.gather(
        exact_task, sitemap_task, brave_task, catalog_task
    )
    combined = exact_results + catalog_results + sitemap_results + brave_results
    return list({item["url"]: item for item in combined}.values())[:limit]
