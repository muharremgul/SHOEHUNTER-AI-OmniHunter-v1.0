# Store adapters import the base classes in this module, so their registry
# imports intentionally live after the class definitions below.
# ruff: noqa: E402

import asyncio
import json
import os
import random
import re
import unicodedata
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from urllib.parse import quote_plus, urljoin, urlparse

import httpx
from browser_runtime import browser_pool
from bs4 import BeautifulSoup
from rapidfuzz import fuzz
from security import URLValidationError, validate_remote_url

HEADERS = {
    "User-Agent": os.environ.get(
        "CRAWLER_USER_AGENT",
        "Mozilla/5.0 (compatible; ShoeHunterAI/0.6; local price and stock monitor)",
    ),
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate",
}

MAX_RESPONSE_BYTES = max(1024 * 1024, int(os.environ.get("MAX_RESPONSE_BYTES", str(5 * 1024 * 1024))))
GLOBAL_FETCH_CONCURRENCY = max(1, int(os.environ.get("GLOBAL_FETCH_CONCURRENCY", "8")))
STORE_FETCH_CONCURRENCY = max(1, int(os.environ.get("STORE_FETCH_CONCURRENCY", "2")))
_GLOBAL_FETCH_SEMAPHORE = asyncio.Semaphore(GLOBAL_FETCH_CONCURRENCY)


@dataclass
class StoreCapabilities:
    search: bool = False
    product_detail: bool = True
    sizes: bool = False
    cart_price: bool = False
    variants: bool = False
    seller_data: bool = False
    requires_browser: bool = False
    discovery_method: str = "html"


def parse_price_text(text):
    if not text:
        return None
    t = str(text).upper().replace("TL", "").replace("\u20ba", "").strip()
    t = re.sub(r"[^\d.,]", "", t)
    if not t:
        return None
    if "," in t and "." in t:
        t = t.replace(".", "").replace(",", ".")
    elif "," in t:
        t = t.replace(",", ".")
    elif t.count(".") > 1:
        t = t.replace(".", "")
    else:
        parts = t.split(".")
        if len(parts) == 2 and len(parts[1]) == 3:
            t = t.replace(".", "")
    try:
        val = round(float(t), 2)
        return val if val > 0 else None
    except ValueError:
        return None


_CART_TEXT_RE = re.compile(r"\bsepet(?:te(?:ki)?|\s+fiyat(?:ı|i))\b", re.IGNORECASE)
_PRICE_FRAGMENT = r"(?:\d{1,3}(?:[.\s]\d{3})*(?:,\d{1,2})?|\d{2,6}(?:[.,]\d{1,2})?)"
_TL_PRICE_RE = re.compile(rf"({_PRICE_FRAGMENT})\s*(?:TL|₺)", re.IGNORECASE)
_EXPLICIT_CART_PRICE_RE = re.compile(
    rf"(?:sepetteki\s+son\s+fiyat|sepet\s+fiyat(?:ı|i)|sepette(?:\s+(?:net|öde))?)"
    rf"\s*[:\-]?\s*({_PRICE_FRAGMENT})\s*(?:TL|₺)",
    re.IGNORECASE,
)


def _normalise_offer_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _cart_condition_tags(value):
    """Return conditions that prevent an offer being treated as unconditional."""

    text = _normalise_offer_text(value).casefold()
    checks = (
        (
            "quantity",
            r"(?:\b\d+\s*(?:ve\s*)?(?:üzeri(?:ne|nde)?|üstü(?:ne|nde)?|ve\s+daha\s+fazla)\b|"
            r"\b\d+\s*(?:ürün(?:de|ler)?|adet(?:te)?)\b|\b\d+\s*al\s*\d+\s*öde\b)",
        ),
        ("membership", r"\b(?:üye(?:lere|lerine|lik|si)?|member|members|friends|club|hopi)\b"),
        ("code_or_coupon", r"\b(?:koduyla|kodunu|kampanya\s+kodu|indirim\s+kodu|kupon)\b"),
        ("app_only", r"\b(?:app['’]?e|uygulama|mobil)\b"),
        ("size", r"\bbeden(?:lerde|de|ler)?\b"),
        (
            "payment_method",
            r"\b(?:maximum|bonus|world|axess|paraf|bank(?:a)?|kredi\s+kartı|"
            r"kart(?:ı|a|lara|larda)\s+özel)\b",
        ),
        ("minimum_basket", rf"\b{_PRICE_FRAGMENT}\s*(?:tl|₺)\s*(?:ve\s*)?(?:üzeri|üstü)\b"),
        ("bundle", r"\b(?:birlikte\s+al|alışverişinle\s+birlikte|yanında)\b"),
        ("first_purchase", r"\b(?:ilk\s+alışveriş|ilk\s+sipariş)\b"),
    )
    return [name for name, pattern in checks if re.search(pattern, text, re.IGNORECASE)]


def _discount_percent(value):
    text = _normalise_offer_text(value)
    match = re.search(r"%\s*(\d{1,2}(?:[.,]\d+)?)", text)
    if not match:
        return None
    percent = float(match.group(1).replace(",", "."))
    return percent if 0 < percent < 100 else None


def _tl_prices(value):
    prices = []
    for match in _TL_PRICE_RE.finditer(_normalise_offer_text(value)):
        price = parse_price_text(match.group(1))
        if price and 50 < price < 200000:
            prices.append(price)
    return prices


