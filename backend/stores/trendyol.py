"""Conservative Trendyol adapter backed by structured page data.

The adapter keeps the broad, real-world ``-p-<id>`` URL shape and only
promotes values that can be tied to a product-like JSON object.
"""

import json
import re
from collections import Counter
from urllib.parse import unquote, urlparse

from bs4 import BeautifulSoup
from engines import (
    StoreEngine,
    _absolute_url,
    _clean_image_url,
    _finalize_stock_status,
    _score_result,
    parse_price_text,
)


class TrendyolEngine(StoreEngine):
    supports_sizes = True
    supports_variants = True
    supports_seller_data = True
    name = "Trendyol"
    slug = "trendyol"
    domains = ["trendyol.com"]
    search_path = "https://www.trendyol.com/sr?q={q}"
    product_pattern = r"-p-\d+(?:$|[/?#])"
    priority = 13
    js_search = True
    use_browser = True
    sitemap_title_prefix = "trendyol"

    @staticmethod
    def _number(value):
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, dict):
            value = value.get("value") or value.get("price") or value.get("discountedPrice")
        parsed = parse_price_text(value)
        return float(parsed) if parsed and 50 < parsed < 200000 else None

    def _find_product(self, node, depth=0):
        if depth > 8 or not isinstance(node, (dict, list)):
            return None
        if isinstance(node, list):
            for item in node[:50]:
                found = self._find_product(item, depth + 1)
                if found:
                    return found
            return None

        name = node.get("name") or node.get("productName") or node.get("title")
        price = node.get("discountedPrice") or node.get("salePrice") or node.get("price")
        if name and price is not None and any(key in node for key in ("id", "productId", "url", "productUrl", "variants")):
            return node
        for key in ("product", "productDetail", "pdp", "item", "pageProps", "initialState", "props", "data"):
            child = node.get(key)
            if isinstance(child, (dict, list)):
                found = self._find_product(child, depth + 1)
                if found:
                    return found
        return None

    def _apply_product(self, product, result):
        price = self._number(product.get("discountedPrice") or product.get("salePrice") or product.get("price"))
        if price is None:
            return False
        result["current_price"] = price
        result["price_source"] = "embedded_json:product.price"
        result["confidence"] = 0.85
        result["debug"]["price_candidates"].append({"source": "embedded_json", "value": price})

        old_price = self._number(product.get("originalPrice") or product.get("listPrice") or product.get("marketPrice"))
        if old_price and old_price >= price:
            result["old_price"] = old_price
        title = product.get("name") or product.get("productName") or product.get("title")
        if title:
            result["title"] = str(title)[:200]

        images = product.get("images") or product.get("image") or []
        image = images[0] if isinstance(images, list) and images else images
        if isinstance(image, dict):
            image = image.get("url") or image.get("imagePath") or image.get("src")
        if image:
            result["image"] = _clean_image_url("https://www.trendyol.com", image)

        sizes = []
        for variant in (product.get("allVariants") or product.get("variants") or [])[:100]:
            if not isinstance(variant, dict):
                continue
            label = variant.get("attributeValue") or variant.get("value") or variant.get("size") or variant.get("name")
            attribute = str(variant.get("attributeTypeName") or variant.get("attributeType") or "").lower()
            if not label or (attribute and not any(word in attribute for word in ("beden", "numara", "size", "shoe"))):
                continue
            if "outOfStock" in variant:
                in_stock = not bool(variant.get("outOfStock"))
            else:
                in_stock = bool(variant.get("inStock") or variant.get("stock") or variant.get("quantity"))
            sizes.append({"name": str(label), "size": str(label), "in_stock": in_stock})
        if sizes:
            result["sizes"] = sizes
            _finalize_stock_status(result)
        elif product.get("inStock") is not None:
            result["in_stock"] = bool(product.get("inStock"))
            result["stock_status"] = "in_stock" if result["in_stock"] else "out_of_stock"

        seller = product.get("merchantName") or product.get("sellerName")
        brand = product.get("brand")
        if not seller and isinstance(brand, dict):
            seller = brand.get("name")
        if seller:
            result["seller"] = str(seller)[:160]
        return True

    def _apply_json_ld(self, soup, result):
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or script.get_text() or "")
            except (TypeError, ValueError):
                continue
            items = data if isinstance(data, list) else [data]
            for item in items:
                if not isinstance(item, dict) or "Product" not in str(item.get("@type") or ""):
                    continue
                offers = item.get("offers") or {}
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}
                if not isinstance(offers, dict):
                    continue
                price = self._number(offers.get("price") or offers.get("lowPrice"))
                if price is None:
                    continue
                result["current_price"] = price
                result["price_source"] = "json_ld:Product.offers.price"
                result["confidence"] = 0.75
                result["debug"]["price_candidates"].append({"source": "json_ld", "value": price})
                availability = str(offers.get("availability") or "").lower()
                if availability:
                    result["in_stock"] = "instock" in availability
                    result["stock_status"] = "in_stock" if result["in_stock"] else "out_of_stock"
                if item.get("name"):
                    result["title"] = str(item["name"])[:200]
                return True
        return False

    def parse(self, html, url):
        soup = BeautifulSoup(html, "lxml")
        result = self.base_result(url)
        self.parse_common_meta(soup, result, url)
        script = soup.find("script", id="__NEXT_DATA__")
        if script:
            try:
                product = self._find_product(json.loads(script.string or script.get_text() or ""))
            except (TypeError, ValueError):
                product = None
            if product and self._apply_product(product, result):
                return result
        self._apply_json_ld(soup, result)
        return result

    def parse_search(self, html, query, base_url):
        results = list(super().parse_search(html, query, base_url))
        seen = {item["url"].split("?")[0] for item in results}
        soup = BeautifulSoup(html, "lxml")
        for card in soup.select(".p-card-wrppr, .product-card, [data-testid='product-card']"):
            anchor = card.select_one("a[href]")
            full_url = _absolute_url(base_url, anchor.get("href")) if anchor else None
            if not full_url or not self.is_product_link(full_url):
                continue
            clean_url = full_url.split("?")[0]
            if clean_url in seen:
                continue
            title = anchor.get("title") or card.get_text(" ", strip=True)
            score = _score_result(title, query)
            if score < 40:
                continue
            price_node = card.select_one(".prc-box-sllng, [class*='price']")
            results.append(
                {
                    "title": str(title)[:200],
                    "url": clean_url,
                    "price": parse_price_text(price_node.get_text(" ", strip=True)) if price_node else None,
                    "image": None,
                    "score": score,
                    "store": self.name,
                }
            )
            seen.add(clean_url)

        title_counts = Counter(str(item.get("title") or "").strip().casefold() for item in results)
        cleaned = []
        seen.clear()
        for item in results:
            clean_url = item["url"].split("?")[0]
            if clean_url in seen:
                continue
            title = str(item.get("title") or "").strip()
            path = unquote(urlparse(clean_url).path)
            slug = path.rstrip("/").rsplit("/", 1)[-1]
            slug = re.sub(r"-p-\d+$", "", slug, flags=re.I)
            slug_title = re.sub(r"[-_]+", " ", slug).strip()
            if slug_title and (not title or title_counts[title.casefold()] > 1):
                title = slug_title
            score = _score_result(title, query)
            if score < 40:
                continue
            cleaned.append({**item, "title": title[:200], "url": clean_url, "score": score})
            seen.add(clean_url)
        cleaned.sort(key=lambda item: (-item["score"], item.get("price") or 10**12))
        return cleaned[:12]
