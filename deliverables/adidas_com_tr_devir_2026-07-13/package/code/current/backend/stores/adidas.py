"""Adidas.com.tr özel mağaza motoru.

Kullanıcının yazdığı JSON-LD (ProductGroup) tabanlı mantık kullanılarak
asenkron yapıya entegre edilmiştir.
"""
import json
import os
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
    name = "Adidas Türkiye"
    slug = "adidas"
    domains = ["adidas.com.tr"]
    search_path = "https://www.adidas.com.tr/tr/search?q={q}"
    product_pattern = r"/[A-Z]{2}\d{4}\.html"
    priority = 21
    js_search = True
    use_browser = True  # Adidas Cloudflare 403 hatasi verdigi icin Playwright kullanimi sarttir
    sitemap_title_prefix = "adidas"

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

    def parse(self, html, url):
        soup = BeautifulSoup(html, "lxml")
        result = self.base_result(url)
        dbg = result["debug"]

        # Ortak baslik ve meta veri ayristirma (StoreEngine icerisinden)
        self.parse_common_meta(soup, result, url)

        # Kullanicinin yazdigi kusursuz JSON-LD (ProductGroup) ayristirma mantigi
        for script in soup.find_all("script", type="application/ld+json"):
            if not script.string:
                continue
            try:
                data = json.loads(script.string)
            except (json.JSONDecodeError, TypeError):
                continue

            if not isinstance(data, dict) or data.get("@type") != "ProductGroup":
                continue

            variants = data.get("hasVariant", [])
            # Gercek beden varyantlari (size ve offers)
            size_variants = [v for v in variants if v.get("size") and v.get("offers")]

            if not size_variants:
                break

            sizes_data = []
            for v in size_variants:
                offers = v["offers"]
                availability = str(offers.get("availability", "")).lower()
                in_stock = "instock" in availability

                sizes_data.append({
                    "name": str(v["size"]),
                    "size": str(v["size"]),
                    "in_stock": in_stock,
                    "sku": v.get("sku"),
                    "stock_source": "json_ld:ProductGroup.hasVariant.offers.availability",
                })

            in_stock_variants = [v for v in size_variants if "instock" in str(v["offers"].get("availability", "")).lower()]
            price_source_variant = in_stock_variants[0] if in_stock_variants else size_variants[0]
            offers = price_source_variant["offers"]

            try:
                result["current_price"] = float(offers["price"])
                result["price_source"] = "json_ld:ProductGroup.hasVariant.offers.price"
                result["confidence"] = 0.9
                dbg["price_candidates"].append({"source": "json_ld", "value": result["current_price"]})
            except (KeyError, TypeError, ValueError):
                pass

            price_spec = offers.get("priceSpecification")
            if isinstance(price_spec, dict) and "strikethrough" in str(price_spec.get("priceType", "")).lower():
                try:
                    result["old_price"] = float(price_spec["price"])
                except (KeyError, TypeError, ValueError):
                    pass

            result["sizes"] = sizes_data
            _finalize_stock_status(result)
            
            if sizes_data:
                dbg["notes"].append(f"adidas_stock: {result['stock_count']}/{len(sizes_data)} beden stokta (json_ld)")
            break

        # Sitedeki diger renk/model linklerini de topluyoruz
        result["variant_urls"] = _extract_variant_urls(soup, url)

        return result