def extract_json_ld_products(soup):
    products = []

    def visit(item):
        if isinstance(item, dict):
            item_type = item.get("@type")
            if item_type == "Product" or (isinstance(item_type, list) and "Product" in item_type):
                products.append(item)
            if isinstance(item.get("@graph"), list):
                for graph_item in item["@graph"]:
                    visit(graph_item)
            if isinstance(item.get("itemListElement"), list):
                for element in item["itemListElement"]:
                    visit(element.get("item") if isinstance(element, dict) else element)
        elif isinstance(item, list):
            for child in item:
                visit(child)

    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string or script.get_text()
        if not raw:
            continue
        try:
            data = json.loads(raw.strip())
        except (json.JSONDecodeError, ValueError):
            continue
        visit(data)
    return products


def _first_offer(offers):
    if isinstance(offers, dict):
        if isinstance(offers.get("offers"), list) and offers["offers"]:
            return offers["offers"][0]
        return offers
    if isinstance(offers, list) and offers:
        return offers[0]
    return None


def _finalize_stock_status(result):
    sizes = result.get("sizes") or []
    status = result.get("stock_status")
    if sizes:
        known_values = [size.get("in_stock") for size in sizes if size.get("in_stock") is not None]
        result["stock_count"] = sum(1 for value in known_values if value is True)
        if any(value is True for value in known_values):
            status = "in_stock"
        elif known_values and all(value is False for value in known_values) and len(known_values) == len(sizes):
            status = "out_of_stock"
    elif status not in {"in_stock", "out_of_stock", "unknown", "blocked", "not_found", "error"}:
        status = "in_stock" if result.get("in_stock") else "unknown"
    result["stock_status"] = status
    result["in_stock"] = status == "in_stock"
    result["availability"] = status
    return result


_SEARCH_BRAND_TOKENS = {
    "adidas",
    "asics",
    "brooks",
    "columbia",
    "hoka",
    "jordan",
    "kappa",
    "lacoste",
    "merrell",
    "mizuno",
    "newbalance",
    "nike",
    "northface",
    "on",
    "puma",
    "reebok",
    "salomon",
    "saucony",
    "skechers",
    "thenorthface",
    "timberland",
    "underarmour",
    "vans",
}
_SEARCH_NOISE_TOKENS = {
    "ayakkabi",
    "ayakkabisi",
    "bot",
    "erkek",
    "kadin",
    "kids",
    "kosu",
    "model",
    "shoe",
    "shoes",
    "sneaker",
    "sneakers",
    "spor",
    "urun",
}


def _search_tokens(value):
    text = str(value or "").replace("\u0131", "i").replace("\u0130", "I")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    return re.findall(r"[a-z0-9]+(?:\.[0-9]+)?", text)


def _score_result(title, query):
    title_text = (title or "").strip().lower()
    query_text = (query or "").strip().lower()
    if not title_text or not query_text:
        return 0

    query_tokens = list(dict.fromkeys(_search_tokens(query_text)))
    title_tokens = set(_search_tokens(title_text))
    if not query_tokens or not title_tokens:
        return 0

    # token_set_ratio considers a one-word subset an exact match.  On search
    # pages this made generic cards titled only "Nike" score 100 for
    # "Nike Zegama 2".  Require an actual model token and an exact generation
    # whenever the query supplies one, then let fuzzy scoring rank valid cards.
    model_tokens = [
        token
        for token in query_tokens
        if not token.isdigit()
        and token not in _SEARCH_BRAND_TOKENS
        and token not in _SEARCH_NOISE_TOKENS
    ]
    if model_tokens and not (set(model_tokens) & title_tokens):
        return 0

    generation_tokens = {token for token in query_tokens if token.isdigit() or re.fullmatch(r"v\d+", token)}
    if generation_tokens and not generation_tokens.issubset(title_tokens):
        return 0

    score = fuzz.token_set_ratio(query_text, title_text)
    coverage = sum(1 for token in query_tokens if token in title_tokens) / len(query_tokens)
    return round(min(score, coverage * 100))


def _looks_like_bot_challenge(html):
    if not html:
        return False
    lower = html[:8000].lower()
    return any(
        token in lower
        for token in [
            "sec-if-cpt-container",
            "scf-akamai",
            "powered and protected by",
            "cf-chl",
            "just a moment",
            "distil_r_captcha",
            "recaptcha",
        ]
    )


def _absolute_url(base_url, value):
    if not value:
        return None
    value = str(value).strip()
    value = value.replace("\\/", "/").replace("\\u002F", "/")
    if not value or value.startswith(("data:", "blob:")):
        return None
    if value.startswith("//"):
        return "https:" + value
    return urljoin(base_url, value)


def _clean_image_url(base_url, value):
    url = _absolute_url(base_url, value)
    if not url:
        return None
    lower = url.lower()
    bad_tokens = (
        "favicon",
        "logo.svg",
        "/logo",
        "sprite",
        "placeholder",
        "blank.gif",
        "loader",
    )
    if any(token in lower for token in bad_tokens):
        return None
    if lower.endswith(".svg") and "product" not in lower:
        return None
    return url


def _first_image_value(value):
    if not value:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        for item in value:
            found = _first_image_value(item)
            if found:
                return found
    if isinstance(value, dict):
        for key in ("url", "image", "contentUrl", "src"):
            found = _first_image_value(value.get(key))
            if found:
                return found
    return None


