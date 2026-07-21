import json
import re
from datetime import datetime, timezone
from urllib.parse import urlparse, quote_plus, urljoin

import httpx
from bs4 import BeautifulSoup
from rapidfuzz import fuzz

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Cache-Control": "no-cache",
}


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


def _score_result(title, query):
    title_text = (title or "").strip().lower()
    query_text = (query or "").strip().lower()
    if not title_text or not query_text:
        return 0
    return round(fuzz.token_set_ratio(query_text, title_text))


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
    priority = 99

    def supports_url(self, url):
        try:
            netloc = urlparse(url).netloc.lower()
        except Exception:
            return False
        return any(d in netloc for d in self.domains)

    async def fetch(self, url, max_retries=3, backoff_seconds=1.5, timeout_seconds=20):
        import asyncio
        last_exc = None
        headers = getattr(self, "headers", HEADERS)
        for attempt in range(1, max_retries + 1):
            try:
                async with httpx.AsyncClient(follow_redirects=True, timeout=timeout_seconds, headers=headers) as client:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    return resp.text
            except Exception as exc:
                last_exc = exc
                if attempt < max_retries:
                    await asyncio.sleep(backoff_seconds * attempt)
        raise last_exc

    async def fetch_with_browser(self, url):
        """Playwright ile sayfayi gercek bir tarayici gibi okur (bot korumasi asan)."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise RuntimeError("Playwright kurulu degil")
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True, args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
            )
            context = await browser.new_context(
                user_agent=HEADERS["User-Agent"],
                locale="tr-TR",
                viewport={"width": 1366, "height": 900},
            )
            page = await context.new_page()
            try:
                from playwright_stealth.stealth import Stealth
                await Stealth().apply_stealth_async(page)
            except Exception:
                pass
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=25000)
                try:
                    await page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    pass
                await page.mouse.wheel(0, 800)
                await page.wait_for_timeout(2000)
                html = await page.content()
            finally:
                await page.close()
                await browser.close()
        return html

    async def get_product_data(self, url):
        if self.use_browser:
            html = await self.fetch_with_browser(url)
            return self.parse(html, url)
        try:
            html = await self.fetch(url)
            result = self.parse(html, url)
            # Eger fiyat bulunamadiysa ve httpx ile 403/captcha aldiysa browser ile tekrar dene
            if result["current_price"] is None:
                html = await self.fetch_with_browser(url)
                result = self.parse(html, url)
            return result
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (403, 429, 503):
                html = await self.fetch_with_browser(url)
                return self.parse(html, url)
            raise

    def base_result(self, url):
        return {
            "store": self.name,
            "store_slug": self.slug,
            "url": url,
            "title": None,
            "brand": None,
            "image": None,
            "current_price": None,
            "old_price": None,
            "cart_price": None,
            "price_source": None,
            "confidence": 0.5,
            "sizes": [],
            "stock_count": 0,
            "in_stock": False,
            "variant_urls": [],
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "debug": {"price_candidates": [], "variant_source": None, "notes": []},
        }

    def parse_common_meta(self, soup, result, base_url=None):
        if not result["title"]:
            og = soup.find("meta", attrs={"property": "og:title"})
            if og and og.get("content"):
                result["title"] = og["content"].strip()
            elif soup.title and soup.title.string:
                result["title"] = soup.title.string.strip()[:150]
        if not result["image"]:
            result["image"] = _extract_meta_image(soup, base_url)

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
            img = prod.get("image")
            if img and not result["image"]:
                result["image"] = _clean_image_url(url, _first_image_value(img))
            offer = _first_offer(prod.get("offers"))
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
                    result["in_stock"] = True
                elif "OutOfStock" in avail:
                    result["in_stock"] = False
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
        if result["current_price"] and result["in_stock"] is False and not result["sizes"] and not dbg["notes"]:
            result["in_stock"] = True
            dbg["notes"].append("stok bilgisi bulunamadi, fiyat mevcut oldugu icin stokta varsayildi (dusuk guven)")
        result["stock_count"] = sum(1 for s in result["sizes"] if s.get("in_stock"))
        if result["sizes"]:
            result["in_stock"] = result["stock_count"] > 0
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
        return self.parse_search(html, query, url)

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

        if cart_price:
            result["current_price"] = cart_price
            result["cart_price"] = cart_price
            result["old_price"] = shelf_price or shelf_old
            result["price_source"] = "cart_offer"
            result["confidence"] = 0.95
        elif shelf_price:
            result["current_price"] = shelf_price
            result["old_price"] = shelf_old
            result["price_source"] = "shelf"
            result["confidence"] = 0.9

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
                        while val > 15000:
                            val = val / 10
                        result["current_price"] = round(val, 2)
                        result["price_source"] = "json_ld"
                        result["confidence"] = 0.7
                        dbg["price_candidates"].append({"source": "json_ld_fixed", "value": result["current_price"]})
                        dbg["notes"].append("json_ld fiyat bug duzeltmesi uygulanmis olabilir")
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
        result["in_stock"] = result["stock_count"] > 0 if sizes else result["current_price"] is not None
        self.parse_common_meta(soup, result, url)
        # Intersport renk varyasyonlari
        result["variant_urls"] = _extract_variant_urls(soup, url)
        return result


def make_engine(name, slug, domains, search_path=None, product_pattern=None, priority=50, js_search=False, use_browser=False):
    e = StoreEngine()
    e.name = name
    e.slug = slug
    e.domains = domains
    e.search_path = search_path
    e.product_pattern = product_pattern
    e.priority = priority
    e.js_search = js_search
    e.use_browser = use_browser
    return e

from stores.sportive import SportiveEngine
from stores.decathlon import DecathlonEngine
from stores.adidas import AdidasEngine
from stores.nike import NikeEngine
from stores.puma import PumaEngine
from stores.newbalance import NewBalanceEngine

ENGINES = [
    DecathlonEngine(),
    AdidasEngine(),
    NikeEngine(),
    PumaEngine(),
    NewBalanceEngine(),
    SportiveEngine(),
    IntersportEngine(),
    make_engine("Barçın", "barcin", ["barcin.com"], "https://www.barcin.com/search?q={q}", priority=3, js_search=True),
    make_engine("Korayspor", "korayspor", ["korayspor.com"], "https://www.korayspor.com/arama?q={q}", priority=4),
    make_engine("FLO", "flo", ["flo.com.tr"], "https://www.flo.com.tr/search?q={q}", priority=5, js_search=True),
    make_engine("SuperStep", "superstep", ["superstep.com.tr"], "https://www.superstep.com.tr/arama?q={q}", priority=6, js_search=True),
    make_engine("Sneaks Up", "sneaksup", ["sneaksup.com"], "https://www.sneaksup.com/search?q={q}", priority=7),
    make_engine("Yalı Spor", "yalispor", ["yalispor.com.tr"], "https://www.yalispor.com.tr/arama?q={q}", priority=8),
    make_engine("Boyner", "boyner", ["boyner.com.tr"], "https://www.boyner.com.tr/arama?q={q}", priority=9),
    make_engine("SPX", "spx", ["spx.com.tr"], "https://www.spx.com.tr/arama?q={q}", priority=11, js_search=True),
    make_engine("Kutupayısı", "kutupayisi", ["kutupayisi.com"], "https://www.kutupayisi.com/arama?q={q}", priority=12, js_search=True),
    make_engine("Trendyol", "trendyol", ["trendyol.com"], "https://www.trendyol.com/sr?q={q}", product_pattern=r"-p-\d+", priority=13),
    make_engine("Hepsiburada", "hepsiburada", ["hepsiburada.com"], "https://www.hepsiburada.com/ara?q={q}", product_pattern=r"-p[m]?-[A-Z0-9]+", priority=14),
    make_engine("n11", "n11", ["n11.com"], "https://www.n11.com/arama?q={q}", product_pattern=r"/urun/", priority=15),
    make_engine("Amazon TR", "amazon", ["amazon.com.tr"], "https://www.amazon.com.tr/s?k={q}", product_pattern=r"/dp/", priority=16),
    make_engine("ASICS TR", "asics", ["asics.com.tr", "asics.com"], "https://www.asics.com.tr/tr-tr/search?q={q}", product_pattern=r"/[0-9]{3,}", priority=24, js_search=True, use_browser=True),
    make_engine("Skechers TR", "skechers", ["skechers.com.tr"], "https://www.skechers.com.tr/arama?q={q}", product_pattern=r"/p-", priority=25, js_search=True, use_browser=True),
]


def get_engine_for_url(url):
    for e in ENGINES:
        if e.supports_url(url):
            return e
    netloc = urlparse(url).netloc.replace("www.", "")
    return make_engine(netloc or "Bilinmeyen", "generic", [netloc] if netloc else [], priority=99)


def search_engines():
    return [e for e in ENGINES if e.search_path]
