import json
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from engines import (
    StoreEngine,
    parse_price_text,
    _absolute_url,
    _clean_image_url,
    _finalize_stock_status,
    _score_result,
)


def _json_value_after_key(text, key):
    match = re.search(rf'"{re.escape(key)}"\s*:\s*', text)
    if not match:
        return None
    start = match.end()
    while start < len(text) and text[start].isspace():
        start += 1
    if start >= len(text) or text[start] not in "[{":
        return None

    opening = text[start]
    closing = "]" if opening == "[" else "}"
    depth = 0
    in_string = False
    escaped = False
    for idx in range(start, len(text)):
        ch = text[idx]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == opening:
            depth += 1
        elif ch == closing:
            depth -= 1
            if depth == 0:
                raw = text[start : idx + 1]
                raw = re.sub(r",\s*([}\]])", r"\1", raw)
                try:
                    return json.loads(raw)
                except (TypeError, ValueError, json.JSONDecodeError):
                    return None
    return None


def _availability_status(text):
    normalized = (text or "").strip().lower()
    if not normalized:
        return None
    out_tokens = ["stokta yok", "temin edilemiyor", "tukendi", "tükendi", "mevcut degil", "mevcut değil"]
    if any(token in normalized for token in out_tokens):
        return "out_of_stock"
    in_tokens = ["stokta", "mevcut", "hemen al", "sepete ekle"]
    if any(token in normalized for token in in_tokens):
        return "in_stock"
    return None