def _extract_meta_image(soup, base_url=None):
    meta_keys = (
        ("property", "og:image"),
        ("property", "og:image:url"),
        ("property", "og:image:secure_url"),
        ("property", "product:image"),
        ("name", "og:image"),
        ("name", "twitter:image"),
        ("name", "twitter:image:src"),
        ("name", "image"),
        ("itemprop", "image"),
        ("itemprop", "thumbnailUrl"),
    )
    for attr, key in meta_keys:
        tag = soup.find("meta", attrs={attr: key})
        image = _clean_image_url(base_url, tag.get("content") if tag else None)
        if image:
            return image

    for link in soup.find_all("link", href=True):
        rel = " ".join(link.get("rel") or []).lower()
        is_image_preload = "preload" in rel and str(link.get("as", "")).lower() == "image"
        if "image_src" in rel or is_image_preload:
            image = _clean_image_url(base_url, link.get("href"))
            if image:
                return image

    for sel in (
        "img[itemprop='image']",
        "picture img",
        ".product img",
        ".product-detail img",
        ".gallery img",
        "[class*='product'] img",
    ):
        img = soup.select_one(sel)
        if not img:
            continue
        for attr in ("src", "data-src", "data-original", "data-lazy", "data-image"):
            image = _clean_image_url(base_url, img.get(attr))
            if image:
                return image
        image = _clean_image_url(base_url, _first_srcset_url(img.get("srcset") or img.get("data-srcset")))
        if image:
            return image
    return None


def _first_srcset_url(value):
    if not value:
        return None
    first = str(value).split(",")[0].strip()
    return first.split(" ")[0] if first else None


def _nearest_product_card(anchor):
    selectors = [
        "[data-testid*='product']",
        "[data-test-id*='product']",
        "[class*='product']",
        "article",
        "li",
        "div",
    ]
    for selector in selectors:
        found = anchor.find_parent(selector)
        if found:
            return found
    return anchor


def _search_title_from_card(card, anchor):
    candidates = [
        anchor.get("aria-label"),
        anchor.get("title"),
    ]
    for selector in [
        "[data-testid*='title']",
        "[data-test-id*='title']",
        "[class*='product-name']",
        "[class*='product-title']",
        "[class*='product-card__title']",
        "[class*='name']",
        "h1",
        "h2",
        "h3",
        "h4",
    ]:
        el = card.select_one(selector)
        if el:
            candidates.append(el.get_text(" ", strip=True))
    img = card.find("img") or anchor.find("img")
    if img:
        candidates.extend([img.get("alt"), img.get("title")])
    candidates.append(anchor.get_text(" ", strip=True))
    candidates.append(card.get_text(" ", strip=True))
    for candidate in candidates:
        text = re.sub(r"\s+", " ", str(candidate or "")).strip()
        if len(text) >= 8:
            return text[:160]
    return ""


def _search_image_from_card(card, anchor, base_url):
    img = card.find("img") or anchor.find("img")
    if not img:
        return None
    for attr in ("src", "data-src", "data-original", "data-lazy", "data-image"):
        image = _absolute_url(base_url, img.get(attr))
        if image:
            return image
    image = _absolute_url(base_url, _first_srcset_url(img.get("srcset") or img.get("data-srcset")))
    return image


def _search_price_from_card(card):
    for selector in [
        "[data-price]",
        "[data-price-value]",
        "[class*='price']",
        "[class*='fiyat']",
        ".amount",
    ]:
        el = card.select_one(selector)
        if not el:
            continue
        raw = el.get("data-price") or el.get("data-price-value") or el.get_text(" ", strip=True)
        price = parse_price_text(raw)
        if price and 50 < price < 200000:
            return price
    return None


_PRICE_KEYS = {"price", "sellingprice", "saleprice", "discountedprice", "currentprice", "bestprice", "finalprice"}


def _collect_prices(obj, out, depth=0):
    if depth > 6 or len(out) >= 10:
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = str(k).lower().replace("_", "")
            if key in _PRICE_KEYS:
                if isinstance(v, (int, float)) and 50 < v < 200000:
                    out.append(float(v))
                elif isinstance(v, str):
                    p = parse_price_text(v)
                    if p and 50 < p < 200000:
                        out.append(p)
            elif isinstance(v, (dict, list)):
                _collect_prices(v, out, depth + 1)
    elif isinstance(obj, list):
        for item in obj[:25]:
            _collect_prices(item, out, depth + 1)


def extract_embedded_prices(soup):
    """__NEXT_DATA__ / __NUXT__ / dataLayer / window state icinden fiyat adaylari."""
    out = []
    next_data = soup.find("script", id="__NEXT_DATA__")
    if next_data and (next_data.string or "").strip():
        try:
            _collect_prices(json.loads(next_data.string), out)
        except (json.JSONDecodeError, ValueError):
            pass
    if not out:
        pattern = re.compile(
            r'"(?:selling_?[Pp]rice|sale[Pp]rice|discounted[Pp]rice|current[Pp]rice|best[Pp]rice)"\s*:\s*"?([\d.,]+)'
        )
        for script in soup.find_all("script"):
            text = script.string or ""
            if not text or len(text) > 500000:
                continue
            if "__NUXT__" in text or "dataLayer" in text or "INITIAL_STATE" in text or "sellingPrice" in text:
                for m in pattern.findall(text)[:8]:
                    p = parse_price_text(m)
                    if p and 50 < p < 200000:
                        out.append(p)
                if out:
                    break
    return out


def _extract_variant_urls(soup, current_url):
    """Sayfadaki renk varyasyonu linklerini toplar (mevcut URL haric)."""
    current_path = urlparse(current_url).path.rstrip("/")
    current_domain = urlparse(current_url).netloc.replace("www.", "")
    seen = set()
    variant_urls = []

    # 1) Bilinen CSS siniflarindaki linkleri tara
    variant_selectors = [
        ".variant.-color-variant a[href]",
        ".variant__color-options a[href]",
        ".color-options a[href]",
        ".product-colors a[href]",
        ".js-variant-color[href]",
        "[class*='color-variant'] a[href]",
        "[class*='renk'] a[href]",
    ]
    for sel in variant_selectors:
        for a_tag in soup.select(sel):
            href = a_tag.get("href", "")
            if not href or href.startswith(("#", "javascript")):
                continue
            full = urljoin(current_url, href).split("?")[0].rstrip("/")
            path = urlparse(full).path.rstrip("/")
            domain = urlparse(full).netloc.replace("www.", "")
            if domain != current_domain:
                continue
            if path == current_path:
                continue
            if full not in seen:
                seen.add(full)
                variant_urls.append(full)
        if variant_urls:
            break  # Ilk basarili selektorden sonra dur, tekrarlardan kacin

    return variant_urls


