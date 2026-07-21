"""Decathlon.com.tr özel mağaza motoru.

Standalone paketteki DecathlonStore'dan async'e çevrildi.
Fiyat: product:price:amount / product:original_price:amount meta etiketleri (güven 0.85)
Stok: "Stokta Mevcut" / "Stokta Mevcut Değil" metin örüntüsü (güven 0.75)
"""
import re
from bs4 import BeautifulSoup

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engines import (
    StoreEngine,
    parse_price_text,
    extract_json_ld_products,
    _first_offer,
    _absolute_url,
    _extract_variant_urls,
    _finalize_stock_status,
    _score_result,
)


class DecathlonEngine(StoreEngine):
    name = "Decathlon"
    slug = "decathlon"
    domains = ["decathlon.com.tr"]
    search_path = "https://www.decathlon.com.tr/search?Ntt={q}"
    product_pattern = None
    priority = 10
    js_search = False
    use_browser = False

    async def fetch(self, url, max_retries=3, backoff_seconds=1.5, timeout_seconds=15):
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

        # --- Baslik ve Gorsel (generic meta) ---
        self.parse_common_meta(soup, result, url)

        # --- Fiyat: once guncel satis fiyati, yoksa orijinal fiyat ---
        price_tag = soup.find("meta", attrs={"property": "product:price:amount"})
        source = "product:price:amount"
        if not price_tag or not price_tag.get("content"):
            price_tag = soup.find("meta", attrs={"property": "product:original_price:amount"})
            source = "product:original_price:amount"

        if price_tag and price_tag.get("content"):
            try:
                price = float(price_tag["content"])
                result["current_price"] = price
                result["price_source"] = source
                result["confidence"] = 0.85
                dbg["price_candidates"].append({"source": source, "value": price})
            except ValueError:
                pass

        # Eski fiyat (orijinal) ayrica kontrol et
        if result["current_price"] is not None:
            orig_tag = soup.find("meta", attrs={"property": "product:original_price:amount"})
            if orig_tag and orig_tag.get("content"):
                try:
                    orig_price = float(orig_tag["content"])
                    if orig_price > result["current_price"]:
                        result["old_price"] = orig_price
                except ValueError:
                    pass

        # --- Stok: "Stokta Mevcut" / "Stokta Mevcut Değil" metin örüntüsü ---
        full_text = soup.get_text(" ", strip=True)
        sizes_data = []
        pattern = re.compile(r'(\d{2}(?:[.,]\d)?)\s*Stokta Mevcut(\s*Değil)?', re.IGNORECASE)
        for match in pattern.finditer(full_text):
            size_label = match.group(1)
            is_out_of_stock = bool(match.group(2))
            if any(s["name"] == size_label for s in sizes_data):
                continue
            sizes_data.append({
                "name": size_label,
                "size": size_label,
                "in_stock": not is_out_of_stock,
                "sku": None,
            })

        offer_availability_by_sku = {}
        product_level_availability = None
        for prod in extract_json_ld_products(soup):
            offers = prod.get("offers")
            if not isinstance(offers, list):
                offers = [offers] if offers else []
            for offer in offers:
                offer = _first_offer(offer)
                if not isinstance(offer, dict):
                    continue
                availability = str(offer.get("availability") or "")
                sku = str(offer.get("sku") or "").strip()
                if availability and not product_level_availability:
                    product_level_availability = availability
                if sku and availability:
                    offer_availability_by_sku[sku] = availability

        seen_size_names = {s["name"] for s in sizes_data}
        for match in re.finditer(r'"skuId"\s*:\s*"([^"]+)"\s*,\s*"size"\s*:\s*"([^"]+)"', html):
            sku, size_label = match.groups()
            size_label = size_label.replace("\\u002F", "/").strip()
            if not size_label or size_label in seen_size_names:
                continue
            availability = offer_availability_by_sku.get(sku) or product_level_availability or ""
            sizes_data.append({
                "name": size_label,
                "size": size_label,
                "in_stock": "instock" in availability.lower(),
                "sku": sku,
                "stock_source": "decathlon_skus_json_ld",
            })
            seen_size_names.add(size_label)

        if not sizes_data and product_level_availability:
            availability_key = product_level_availability.lower()
            if "instock" in availability_key:
                result["stock_status"] = "in_stock"
            elif "outofstock" in availability_key:
                result["stock_status"] = "out_of_stock"

        result["sizes"] = sizes_data
        _finalize_stock_status(result)

        if sizes_data:
            dbg["notes"].append(f"decathlon_stock: {result['stock_count']}/{len(sizes_data)} beden stokta")

        # --- Varyasyon kesfet ---
        result["variant_urls"] = _extract_variant_urls(soup, url)

        return result

    def parse_search(self, html, query, base_url):
        """Decathlon arama sonuçlarını ayrıştır."""
        soup = BeautifulSoup(html, "lxml")
        results = []
        # Decathlon arama sonuclari genellikle article veya product-card icinde
        for card in soup.select("article, .product-card, .dpb-product-model-link, [data-testid='product-card']"):
            a_tag = card.find("a", href=True) if card.name != "a" else card
            if not a_tag or not a_tag.get("href"):
                continue
            href = a_tag["href"]
            if not href.startswith("http"):
                from urllib.parse import urljoin
                href = urljoin(base_url, href)
            title = ""
            title_el = card.select_one("h2, h3, .product-title, .dpb-product-model-link__title")
            if title_el:
                title = title_el.get_text(strip=True)
            elif a_tag.get("title"):
                title = a_tag["title"]
            if not title:
                title = a_tag.get_text(strip=True)[:100]
            price = None
            price_el = card.select_one(".dpb-product-model-link__price, .product-price, .price")
            if price_el:
                price = parse_price_text(price_el.get_text(strip=True))
            img = None
            img_el = card.select_one("img")
            if img_el:
                img = _absolute_url(base_url, img_el.get("src") or img_el.get("data-src"))
            if title and "decathlon" in href.lower():
                score = _score_result(title, query)
                if score < 60:
                    continue
                results.append({
                    "title": title,
                    "url": href,
                    "price": price,
                    "image": img,
                    "score": score,
                    "store": self.name,
                })
        results.sort(key=lambda item: -item["score"])
        return results[:12]