class AmazonEngine(StoreEngine):
    name = "Amazon TR"
    slug = "amazon"
    domains = ["amazon.com.tr"]
    search_path = "https://www.amazon.com.tr/s?k={q}"
    product_pattern = r"/dp/[A-Z0-9]{10}"
    priority = 16
    js_search = False
    use_browser = False
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    }

    def parse(self, html, url):
        soup = BeautifulSoup(html, "lxml")
        result = self.base_result(url)
        dbg = result["debug"]

        title_el = soup.select_one("#productTitle")
        if title_el:
            result["title"] = title_el.get_text(" ", strip=True)
        self.parse_common_meta(soup, result, url)

        image = self._extract_image(soup, url)
        if image:
            result["image"] = image

        price = self._extract_price(soup)
        if price:
            result["current_price"] = price
            result["price_source"] = "amazon_price_block"
            result["confidence"] = 0.82
            dbg["price_candidates"].append({"source": "amazon_price_block", "value": price})

        availability_el = soup.select_one("#availability, #outOfStock, #availabilityInsideBuyBox_feature_div")
        availability_text = availability_el.get_text(" ", strip=True) if availability_el else ""
        availability_status = _availability_status(availability_text)
        if availability_status:
            result["stock_status"] = availability_status

        sizes = self._extract_sizes(html, url=url, overall_status=availability_status)
        if sizes:
            result["sizes"] = sizes
            dbg["variant_source"] = "amazon_twister_variations"
            dbg["notes"].append(f"amazon_stock: {sum(1 for s in sizes if s.get('in_stock'))}/{len(sizes)} beden stokta")

        asin_match = re.search(r"/dp/([A-Z0-9]{10})", url, re.I)
        if asin_match:
            result["model_code"] = asin_match.group(1).upper()
        seller_el = soup.select_one("#sellerProfileTriggerId, #merchant-info a, #merchant-info")
        if seller_el:
            result["seller"] = seller_el.get_text(" ", strip=True)[:160]
            result["official_seller"] = "amazon.com.tr" in result["seller"].lower()
        shipping_el = soup.select_one("#mir-layout-DELIVERY_BLOCK, #deliveryBlockMessage, #ddmDeliveryMessage")
        if shipping_el:
            result["shipping"] = shipping_el.get_text(" ", strip=True)[:240]
        coupon = soup.select_one("#couponText, .couponBadge, [id*='coupon'] label")
        if coupon:
            result["campaigns"].append({"type": "coupon", "label": coupon.get_text(" ", strip=True)[:160]})

        _finalize_stock_status(result)
        return result

    def _extract_image(self, soup, base_url):
        img = soup.select_one("#landingImage")
        if img:
            for attr in ("data-old-hires", "src"):
                image = _clean_image_url(base_url, img.get(attr))
                if image:
                    return image
            dynamic = img.get("data-a-dynamic-image")
            if dynamic:
                try:
                    data = json.loads(dynamic)
                    for image_url in data:
                        image = _clean_image_url(base_url, image_url)
                        if image:
                            return image
                except (TypeError, ValueError, json.JSONDecodeError):
                    pass
        return None

    def _extract_price(self, soup):
        selectors = [
            "#corePrice_feature_div .a-price .a-offscreen",
            "#apex_desktop .a-price .a-offscreen",
            ".priceToPay .a-offscreen",
            "#priceblock_ourprice",
            "#priceblock_dealprice",
            "#price_inside_buybox",
            "#apex-pricetopay-accessibility-label",
            ".a-price .a-offscreen",
        ]
        for selector in selectors:
            for el in soup.select(selector):
                raw = el.get("data-pricetopay-label") or el.get_text(" ", strip=True)
                price = parse_price_text(raw)
                if price and 50 < price < 200000:
                    return price
        return None

    def _extract_sizes(self, html, url=None, overall_status=None):
        sorted_dims = _json_value_after_key(html, "sortedDimValuesForAllDims")
        sizes = []
        seen = set()
        if isinstance(sorted_dims, dict):
            for item in sorted_dims.get("size_name") or []:
                if not isinstance(item, dict):
                    continue
                label = str(item.get("dimensionValueDisplayText") or item.get("value") or "").strip()
                if not label or label in seen:
                    continue
                state = str(item.get("dimensionValueState") or "").upper()
                disabled = bool(item.get("disabled"))
                sizes.append({
                    "name": label,
                    "size": label,
                    "in_stock": state != "UNAVAILABLE" and not disabled,
                    "sku": item.get("defaultAsin"),
                    "stock_source": "amazon_sortedDimValuesForAllDims",
                })
                seen.add(label)
        if sizes:
            return sizes

        selected_asin = None
        if url:
            selected_match = re.search(r"/dp/([A-Z0-9]{10})", url, re.I)
            selected_asin = selected_match.group(1).upper() if selected_match else None
        available_asins = {asin.upper() for asin in re.findall(
            r'"([A-Z0-9]{10})"\s*:\s*\{[^{}]{0,400}"(?:isAvailable|available)"\s*:\s*true',
            html,
            re.I,
        )}
        unavailable_asins = {asin.upper() for asin in re.findall(
            r'"([A-Z0-9]{10})"\s*:\s*\{[^{}]{0,400}"(?:isAvailable|available)"\s*:\s*false',
            html,
            re.I,
        )}
        display_data = _json_value_after_key(html, "dimensionValuesDisplayData")
        if isinstance(display_data, dict):
            for asin, values in display_data.items():
                if not isinstance(values, list) or not values:
                    continue
                label = str(values[0]).strip()
                if not label or label in seen:
                    continue
                normalized_asin = str(asin).upper()
                if normalized_asin in available_asins:
                    in_stock = True
                elif normalized_asin in unavailable_asins:
                    in_stock = False
                elif normalized_asin == selected_asin and overall_status == "in_stock":
                    in_stock = True
                else:
                    in_stock = None
                sizes.append({
                    "name": label,
                    "size": label,
                    "in_stock": in_stock,
                    "sku": asin,
                    "stock_source": "amazon_dimensionValuesDisplayData",
                })
                seen.add(label)
        return sizes

    def parse_search(self, html, query, base_url):
        soup = BeautifulSoup(html, "lxml")
        results = []
        seen = set()
        for card in soup.select("div[data-component-type='s-search-result'][data-asin]"):
            asin = card.get("data-asin")
            a_tag = card.select_one("a.a-link-normal[href*='/dp/']")
            title_el = card.select_one("h2 span, [data-cy='title-recipe-title'] span")
            title = title_el.get_text(" ", strip=True) if title_el else ""
            if not asin or not a_tag or not title:
                continue
            href = urljoin(base_url, a_tag.get("href")).split("?")[0]
            if "/dp/" not in href:
                href = f"https://www.amazon.com.tr/dp/{asin}"
            parsed = urlparse(href)
            full = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            if full in seen:
                continue
            score = _score_result(title, query)
            if score < 50:
                continue
            img = card.select_one("img.s-image")
            price_el = card.select_one(".a-price .a-offscreen")
            seen.add(full)
            results.append({
                "title": title[:160],
                "url": full,
                "score": score,
                "image": _absolute_url(base_url, img.get("src")) if img else None,
                "price": parse_price_text(price_el.get_text(" ", strip=True)) if price_el else None,
                "store": self.name,
            })
        results.sort(key=lambda item: -item["score"])
        return results[:8]