class StoreEngine:
    name = "Generic"
    slug = "generic"
    domains = []
    search_path = None
    product_pattern = None
    js_search = False
    use_browser = False
    search_browser_fallback = False
    search_timeout_seconds = 40
    priority = 99
    parser_version = "2"
    supports_product_detail = True
    supports_sizes = False
    # Every dedicated adapter runs the shared visible cart-offer detector.
    # This means the engine can recognise an offer when a public product page
    # exposes it; it does not claim that every product is currently on sale.
    supports_cart_price = True
    supports_variants = False
    supports_seller_data = False
    discovery_method = None
    _response_cache = {}
    _fetch_semaphores = {}

    def supports_url(self, url):
        try:
            netloc = urlparse(url).netloc.lower()
        except Exception:
            return False
        netloc = netloc.split(":", 1)[0].rstrip(".")
        return any(netloc == d.lower() or netloc.endswith("." + d.lower()) for d in self.domains)

    def capabilities(self):
        if self.discovery_method:
            discovery_method = self.discovery_method
        elif self.js_search:
            discovery_method = "browser+sitemap"
        elif self.search_browser_fallback:
            discovery_method = "html+browser+sitemap"
        else:
            discovery_method = "html+sitemap"
        return asdict(
            StoreCapabilities(
                search=bool(self.search_path),
                product_detail=bool(self.supports_product_detail),
                sizes=bool(self.supports_sizes),
                cart_price=bool(self.supports_cart_price),
                variants=bool(self.supports_variants),
                seller_data=bool(self.supports_seller_data),
                requires_browser=bool(self.use_browser or self.js_search or self.search_browser_fallback),
                discovery_method=discovery_method,
            )
        )

    async def fetch(self, url, max_retries=3, backoff_seconds=1.5, timeout_seconds=20):
        last_exc = None
        headers = getattr(self, "headers", HEADERS)
        await validate_remote_url(url, self.domains)
        semaphore = self._fetch_semaphores.setdefault(self.slug, asyncio.Semaphore(STORE_FETCH_CONCURRENCY))
        async with _GLOBAL_FETCH_SEMAPHORE, semaphore:
            for attempt in range(1, max_retries + 1):
                current_url = url
                try:
                    cached = self._response_cache.get(url) or {}
                    request_headers = dict(headers)
                    if cached.get("etag"):
                        request_headers["If-None-Match"] = cached["etag"]
                    if cached.get("last_modified"):
                        request_headers["If-Modified-Since"] = cached["last_modified"]
                    async with httpx.AsyncClient(
                        follow_redirects=False,
                        timeout=timeout_seconds,
                        # Store checks must not silently inherit a stale desktop
                        # or development proxy.  Operators can opt back in for
                        # a legitimate corporate proxy when required.
                        trust_env=os.environ.get("SHOEHUNTER_TRUST_ENV_PROXY", "false").lower()
                        in {"1", "true", "yes"},
                    ) as client:
                        for _ in range(6):
                            await validate_remote_url(current_url, self.domains)
                            async with client.stream("GET", current_url, headers=request_headers) as response:
                                if response.status_code == 304 and cached.get("html"):
                                    return cached["html"]
                                if response.status_code in {301, 302, 303, 307, 308}:
                                    location = response.headers.get("location")
                                    if not location:
                                        raise RuntimeError("Yonlendirme hedefi eksik")
                                    current_url = urljoin(current_url, location)
                                    request_headers.pop("If-None-Match", None)
                                    request_headers.pop("If-Modified-Since", None)
                                    continue
                                response.raise_for_status()
                                chunks = []
                                total = 0
                                async for chunk in response.aiter_bytes():
                                    total += len(chunk)
                                    if total > MAX_RESPONSE_BYTES:
                                        raise RuntimeError("Yanit izin verilen boyutu asti")
                                    chunks.append(chunk)
                                raw_bytes = b"".join(chunks)
                                declared_encoding = response.charset_encoding or "utf-8"
                                try:
                                    html = raw_bytes.decode("utf-8")
                                except UnicodeDecodeError:
                                    html = raw_bytes.decode(declared_encoding, errors="replace")
                                self._response_cache[url] = {
                                    "html": html,
                                    "etag": response.headers.get("etag"),
                                    "last_modified": response.headers.get("last-modified"),
                                }
                                if len(self._response_cache) > 200:
                                    self._response_cache.pop(next(iter(self._response_cache)))
                                return html
                        raise RuntimeError("Cok fazla yonlendirme")
                except (URLValidationError, httpx.HTTPStatusError, httpx.TimeoutException, RuntimeError) as exc:
                    last_exc = exc
                    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in {401, 403, 429}:
                        # Access-control and rate-limit responses are terminal.
                        # Do not retry them with a different identity or route.
                        raise
                    if attempt < max_retries:
                        delay = backoff_seconds * (2 ** (attempt - 1)) + random.uniform(0.1, 0.8)
                        await asyncio.sleep(delay)
        raise last_exc

    async def fetch_with_browser(self, url):
        return await browser_pool.fetch(
            store_slug=self.slug,
            domains=self.domains,
            url=url,
            user_agent=getattr(self, "headers", HEADERS).get("User-Agent", HEADERS["User-Agent"]),
            browser_wait_selector=getattr(self, "browser_wait_selector", None),
        )

    async def get_product_data(self, url):
        if self.use_browser:
            html = await self.fetch_with_browser(url)
            if _looks_like_bot_challenge(html):
                return self.blocked_result(url, "access_challenge")
            return self.parse(html, url)
        try:
            html = await self.fetch(url)
            if _looks_like_bot_challenge(html):
                return self.blocked_result(url, "access_challenge")
            result = self.parse(html, url)
            # Public pages whose product data is client-rendered get one normal
            # browser-rendering fallback. Access challenges never reach here.
            if result["current_price"] is None:
                html = await self.fetch_with_browser(url)
                if _looks_like_bot_challenge(html):
                    return self.blocked_result(url, "access_challenge")
                result = self.parse(html, url)
            return result
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in {401, 403, 429}:
                return self.blocked_result(url, f"http_{exc.response.status_code}")
            raise

    def base_result(self, url):
        return {
            "store": self.name,
            "store_slug": self.slug,
            "url": url,
            "title": None,
            "brand": None,
            "model": None,
            "model_code": None,
            "gtin": None,
            "gender": None,
            "color": None,
            "width": None,
            "image": None,
            "current_price": None,
            "old_price": None,
            "cart_price": None,
            "cart_price_source": None,
            "cart_price_confidence": None,
            "cart_price_conditions": [],
            "price_source": None,
            "confidence": 0.5,
            "sizes": [],
            "stock_count": 0,
            "in_stock": False,
            "stock_status": "unknown",
            "variant_urls": [],
            "seller": None,
            "seller_rating": None,
            "official_seller": None,
            "shipping": None,
            "campaigns": [],
            "currency": "TRY",
            "availability": "unknown",
            "evidence": [],
            "checked_at": datetime.now(UTC).isoformat(),
            "debug": {"price_candidates": [], "variant_source": None, "notes": []},
        }

    def blocked_result(self, url, reason="access_challenge"):
        result = self.base_result(url)
        result["stock_status"] = "blocked"
        result["availability"] = "blocked"
        result["debug"]["notes"].append(str(reason)[:120])
        return result

    def _apply_cart_offers(self, soup, result, extra_selectors=()):
        """Extract exact and conditional cart offers from public product HTML.

        Exact, unconditional prices are stored in ``cart_price``. Percentage,
        quantity, membership, app, code, payment-method and size-dependent
        offers remain campaign metadata so they cannot trigger a false price
        alert. Candidates are processed in document order to avoid promoting a
        cheaper recommendation card below the main product.
        """

        general_selectors = (
            "[data-testid*='cart-price']",
            "[data-test-id*='cart-price']",
            "[data-testid*='basket-price']",
            "[data-test-id*='basket-price']",
            "[data-testid='discounted-price']",
            "[data-testid='basket-promo-price-wrapper']",
            "[class*='cart-price']",
            "[class*='cartPrice']",
            "[class*='basket-price']",
            "[class*='basketPrice']",
            "[class*='basket-promo-price']",
            "[class*='sepette']",
            "[class*='Sepette']",
            "[class*='sepet-fiyat']",
            "[class*='sepetFiyat']",
            "[id*='cart-price']",
            "[id*='basket-price']",
            "[id*='sepette']",
            ".product-item__offers",
        )
        candidates = []
        seen_nodes = set()

        for selector in tuple(extra_selectors) + general_selectors:
            try:
                nodes = soup.select(selector)[:24]
            except Exception:
                continue
            for node in nodes:
                identity = id(node)
                if identity in seen_nodes:
                    continue
                seen_nodes.add(identity)
                candidates.append((node, f"selector:{selector}"))

        for text_node in soup.find_all(string=_CART_TEXT_RE, limit=40):
            node = text_node.parent
            if not node or id(node) in seen_nodes:
                continue
            seen_nodes.add(id(node))
            candidates.append((node, "visible_text:sepet"))

        existing_campaigns = result.setdefault("campaigns", [])
        existing_labels = {
            _normalise_offer_text(item.get("label")): item
            for item in existing_campaigns
            if isinstance(item, dict) and item.get("label")
        }
        exact_applied = result.get("cart_price") is not None

        for node, source in candidates:
            visibility_node = node
            hidden = False
            for _ in range(4):
                if not visibility_node:
                    break
                style = str(visibility_node.get("style") or "").replace(" ", "").lower()
                if (
                    visibility_node.has_attr("hidden")
                    or str(visibility_node.get("aria-hidden") or "").lower() == "true"
                    or "display:none" in style
                    or "visibility:hidden" in style
                ):
                    hidden = True
                    break
                visibility_node = visibility_node.parent
            if hidden:
                continue
            direct_text = _normalise_offer_text(node.get_text(" ", strip=True))
            contexts = []
            current = node
            for _ in range(5):
                if not current:
                    break
                context_text = _normalise_offer_text(current.get_text(" ", strip=True))
                if _CART_TEXT_RE.search(context_text) and len(context_text) <= 520:
                    contexts.append((current, context_text))
                current = current.parent
            if not contexts:
                continue

            label = direct_text if _CART_TEXT_RE.search(direct_text) else contexts[0][1]
            label = label[:180]
            percent = _discount_percent(label)
            conditions = _cart_condition_tags(" ".join(text for _, text in contexts[:2]))

            exact_price = None
            exact_context = None
            for _, context_text in contexts:
                match = _EXPLICIT_CART_PRICE_RE.search(context_text)
                if match:
                    price = parse_price_text(match.group(1))
                    if price and 50 < price < 200000:
                        exact_price = price
                        exact_context = context_text
                        break
            if exact_price is None and percent is not None:
                # Some storefronts render the label and exact result as sibling
                # nodes: "22.999 TL / Sepette %26 / 16.999 TL".
                for _, context_text in contexts:
                    prices = _tl_prices(context_text)
                    if len(prices) >= 2:
                        exact_price = min(prices)
                        exact_context = context_text
                        break

            if exact_context:
                conditions = list(dict.fromkeys(conditions + _cart_condition_tags(exact_context)))

            campaign = existing_labels.get(label)
            if campaign is None:
                campaign = {"type": "cart", "label": label}
                existing_campaigns.append(campaign)
                existing_labels[label] = campaign
            campaign_type = "coupon" if "code_or_coupon" in conditions and re.search(
                r"\b(?:kupon|coupon)\b", label, re.IGNORECASE
            ) else "cart"
            campaign.update(
                {
                    "type": campaign_type,
                    "conditional": bool(conditions),
                    "conditions": conditions,
                    "source": source,
                }
            )
            if percent is not None:
                campaign["discount_percent"] = percent
            if exact_price is not None:
                campaign["exact_price"] = exact_price

            if conditions:
                result["debug"]["notes"].append(
                    f"conditional_cart_offer:{','.join(conditions)}:{label[:90]}"
                )
                continue
            if exact_price is None or exact_applied:
                if percent is not None and exact_price is None:
                    result["debug"]["notes"].append(f"cart_percent_without_exact_price:{percent:g}")
                continue

            shelf_price = result.get("current_price")
            if isinstance(shelf_price, (int, float)) and exact_price > shelf_price * 1.01:
                result["debug"]["notes"].append(
                    f"cart_price_above_shelf_ignored:{exact_price}>{shelf_price}"
                )
                continue

            confidence = 0.94 if source.startswith("selector:") else 0.9
            result["cart_price"] = exact_price
            result["cart_price_source"] = source
            result["cart_price_confidence"] = confidence
            result["cart_price_conditions"] = []
            result["debug"]["price_candidates"].append(
                {"source": source, "value": exact_price, "kind": "cart_price"}
            )
            result["evidence"].append(f"cart_offer:{(exact_context or label)[:180]}")
            exact_applied = True

    def parse_common_meta(self, soup, result, base_url=None):
        if not result["title"]:
            og = soup.find("meta", attrs={"property": "og:title"})
            if og and og.get("content"):
                result["title"] = og["content"].strip()
            elif soup.title and soup.title.string:
                result["title"] = soup.title.string.strip()[:150]
        if not result["image"]:
            result["image"] = _extract_meta_image(soup, base_url)
        if not result.get("seller"):
            seller_el = soup.select_one(
                "[itemprop='seller'] [itemprop='name'], [data-testid*='seller'], "
                "[class*='seller-name'], [class*='merchant-name'], [class*='satici-adi']"
            )
            if seller_el:
                result["seller"] = seller_el.get("content") or seller_el.get_text(" ", strip=True)[:120]
        if not result.get("shipping"):
            shipping_el = soup.select_one(
                "[data-testid*='shipping'], [class*='shipping-info'], [class*='delivery-info'], [class*='kargo-bilgi']"
            )
            if shipping_el:
                result["shipping"] = shipping_el.get_text(" ", strip=True)[:240]
        if not result.get("campaigns"):
            seen_campaigns = set()
            for campaign_el in soup.select(
                "[data-testid*='coupon'], [class*='coupon'], [class*='kupon'], "
                "[class*='campaign'], [class*='kampanya'], [class*='cart-price'], [class*='sepette']"
            )[:8]:
                label = re.sub(r"\s+", " ", campaign_el.get_text(" ", strip=True))[:180]
                if len(label) < 4 or label in seen_campaigns:
                    continue
                lowered = label.lower()
                if "kupon" in lowered or "coupon" in lowered:
                    campaign_type = "coupon"
                elif "sepet" in lowered or "cart" in lowered:
                    campaign_type = "cart"
                elif "uye" in lowered or "üye" in lowered or "member" in lowered:
                    campaign_type = "membership"
                elif "banka" in lowered or "kart" in lowered:
                    campaign_type = "bank"
                else:
                    campaign_type = "campaign"
                result["campaigns"].append({"type": campaign_type, "label": label})
                seen_campaigns.add(label)

        # Cart offers are evaluated even when another campaign (for example a
        # coupon) was already found, so one label cannot hide another.
        self._apply_cart_offers(soup, result)

    def parse(self, html, url):
        soup = BeautifulSoup(html, "lxml")
        result = self.base_result(url)
        dbg = result["debug"]

        for prod in extract_json_ld_products(soup):
            if not result["title"] and prod.get("name"):
                result["title"] = str(prod["name"]).strip()
            brand = prod.get("brand")
            if brand and not result["brand"]:
                result["brand"] = brand.get("name") if isinstance(brand, dict) else str(brand)
            if not result.get("model_code"):
                result["model_code"] = prod.get("mpn") or prod.get("sku")
            if not result.get("gtin"):
                result["gtin"] = prod.get("gtin13") or prod.get("gtin12") or prod.get("gtin")
            img = prod.get("image")
            if img and not result["image"]:
                result["image"] = _clean_image_url(url, _first_image_value(img))
            offer = _first_offer(prod.get("offers"))
            if offer and not result.get("seller"):
                seller = offer.get("seller")
                result["seller"] = seller.get("name") if isinstance(seller, dict) else seller
            if offer and offer.get("price") is not None and result["current_price"] is None:
                price = parse_price_text(str(offer.get("price")))
                if price and 50 < price < 200000:
                    result["current_price"] = price
                    result["price_source"] = "json_ld"
                    result["confidence"] = 0.75
                    dbg["price_candidates"].append({"source": "json_ld", "value": price})
                elif price:
                    dbg["price_candidates"].append({"source": "json_ld_ignored", "value": price})
                avail = str(offer.get("availability", ""))
                if "InStock" in avail:
                    result["stock_status"] = "in_stock"
                    result["in_stock"] = True
                elif "OutOfStock" in avail:
                    result["stock_status"] = "out_of_stock"
                    dbg["notes"].append("json_ld availability: OutOfStock")

        if result["current_price"] is None:
            meta_price = soup.find("meta", attrs={"property": "product:price:amount"}) or soup.find(
                "meta", attrs={"itemprop": "price"}
            )
            if meta_price and meta_price.get("content"):
                price = parse_price_text(meta_price["content"])
                if price and 50 < price < 200000:
                    result["current_price"] = price
                    result["price_source"] = "meta"
                    result["confidence"] = 0.6
                    dbg["price_candidates"].append({"source": "meta", "value": price})
                elif price:
                    dbg["price_candidates"].append({"source": "meta_ignored", "value": price})

        if result["current_price"] is None:
            embedded = extract_embedded_prices(soup)
            if embedded:
                price = min(embedded)
                result["current_price"] = price
                result["old_price"] = max(embedded) if max(embedded) > price else None
                result["price_source"] = "embedded_json"
                result["confidence"] = 0.55
                dbg["price_candidates"].append({"source": "embedded_json", "value": price, "all": embedded[:6]})

        if result["current_price"] is None:
            for sel in [".product-price", ".price__current", ".prc-dsc", "[data-price]", ".price", ".current-price", ".urun-fiyat"]:
                el = soup.select_one(sel)
                if el:
                    price = parse_price_text(el.get("data-price") or el.get("data-price-value") or el.get_text(" ", strip=True))
                    if price and 50 < price < 200000:
                        result["current_price"] = price
                        result["price_source"] = f"selector:{sel}"
                        result["confidence"] = 0.45
                        dbg["price_candidates"].append({"source": sel, "value": price})
                        break

        self.parse_common_meta(soup, result, url)
        if result["current_price"] and result["stock_status"] == "unknown" and not result["sizes"] and not dbg["notes"]:
            dbg["notes"].append("stok bilgisi bulunamadi; fiyat mevcut ama stok durumu belirsiz")
        _finalize_stock_status(result)
        # Genel varyasyon kesifleri
        result["variant_urls"] = _extract_variant_urls(soup, url)
        return result

    def is_product_link(self, url):
        path = urlparse(url).path
        if self.product_pattern:
            return bool(re.search(self.product_pattern, url))
        return path.count("-") >= 3 and len(path) > 25

    async def search(self, query):
        if not self.search_path:
            return []
        url = self.search_path.format(q=quote_plus(query))
        html = await self.fetch(url, max_retries=2, backoff_seconds=1, timeout_seconds=15)
        if _looks_like_bot_challenge(html):
            raise RuntimeError("403 bot protection challenge")
        results = self.parse_search(html, query, url)
        if results or not self.search_browser_fallback:
            return results

        # Some public catalog pages return an empty, client-rendered shell.
        # Use one ordinary browser render only for that case.  Access
        # challenges above remain terminal and are never bypassed.
        rendered_html = await self.fetch_with_browser(url)
        if _looks_like_bot_challenge(rendered_html):
            raise RuntimeError("403 bot protection challenge")
        return self.parse_search(rendered_html, query, url)

    def parse_search(self, html, query, base_url):
        soup = BeautifulSoup(html, "lxml")
        seen = set()
        out = []

        for prod in extract_json_ld_products(soup):
            title = str(prod.get("name") or "").strip()
            offer = _first_offer(prod.get("offers"))
            url = prod.get("url") or (offer or {}).get("url")
            full = _absolute_url(base_url, url)
            if not title or not full or not self.supports_url(full) or not self.is_product_link(full):
                continue
            score = _score_result(title, query)
            if score < 50 or full in seen:
                continue
            img = prod.get("image")
            if isinstance(img, list):
                img = img[0] if img else None
            price = parse_price_text((offer or {}).get("price")) if offer else None
            seen.add(full)
            out.append({
                "title": title[:160],
                "url": full.split("?")[0],
                "score": score,
                "image": _absolute_url(base_url, img),
                "price": price,
                "store": self.name,
            })

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith(("#", "javascript", "mailto")):
                continue
            full = urljoin(base_url, href).split("?")[0]
            if not self.supports_url(full) or not self.is_product_link(full):
                continue
            if full in seen:
                continue
            card = _nearest_product_card(a)
            title = _search_title_from_card(card, a)
            if len(title) < 8:
                continue
            score = _score_result(title, query)
            if score < 50:
                continue
            seen.add(full)
            out.append({
                "title": title,
                "url": full,
                "score": score,
                "image": _search_image_from_card(card, a, base_url),
                "price": _search_price_from_card(card),
                "store": self.name,
            })
        out.sort(key=lambda x: -x["score"])
        return out[:6]


