"""Sportive.com.tr özel mağaza motoru.

Standalone paketteki SportiveStore'dan async'e çevrildi.
Fiyat: JSON-LD Product.offers.price (güven 0.9) → meta[name="og:price:amount"] fallback (güven 0.7)
       NOT: Sportive, property= yerine name= kullanıyor!
Stok: <button id="42,5"> içindeki <p>Tükendi</p> metni (güven 0.85)
"""
import json
import re
from bs4 import BeautifulSoup

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engines import StoreEngine, parse_price_text, extract_json_ld_products, _extract_variant_urls


# Beden butonlari "41", "42,5" gibi id'ler kullanir
_SIZE_ID_PATTERN = re.compile(r"^\d{2}(?:,\d)?$")


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
    search_path = "https://www.sportive.com.tr/arama?q={q}"
    product_pattern = None
    priority = 2
    js_search = True
    use_browser = False

    def parse(self, html, url):
        soup = BeautifulSoup(html, "lxml")
        result = self.base_result(url)
        dbg = result["debug"]

        # --- Baslik ve Gorsel (generic meta) ---
        self.parse_common_meta(soup, result)

        # --- 1. Fiyat: JSON-LD Product.offers.price (en guvenilir) ---
        for prod in extract_json_ld_products(soup):
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
        result["stock_count"] = sum(1 for s in sizes_data if s["in_stock"])
        result["in_stock"] = result["stock_count"] > 0

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
                img = img_el.get("src") or img_el.get("data-src")
            if title and "sportive" in href.lower():
                from engines import _score_result
                results.append({
                    "title": title,
                    "url": href,
                    "price": price,
                    "image": img,
                    "score": _score_result(title, query),
                })
        return results[:12]
