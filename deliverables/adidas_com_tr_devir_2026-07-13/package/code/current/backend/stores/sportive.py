"""Sportive.com.tr özel mağaza motoru.

Standalone paketteki SportiveStore'dan async'e çevrildi.
Fiyat: JSON-LD Product.offers.price (güven 0.9) → meta[name="og:price:amount"] fallback (güven 0.7)
       NOT: Sportive, property= yerine name= kullanıyor!
Stok: <button id="42,5"> içindeki <p>Tükendi</p> metni (güven 0.85)
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
    _extract_variant_urls,
    _finalize_stock_status,
    _score_result,
    extract_json_ld_products,
    parse_price_text,
)
from product_identity import STYLE_CODE_RE

# Beden butonlari "41", "42,5" gibi id'ler kullanir
_SIZE_ID_PATTERN = re.compile(r"^\d{2}(?:,\d)?$")


def _find_json_array_end(text, start_index=0):
    depth = 0
    in_string = False
    escaped = False
    for idx in range(start_index, len(text)):
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
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return idx
    return -1


def _extract_flight_products(html):
    marker = '\\"products\\":'
    search_from = 0
    while True:
        marker_pos = html.find(marker, search_from)
        if marker_pos == -1:
            return
        array_start = html.find("[", marker_pos + len(marker))
        if array_start == -1:
            return
        script_end = html.find("</script>", array_start)
        if script_end == -1:
            script_end = len(html)
        decoded = html[array_start:script_end].replace('\\"', '"')
        array_end = _find_json_array_end(decoded)
        if array_end != -1:
            try:
                products = json.loads(decoded[: array_end + 1])
            except (TypeError, ValueError, json.JSONDecodeError):
                products = []
            if isinstance(products, list):
                for product in products:
                    if isinstance(product, dict):
                        yield product
        search_from = marker_pos + len(marker)


def _normalize_text(text):
    """Turk karakter normalizasyonu (tukendi kontrolu icin)."""
    normalized = (text or "").strip().lower()
    return (
        normalized.replace("ü", "u")
        .replace("ğ", "g")
        .replace("ı", "i")
        .replace("ş", "s")
        .replace("ö", "o")
        .replace("ç", "c")
    )


class SportiveEngine(StoreEngine):
    name = "Sportive"
    slug = "sportive"
    domains = ["sportive.com.tr"]
    search_path = "https://www.sportive.com.tr/list/?search_text={q}"
    product_pattern = None
    priority = 2
    js_search = False
    use_browser = False

    async def fetch(self, url, max_retries=2, backoff_seconds=1, timeout_seconds=15):
        return await super().fetch(
            url,
            max_retries=max_retries,
            backoff_seconds=backoff_seconds,
            timeout_seconds=timeout_seconds,
        )

    def parse(self, html, url):
        soup = BeautifulSoup(html, "lxml")
        result = self.base_result(url)
        dbg = result["debug"]
        products = list(extract_json_ld_products(soup))

        # Sportive'in og:title alani her urunde ayni pazarlama metnini tasiyor.
        title_el = soup.select_one("h1[data-testid*='product-name'], [data-testid='product-name']")
        if title_el:
            result["title"] = title_el.get_text(" ", strip=True)[:160]
        elif products and products[0].get("name"):
            result["title"] = str(products[0]["name"]).strip()[:160]
        elif soup.title and soup.title.string:
            result["title"] = soup.title.string.split(" | ", 1)[0].strip()[:160]

        style_codes = [match.group(0).upper() for match in STYLE_CODE_RE.finditer(result.get("title") or "")]
        if style_codes:
            result["model_code"] = style_codes[-1]

        # --- Baslik disindaki ortak meta alanlari ---
        self.parse_common_meta(soup, result, url)

        # --- 1. Fiyat: JSON-LD Product.offers.price (en guvenilir) ---
        for prod in products:
            brand = prod.get("brand")
            if brand and not result.get("brand"):
                result["brand"] = brand.get("name") if isinstance(brand, dict) else str(brand)
            offers = prod.get("offers")
            offer = self._first_offer(offers)
            if not offer or offer.get("price") is None:
                continue
            try:
                price = float(offer["price"])
                result["current_price"] = price
                result["price_source"] = "json_ld:Product.offers.price"
                result["confidence"] = 0.9
                dbg["price_candidates"].append({"source": "json_ld", "value": price})
                break
            except (ValueError, TypeError):
                pass

        # --- 2. Fallback: meta[name="og:price:amount"] ---
        # ONEMLI: Sportive property= yerine name= kullanıyor!
        if result["current_price"] is None:
            price_tag = soup.find("meta", attrs={"name": "og:price:amount"})
            if price_tag and price_tag.get("content"):
                try:
                    price = float(price_tag["content"])
                    result["current_price"] = price
                    result["price_source"] = "meta[name=og:price:amount]"
                    result["confidence"] = 0.7
                    dbg["price_candidates"].append({"source": "meta_name_og", "value": price})
                except ValueError:
                    pass

        # --- 3. Stok: <button id="{beden}"> ve "Tükendi" marker ---
        sizes_data = []
        for button in soup.find_all("button", id=True):
            size_label = button["id"]
            if not _SIZE_ID_PATTERN.match(size_label):
                continue

            sold_out = any(
                _normalize_text(p.get_text(strip=True)) == "tukendi"
                for p in button.find_all("p")
            )
            sizes_data.append({
                "name": size_label,
                "size": size_label,
                "in_stock": not sold_out,
                "sku": None,
            })

        result["sizes"] = sizes_data
        _finalize_stock_status(result)

        if sizes_data:
            dbg["notes"].append(f"sportive_stock: {result['stock_count']}/{len(sizes_data)} beden stokta")

        # --- Varyasyon kesfet ---
        result["variant_urls"] = _extract_variant_urls(soup, url)

        return result

    @staticmethod
    def _first_offer(offers):
        """JSON-LD offers alanini normalize et (dict veya list olabilir)."""
        if isinstance(offers, dict):
            nested = offers.get("offers")
            if isinstance(nested, list) and nested:
                return nested[0]
            return offers
        if isinstance(offers, list) and offers:
            return offers[0]
        return None

    def parse_search(self, html, query, base_url):
        """Sportive arama sonuçlarını ayrıştır (JS-rendered)."""
        soup = BeautifulSoup(html, "lxml")
        results = []
        seen = set()
        # Sportive arama sonuclari genellikle product-card icinde
        for card in soup.select(".product-card, .product-item, [data-testid='product-card'], .search-product"):
            a_tag = card.find("a", href=True) if card.name != "a" else card
            if not a_tag or not a_tag.get("href"):
                continue
            href = a_tag["href"]
            if not href.startswith("http"):
                from urllib.parse import urljoin
                href = urljoin(base_url, href)
            title = ""
            title_el = card.select_one("h2, h3, .product-name, .product-title")
            if title_el:
                title = title_el.get_text(strip=True)
            elif a_tag.get("title"):
                title = a_tag["title"]
            if not title:
                title = a_tag.get_text(strip=True)[:100]
            price = None
            price_el = card.select_one(".product-price, .price, .amount")
            if price_el:
                price = parse_price_text(price_el.get_text(strip=True))
            img = None
            img_el = card.select_one("img")
            if img_el:
                img = _absolute_url(base_url, img_el.get("src") or img_el.get("data-src"))
            if title and "sportive" in href.lower():
                score = _score_result(title, query)
                if score < 45:
                    continue
                clean_url = href.split("?")[0]
                if clean_url in seen:
                    continue
                seen.add(clean_url)
                results.append({
                    "title": title,
                    "url": clean_url,
                    "price": price,
                    "image": img,
                    "score": score,
                    "store": self.name,
                })

        for product in _extract_flight_products(html):
            if product.get("is_listable") is False or product.get("in_stock") is False:
                continue
            if str(product.get("stock") or "").strip() == "0":
                continue
            title = str(product.get("name") or "").strip()
            url = product.get("absolute_url") or product.get("url")
            full_url = _absolute_url(base_url, url)
            if not title or not full_url or "sportive.com.tr" not in full_url.lower():
                continue
            score = _score_result(title, query)
            if score < 45:
                continue
            clean_url = full_url.split("?")[0]
            if clean_url in seen:
                continue
            image = product.get("image")
            for image_item in product.get("productimage_set") or []:
                if isinstance(image_item, dict) and image_item.get("image"):
                    image = image_item["image"]
                    break
            seen.add(clean_url)
            results.append({
                "title": title[:160],
                "url": clean_url,
                "price": parse_price_text(product.get("price") or product.get("retail_price")),
                "image": _absolute_url(base_url, image),
                "score": score,
                "store": self.name,
            })
        results.sort(key=lambda item: -item["score"])
        return results[:12]