class IntersportEngine(StoreEngine):
    name = "Intersport"
    slug = "intersport"
    domains = ["intersport.com.tr"]
    search_path = "https://www.intersport.com.tr/list/?search_text={q}"
    product_pattern = r"/urun/"
    priority = 1
    supports_sizes = True
    supports_cart_price = True
    supports_variants = True

    def parse(self, html, url):
        soup = BeautifulSoup(html, "lxml")
        result = self.base_result(url)
        dbg = result["debug"]

        cart_price = None
        cart_block = soup.select_one(".product-item__offers")
        if cart_block:
            el = cart_block.select_one(".product-item__offer-price pz-price, .product-item__offer-price")
            if el:
                cart_price = parse_price_text(el.get_text(strip=True))
                if cart_price:
                    dbg["price_candidates"].append({"source": "cart_offer", "value": cart_price})

        shelf_price = None
        shelf_old = None
        prices = []
        price_block = soup.select_one(".product-price")
        if price_block:
            for pz in price_block.select("pz-price"):
                v = parse_price_text(pz.get_text(strip=True))
                if v:
                    prices.append(v)
                    dbg["price_candidates"].append({"source": "shelf_pz_price", "value": v})
        if not prices:
            el = soup.select_one(".price.-has-discount pz-price, .price.-has-discount, .price__current")
            if el:
                v = parse_price_text(el.get_text(strip=True))
                if v:
                    prices.append(v)
                    dbg["price_candidates"].append({"source": "shelf_fallback", "value": v})
        if prices:
            shelf_price = min(prices)
            mx = max(prices)
            shelf_old = mx if mx > shelf_price else None

        if shelf_price:
            result["current_price"] = shelf_price
            result["old_price"] = shelf_old
            result["price_source"] = "shelf"
            result["confidence"] = 0.9
        if cart_price and (not shelf_price or cart_price <= shelf_price):
            # Preserve the normal product price and expose the cart offer as a
            # separate actionable value. Target-price evaluation already uses
            # the lower of these two fields.
            result["current_price"] = shelf_price or cart_price
            result["cart_price"] = cart_price
            result["cart_price_source"] = "intersport:.product-item__offers"
            result["cart_price_confidence"] = 0.95
            result["cart_price_conditions"] = []
            result["price_source"] = "shelf" if shelf_price else "cart_offer"
            result["confidence"] = 0.95

        for prod in extract_json_ld_products(soup):
            if not result["title"] and prod.get("name"):
                result["title"] = str(prod["name"]).strip()
            brand = prod.get("brand")
            if brand and not result["brand"]:
                result["brand"] = brand.get("name") if isinstance(brand, dict) else str(brand)
            img = prod.get("image")
            if img and not result["image"]:
                result["image"] = img[0] if isinstance(img, list) else str(img)
            if result["current_price"] is None:
                offer = _first_offer(prod.get("offers"))
                if offer and offer.get("price") is not None:
                    try:
                        val = float(offer["price"])
                        if val > 100000:
                            val = val / 100
                            dbg["notes"].append("json_ld kurus olcegi /100 uygulandi")
                        if 50 < val < 200000:
                            result["current_price"] = round(val, 2)
                            result["price_source"] = "json_ld"
                            result["confidence"] = 0.7
                            dbg["price_candidates"].append({"source": "json_ld", "value": result["current_price"]})
                        else:
                            dbg["price_candidates"].append({"source": "json_ld_ignored", "value": val})
                    except (TypeError, ValueError):
                        pass

        sizes = []
        beden = soup.find("pz-variant", attrs={"key": "integration_beden"})
        if beden:
            dbg["variant_source"] = "pz-variant key=integration_beden"
            for opt in beden.find_all("pz-variant-option"):
                label = opt.get("label") or opt.get("value") or opt.get_text(strip=True)
                if not label:
                    continue
                sizes.append(
                    {
                        "name": label,
                        "size": label,
                        "in_stock": opt.has_attr("selectable"),
                        "sku": opt.get("data-product-sku"),
                        "confidence": 0.95,
                        "stock_source": "pz-variant-option selectable" if opt.has_attr("selectable") else "pz-variant-option not selectable",
                    }
                )
        result["sizes"] = sizes
        result["stock_count"] = sum(1 for s in sizes if s["in_stock"])
        if sizes:
            result["stock_status"] = "in_stock" if result["stock_count"] > 0 else "out_of_stock"
        elif result["current_price"] is not None:
            result["stock_status"] = "unknown"
        _finalize_stock_status(result)
        self.parse_common_meta(soup, result, url)
        # Intersport renk varyasyonlari
        result["variant_urls"] = _extract_variant_urls(soup, url)
        return result


