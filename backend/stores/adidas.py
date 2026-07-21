"""Adidas.com.tr özel mağaza motoru.

Kullanıcının yazdığı JSON-LD (ProductGroup) tabanlı mantık kullanılarak
asenkron yapıya entegre edilmiştir.
"""
import json
import os
import re
import sys

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engines import (
    StoreEngine,
    _absolute_url,
    _clean_image_url,
    _extract_variant_urls,
    _finalize_stock_status,
    _score_result,
    parse_price_text,
)


class AdidasEngine(StoreEngine):
    supports_sizes = True
    supports_variants = True
    name = "Adidas Türkiye"
    slug = "adidas"
    domains = ["adidas.com.tr"]
    search_path = "https://www.adidas.com.tr/tr/search?q={q}"
    product_pattern = r"/[A-Z]{2}\d{4}\.html"
    priority = 21
    js_search = True
    use_browser = True  # Adidas Cloudflare 403 hatasi verdigi icin Playwright kullanimi sarttir
    sitemap_title_prefix = "adidas"
    browser_wait_selector = "script[type='application/ld+json'], [data-testid*='price'], [class*='gl-price']"

    async def exact_identifier_candidates(self, query):
        """Resolve a style code through Adidas' public canonical redirect."""
        code = str(query or "").strip().upper()
        if not re.fullmatch(r"[A-Z]{2}\d{4}", code):
            return []
        url = f"https://www.adidas.com.tr/en/{code}.html"
        try:
            html = await self.fetch_with_browser(url)
        except RuntimeError as exc:
            if "HTTP 404" in str(exc):
                return []
            if "HTTP 403" in str(exc):
                return [
                    {
                        "title": f"adidas {code}",
                        "url": url,
                        "price": None,
                        "image": None,
                        "source": "official_exact_code",
                        "verification_required": True,
                    }
                ]
            raise
        result = self.parse(html, url)
        title = str(result.get("title") or "").strip()
        if not title or code.lower() not in html.lower():
            return []
        return [
            {
                "title": title,
                "url": url,
                "price": result.get("current_price"),
                "image": result.get("image"),
                "source": "official_exact_code",
            }
        ]

    def _image_from_card(self, card, base_url):
        img = card.find("img")
        if not img:
            return None
        for attr in ("src", "data-src", "data-original", "data-testid"):
            image = _clean_image_url(base_url, img.get(attr))
            if image:
                return image
        srcset = img.get("srcset") or img.get("data-srcset")
        if srcset:
            image = _clean_image_url(base_url, srcset.split(",")[0].strip().split(" ")[0])
            if image:
                return image
        return None

    def _title_from_card(self, card, anchor):
        candidates = [anchor.get("aria-label"), anchor.get("title")]
        for selector in (
            "[data-testid*='product-name']",
            "[data-testid*='product-title']",
            "[class*='product-name']",
            "[class*='product-title']",
            "[class*='name']",
            "h2",
            "h3",
        ):
            el = card.select_one(selector)
            if el:
                candidates.append(el.get_text(" ", strip=True))
        img = card.find("img") or anchor.find("img")
        if img:
            candidates.extend([img.get("alt"), img.get("title")])
        candidates.append(anchor.get_text(" ", strip=True))
        for candidate in candidates:
            text = " ".join(str(candidate or "").split())
            if len(text) >= 8:
                return text[:160]
        return ""

    def _price_from_card(self, card):
        for selector in ("[class*='price']", "[data-auto-id*='price']", "[data-testid*='price']"):
            el = card.select_one(selector)
            price = parse_price_text(el.get_text(" ", strip=True)) if el else None
            if price and 50 < price < 200000:
                return price
        return None

    def _walk_embedded_products(self, obj, base_url, depth=0):
        if depth > 7:
            return
        if isinstance(obj, dict):
            title = obj.get("name") or obj.get("title") or obj.get("displayName") or obj.get("productName")
            url = obj.get("url") or obj.get("link") or obj.get("href") or obj.get("pdpUrl") or obj.get("productUrl")
            full = _absolute_url(base_url, url)
            if title and full and self.supports_url(full) and self.is_product_link(full):
                image = obj.get("image") or obj.get("imageUrl") or obj.get("thumbnail") or obj.get("src")
                if isinstance(image, list):
                    image = image[0] if image else None
                if isinstance(image, dict):
                    image = image.get("url") or image.get("src")
                price = None
                for key in ("salePrice", "currentPrice", "price", "displayPrice"):
                    price = parse_price_text(obj.get(key))
                    if price:
                        break
                yield {
                    "title": str(title),
                    "url": full.split("?")[0],
                    "price": price,
                    "image": _clean_image_url(base_url, image),
                }
            for value in obj.values():
                if isinstance(value, (dict, list)):
                    yield from self._walk_embedded_products(value, base_url, depth + 1)
        elif isinstance(obj, list):
            for item in obj[:200]:
                yield from self._walk_embedded_products(item, base_url, depth + 1)

    def parse_search(self, html, query, base_url):
        soup = BeautifulSoup(html, "lxml")
        results = []
        seen = set()

        for item in super().parse_search(html, query, base_url):
            clean_url = item["url"].split("?")[0]
            seen.add(clean_url)
            results.append(item)

        card_selectors = (
            "[data-testid*='product-card']",
            "[data-auto-id*='product-card']",
            ".glass-product-card",
            ".product-card",
            "[class*='product-card']",
            "article",
            "li[class*='product']",
        )
        for card in soup.select(", ".join(card_selectors)):
            anchor = card.select_one("a[href*='.html']")
            if not anchor:
                continue
            full = _absolute_url(base_url, anchor.get("href"))
            if not full or not self.supports_url(full) or not self.is_product_link(full):
                continue
            clean_url = full.split("?")[0]
            if clean_url in seen:
                continue
            title = self._title_from_card(card, anchor)
            score = _score_result(title, query)
            if score < 45:
                continue
            seen.add(clean_url)
            results.append(
                {
                    "title": title,
                    "url": clean_url,
                    "price": self._price_from_card(card),
                    "image": self._image_from_card(card, base_url),
                    "score": score,
                    "store": self.name,
                }
            )

        for script in soup.find_all("script", id="__NEXT_DATA__"):
            raw = script.string or script.get_text()
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except (TypeError, ValueError):
                continue
            for item in self._walk_embedded_products(data, base_url):
                clean_url = item["url"]
                if clean_url in seen:
                    continue
                score = _score_result(item["title"], query)
                if score < 45:
                    continue
                seen.add(clean_url)
                results.append({**item, "score": score, "store": self.name})

        results.sort(key=lambda item: (-item["score"], item["price"] if item.get("price") is not None else 10**12))
        return results[:12]

    @staticmethod
    def _find_product_nodes(data, depth=0):
        """Find ProductGroup and usable Product nodes in common JSON-LD wrappers."""
        groups = []
        products = []

        def walk(node, level):
            if level > 6 or not isinstance(node, (dict, list)):
                return
            if isinstance(node, list):
                for item in node[:50]:
                    walk(item, level + 1)
                return

            raw_types = node.get("@type")
            types = raw_types if isinstance(raw_types, list) else [raw_types]
            if "ProductGroup" in types and isinstance(node.get("hasVariant"), list):
                groups.append(node)
                return
            if "Product" in types and isinstance(node.get("offers"), (dict, list)):
                products.append(node)

            graph = node.get("@graph")
            if isinstance(graph, list):
                walk(graph, level + 1)
            for key in ("mainEntity", "item", "product"):
                child = node.get(key)
                if isinstance(child, (dict, list)):
                    walk(child, level + 1)

        walk(data, depth)
        return groups, products

    @staticmethod
    def _first_offer(offers):
        if isinstance(offers, dict):
            return offers
        if isinstance(offers, list):
            return next((item for item in offers if isinstance(item, dict)), None)
        return None

    def _price_from_page_text(self, soup):
        for selector in (
            "[data-testid*='price']:not([data-testid*='old']):not([data-testid*='strikethrough'])",
            "[data-auto-id*='price']",
            "[class*='gl-price']",
            "[class*='price-value']",
        ):
            for element in soup.select(selector)[:5]:
                price = parse_price_text(element.get_text(" ", strip=True))
                if price and 50 < price < 200000:
                    return price
        return None

    def _apply_product_group(self, node, result, dbg):
        variants = node.get("hasVariant") or []
        size_variants = []
        for variant in variants:
            if not isinstance(variant, dict) or variant.get("size") in (None, ""):
                continue
            offer = self._first_offer(variant.get("offers"))
            if offer:
                size_variants.append((variant, offer))
        if not size_variants:
            return False

        sizes = []
        for variant, offer in size_variants:
            availability = str(offer.get("availability") or "").lower()
            sizes.append(
                {
                    "name": str(variant["size"]),
                    "size": str(variant["size"]),
                    "in_stock": "instock" in availability,
                    "sku": variant.get("sku"),
                    "stock_source": "json_ld:ProductGroup.hasVariant.offers.availability",
                }
            )

        stocked = [pair for pair in size_variants if "instock" in str(pair[1].get("availability") or "").lower()]
        _, price_offer = (stocked or size_variants)[0]
        try:
            result["current_price"] = float(price_offer["price"])
            result["price_source"] = "json_ld:ProductGroup.hasVariant.offers.price"
            result["confidence"] = 0.9
            dbg["price_candidates"].append({"source": "json_ld", "value": result["current_price"]})
        except (KeyError, TypeError, ValueError):
            pass

        specification = price_offer.get("priceSpecification")
        if isinstance(specification, dict) and "strikethrough" in str(specification.get("priceType") or "").lower():
            try:
                result["old_price"] = float(specification["price"])
            except (KeyError, TypeError, ValueError):
                pass

        result["sizes"] = sizes
        _finalize_stock_status(result)
        dbg["notes"].append(f"adidas_stock:{result['stock_count']}/{len(sizes)}:json_ld_product_group")
        return result["current_price"] is not None or bool(sizes)

    def _apply_single_product(self, node, result, dbg):
        offer = self._first_offer(node.get("offers"))
        if not offer:
            return False
        try:
            price = float(offer["price"])
        except (KeyError, TypeError, ValueError):
            return False
        if not 50 < price < 200000:
            return False

        result["current_price"] = price
        result["price_source"] = "json_ld:Product.offers.price"
        result["confidence"] = 0.6
        dbg["price_candidates"].append({"source": "json_ld_product_fallback", "value": price})
        availability = str(offer.get("availability") or "").lower()
        if availability:
            result["in_stock"] = "instock" in availability
            result["stock_status"] = "in_stock" if result["in_stock"] else "out_of_stock"
        specification = offer.get("priceSpecification")
        if isinstance(specification, dict) and "strikethrough" in str(specification.get("priceType") or "").lower():
            try:
                result["old_price"] = float(specification["price"])
            except (KeyError, TypeError, ValueError):
                pass
        dbg["notes"].append("adidas_fallback:single_product:no_size_data")
        return True

    def parse(self, html, url):
        soup = BeautifulSoup(html, "lxml")
        result = self.base_result(url)
        dbg = result["debug"]

        # Ortak baslik ve meta veri ayristirma (StoreEngine icerisinden)
        self.parse_common_meta(soup, result, url)

        groups = []
        products = []
        for script in soup.find_all("script", type="application/ld+json"):
            raw = script.string or script.get_text()
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                continue
            found_groups, found_products = self._find_product_nodes(data)
            groups.extend(found_groups)
            products.extend(found_products)

        applied = any(self._apply_product_group(node, result, dbg) for node in groups)
        if not applied:
            applied = any(self._apply_single_product(node, result, dbg) for node in products)
        if not applied and result["current_price"] is None:
            fallback_price = self._price_from_page_text(soup)
            if fallback_price:
                result["current_price"] = fallback_price
                result["price_source"] = "dom_text:adidas_price_label"
                result["confidence"] = 0.55
                dbg["notes"].append("adidas_fallback:dom_price:no_size_or_stock_data")
            else:
                dbg["notes"].append("adidas_no_data")

        # Sitedeki diger renk/model linklerini de topluyoruz
        result["variant_urls"] = _extract_variant_urls(soup, url)

        return result
