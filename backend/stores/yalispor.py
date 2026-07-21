import html as html_lib
import json
import re

from bs4 import BeautifulSoup

from engines import (
    StoreEngine,
    _clean_image_url,
    _finalize_stock_status,
    _score_result,
    parse_price_text,
)


class YaliSporEngine(StoreEngine):
    supports_sizes = True
    name = "Yali Spor"
    slug = "yalispor"
    domains = ["yalispor.com.tr"]
    search_path = "https://www.yalispor.com.tr/tum-urunler?q={q}"
    product_pattern = r"/[a-z0-9-]+(?:-\d+)?$"
    priority = 8

    def _is_size_text(self, text):
        text = " ".join(str(text or "").split())
        if not text:
            return False
        return bool(re.search(r"\d", text)) and len(text) <= 24

    def _size_disabled(self, el):
        classes = " ".join(el.get("class") or []).lower()
        nested_input = el.find("input")
        return (
            el.has_attr("disabled")
            or str(el.get("aria-disabled", "")).lower() == "true"
            or bool(nested_input and nested_input.has_attr("disabled"))
            or any(token in classes for token in ("disabled", "passive", "sold", "unavailable", "tukendi"))
        )

    def _append_size(self, sizes, seen, text, in_stock, sku=None, source="yalispor_size_selector"):
        text = " ".join(str(text or "").split())
        if not self._is_size_text(text) or text in seen:
            return
        seen.add(text)
        sizes.append(
            {
                "name": text,
                "size": text,
                "in_stock": bool(in_stock),
                "sku": sku,
                "stock_source": source,
            }
        )

    def _card_data(self, card):
        raw = html_lib.unescape(card.get("data-gta") or "")
        if not raw:
            return {}
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except (TypeError, ValueError):
            return {}

    def _card_price(self, card, data):
        for selector in (".kategoriUrunFiyat", ".price", "[class*='price']", "[class*='Fiyat']"):
            el = card.select_one(selector)
            if not el:
                continue
            price = parse_price_text(el.get_text(" ", strip=True))
            if price and 50 < price < 200000:
                return price
        for key in ("price", "value"):
            value = data.get(key)
            if isinstance(value, (int, float)) and 50 < float(value) < 200000:
                return round(float(value), 2)
            price = parse_price_text(value)
            if price and 50 < price < 200000:
                return price
        return None

    def _card_image(self, card, data, base_url):
        image = _clean_image_url(base_url, data.get("product_image_url"))
        if image:
            return image
        img = card.find("img")
        if not img:
            return None
        for attr in ("src", "data-src", "data-rsrc", "data-original", "data-lazy"):
            image = _clean_image_url(base_url, img.get(attr))
            if image:
                return image
        return None

    def _card_title(self, card, data):
        title_el = card.select_one(".card-title")
        title = title_el.get_text(" ", strip=True) if title_el else ""
        if not title:
            img = card.find("img")
            title = (img.get("alt") if img else None) or data.get("item_name") or ""
        variant = str(data.get("item_variant") or "").strip()
        if variant and variant.lower() not in title.lower():
            title = f"{title} {variant}".strip()
        return " ".join(str(title).split())

    def parse_search(self, html, query, base_url):
        soup = BeautifulSoup(html, "lxml")
        out = []
        seen = set()

        for card in soup.select(".product-list-horizontal .product[data-gta], .item.product[data-gta]"):
            data = self._card_data(card)
            link = card.select_one("a[href]")
            if not link:
                continue
            url = self._absolute(base_url, link.get("href")).split("?")[0]
            if url in seen or not self.supports_url(url) or not self.is_product_link(url):
                continue
            title = self._card_title(card, data)
            score = _score_result(title, query)
            if score < 55:
                continue
            seen.add(url)
            out.append(
                {
                    "title": title[:160],
                    "url": url,
                    "score": score,
                    "image": self._card_image(card, data, base_url),
                    "price": self._card_price(card, data),
                    "store": self.name,
                }
            )

        out.sort(key=lambda item: (-item["score"], item["price"] if item.get("price") is not None else 10**12))
        return out[:10]

    def parse(self, html, url):
        result = super().parse(html, url)
        soup = BeautifulSoup(html, "lxml")

        if not result.get("title"):
            title_el = soup.select_one("h1, .product-title, .card-title")
            if title_el:
                result["title"] = title_el.get_text(" ", strip=True)

        if not result.get("current_price"):
            for selector in (".kategoriUrunFiyat", ".price", ".product-price"):
                el = soup.select_one(selector)
                price = parse_price_text(el.get_text(" ", strip=True)) if el else None
                if price and 50 < price < 200000:
                    result["current_price"] = price
                    result["price_source"] = f"yalispor:{selector}"
                    result["confidence"] = 0.75
                    break

        if not result.get("old_price"):
            old_el = soup.select_one(".kategoriUrunEskiFiyat, .old-price")
            old_price = parse_price_text(old_el.get_text(" ", strip=True)) if old_el else None
            if old_price and result.get("current_price") and old_price > result["current_price"]:
                result["old_price"] = old_price

        sizes = []
        seen_sizes = set()

        body_size = soup.select_one("#body-size")
        if body_size:
            for el in body_size.select(".product-size label, label"):
                input_el = el.find("input")
                text = el.get_text(" ", strip=True)
                self._append_size(
                    sizes,
                    seen_sizes,
                    text,
                    not self._size_disabled(el),
                    sku=(input_el.get("value") if input_el else None),
                    source="yalispor_body_size",
                )

            for option in body_size.select("select[name='size'] option"):
                value = str(option.get("value") or "").strip()
                if value in ("", "0"):
                    continue
                self._append_size(
                    sizes,
                    seen_sizes,
                    option.get_text(" ", strip=True),
                    not self._size_disabled(option),
                    sku=value,
                    source="yalispor_size_select",
                )

        for el in soup.select(".variant-box, .product-size-list button, .product-sizes button, .product-sizes label"):
            text = el.get_text(" ", strip=True)
            if not self._is_size_text(text):
                continue
            self._append_size(
                sizes,
                seen_sizes,
                text,
                not self._size_disabled(el),
                sku=el.get("data-id") or el.get("data-sku"),
            )
        if sizes:
            result["sizes"] = sizes
        _finalize_stock_status(result)
        return result

    def _absolute(self, base_url, href):
        from urllib.parse import urljoin

        return urljoin(base_url, href or "")