from stores.amazon import AmazonEngine
from stores.kaptanspor import KaptanSporEngine
from stores.marketplaces import HepsiburadaEngine, N11Engine
from stores.newbalance import NewBalanceEngine
from stores.nike import NikeEngine
from stores.outdoor import BrooksEngine, ColumbiaEngine, SalomonEngine, TheNorthFaceEngine
from stores.puma import PumaEngine
from stores.retailers import (
    AsicsEngine,
    BarcinEngine,
    BoynerEngine,
    FloEngine,
    KoraySporEngine,
    KutupayisiEngine,
    SkechersEngine,
    SneaksUpEngine,
    SpxEngine,
    SuperStepEngine,
)
from stores.trendyol import TrendyolEngine
from stores.yalispor import YaliSporEngine

from stores.adidas import AdidasEngine
from stores.decathlon import DecathlonEngine
from stores.sportive import SportiveEngine

ENGINES = [
    DecathlonEngine(),
    AdidasEngine(),
    NikeEngine(),
    PumaEngine(),
    NewBalanceEngine(),
    SportiveEngine(),
    IntersportEngine(),
    BarcinEngine(),
    KoraySporEngine(),
    FloEngine(),
    SuperStepEngine(),
    SneaksUpEngine(),
    YaliSporEngine(),
    BoynerEngine(),
    KaptanSporEngine(),
    SpxEngine(),
    KutupayisiEngine(),
    TrendyolEngine(),
    HepsiburadaEngine(),
    N11Engine(),
    AmazonEngine(),
    AsicsEngine(),
    SkechersEngine(),
    BrooksEngine(),
    ColumbiaEngine(),
    SalomonEngine(),
    TheNorthFaceEngine(),
]


def get_engine_for_url(url):
    for e in ENGINES:
        if e.supports_url(url):
            return e
    raise ValueError("Bu magaza desteklenen guvenli alan adlari listesinde degil")


def search_engines():
    return [e for e in ENGINES if e.search_path]
