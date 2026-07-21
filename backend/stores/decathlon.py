"""Decathlon.com.tr özel mağaza motoru.

Standalone paketteki DecathlonStore'dan async'e çevrildi.
Fiyat: product:price:amount / product:original_price:amount meta etiketleri (güven 0.85)
Stok: "Stokta Mevcut" / "Stokta Mevcut Değil" metin örüntüsü (güven 0.75)
"""
import json
import re
from urllib.parse import parse_qs, urlparse

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
    supports_sizes = True
    supports_variants = True
    name = "Decathlon"
    slug = "decathlon"
    domains = ["decathlon.com.tr"]
    search_path = "https://www.decathlon.com.tr/search?Ntt={q}"
    product_pattern = None
    priority = 10
    # Decathlon's plain HTTP route currently returns 403 while its public page
    # renders in a regular browser.  Use the shared standards-based Playwright
    # pool directly; no stealth, fingerprint masking, proxy or CAPTCHA bypass.
    js_search = True
    use_browser = True
    search_browser_fallback = False
    search_timeout_seconds = 55
    browser_wait_selector = (
        "a[href*='R-p-'], article, .product-card, .dpb-product-model-link, "
        "[data-testid='product-card']"
    )

    async def fetch(self, url, max_retries=3, backoff_seconds=1.5, timeout_seconds=15):
        return await super().fetch(
            url,
            max_retries=max_retries,
            backoff_seconds=backoff_seconds,
            timeout_seconds=timeout_seconds,
        )

    @staticmethod
    def _extract_dkt_payload(html):
        """Read Decathlon's server-rendered ``__DKT`` JSON assignment."""
        decoder = json.JSONDecoder()
        for marker in re.finditer(r"\b__DKT\s*=", html):
            start = html.find("{", marker.end())
            if start < 0:
                continue
            try:
                payload, _ = decoder.raw_decode(html[start:])
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            if isinstance(payload, dict):
                return payload
        return None

    @staticmethod
    def _dkt_components(payload):
        if not isinstance(payload, dict):
            return []
        context = payload.get("_ctx") if isinstance(payload.get("_ctx"), dict) else payload
        components = context.get("data") if isinstance(context, dict) else None
        return components if isinstance(components, list) else []

    @classmethod
    def _dkt_supermodel(cls, payload):
        for component in cls._dkt_components(payload):
            if not isinstance(component, dict) or component.get("type") != "Supermodel":
                continue
            data = component.get("data")
            if isinstance(data, dict):
                return data
        return None

    @staticmethod
    def _select_dkt_model(supermodel, url):
        if not isinstance(supermodel, dict):
            return None
        models = [item for item in supermodel.get("models") or [] if isinstance(item, dict)]
        if not models:
            return None
        model_id = (parse_qs(urlparse(url).query).get("mc") or [None])[0]
        if model_id:
            selected = next((item for item in models if str(item.get("modelId")) == str(model_id)), None)
            if selected:
                return selected
        return models[0]

    @staticmethod
    def _dkt_image(node):
        if not isinstance(node, dict):
            return None
        image = node.get("image")
        if isinstance(image, str):
            return image
        if isinstance(image, dict):
            media = image.get("media")
            media_resource = media.get("resource") if isinstance(media, dict) else None
            return image.get("url") or image.get("src") or media_resource
        images = node.get("images")
        if isinstance(images, dict):
            product_images = images.get("product")
            if isinstance(product_images, list) and product_images:
                return DecathlonEngine._dkt_image(product_images[0])
        return None

    @staticmethod
    def _dkt_price(node):
        if not isinstance(node, dict):
            return None
        price = parse_price_text(node.get("price"))
        if price and 0 < price < 200000:
            return price
        for sku in node.get("skus") or []:
            if not isinstance(sku, dict) or sku.get("isNotAvailable") or sku.get("isNotAvailableOnline"):
                continue
            price = parse_price_text(sku.get("price"))
            if price and 0 < price < 200000:
                return price
        return None

    @staticmethod
    def _dkt_old_price(model, current_price):
        if not current_price or not isinstance(model, dict):
            return None
        candidates = []
        for node in [model, *(item for item in model.get("skus") or [] if isinstance(item, dict))]:
            for key in ("previousPrice", "originalPrice", "crossedPrice", "strikethroughPrice"):
                price = parse_price_text(node.get(key))
                if price and price > current_price:
                    candidates.append(price)
        return min(candidates) if candidates else None

    @staticmethod
    def _model_url(base_url, raw_url):
        if not raw_url:
            return None
        raw_url = str(raw_url).strip()
        if raw_url.startswith("p/"):
            raw_url = "/" + raw_url
        return _absolute_url(base_url, raw_url)

    def _apply_dkt_product(self, payload, url, result):
        supermodel = self._dkt_supermodel(payload)
        model = self._select_dkt_model(supermodel, url)
        if not model:
            return False

        result["title"] = str(model.get("webLabel") or supermodel.get("webLabel") or result["title"] or "").strip()
        image = self._dkt_image(model)
        if image:
            result["image"] = _absolute_url(url, image)

        price = self._dkt_price(model)
        if price:
            result["current_price"] = price
            result["old_price"] = self._dkt_old_price(model, price)
            result["price_source"] = "decathlon_dkt:model.price"
            result["confidence"] = 0.95
            result["debug"]["price_candidates"].append(
                {"source": "decathlon_dkt:model.price", "value": price}
            )

        sizes = []
        seen = set()
        for sku in model.get("skus") or []:
            if not isinstance(sku, dict):
                continue
            size = str(sku.get("size") or "").replace("\\u002F", "/").strip().rstrip(".")
            if not size or size in seen:
                continue
            seen.add(size)
            sizes.append(
                {
                    "name": size,
                    "size": size,
                    "in_stock": not bool(sku.get("isNotAvailable") or sku.get("isNotAvailableOnline")),
                    "sku": str(sku.get("skuId") or sku.get("skuCode") or "") or None,
                    "stock_source": "decathlon_dkt:sku_availability",
                }
            )
        result["sizes"] = sizes
        _finalize_stock_status(result)

        selected_model_id = str(model.get("modelId") or "")
        variants = []
        for candidate in supermodel.get("models") or []:
            if not isinstance(candidate, dict) or str(candidate.get("modelId") or "") == selected_model_id:
                continue
            variant_url = self._model_url(url, candidate.get("url"))
            if variant_url and variant_url not in variants:
                variants.append(variant_url)
        result["variant_urls"] = variants
        result["debug"]["notes"].append(
            f"decathlon_dkt:model={selected_model_id};stock={result['stock_count']}/{len(sizes)}"
        )
        return True

    def _walk_dkt_product_nodes(self, node, depth=0):
        if depth > 9:
            return
        if isinstance(node, list):
            for item in node[:300]:
                yield from self._walk_dkt_product_nodes(item, depth + 1)
            return
        if not isinstance(node, dict):
            return

        raw_url = node.get("url") or node.get("productUrl") or node.get("pdpUrl")
        title = node.get("webLabel") or node.get("productName") or node.get("name")
        if raw_url and title and ("/_/R-p-" in str(raw_url) or str(raw_url).startswith(("p/", "/p/"))):
            yield node

        for value in node.values():
            if isinstance(value, (dict, list)):
                yield from self._walk_dkt_product_nodes(value, depth + 1)

    def parse(self, html, url):
        soup = BeautifulSoup(html, "lxml")
        result = self.base_result(url)
        dbg = result["debug"]

        # --- Baslik ve Gorsel (generic meta) ---
        self.parse_common_meta(soup, result, url)

        dkt_payload = self._extract_dkt_payload(html)
        if self._apply_dkt_product(dkt_payload, url, result):
            return result

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
        seen = set()
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
                seen.add(href)

        payload = self._extract_dkt_payload(html)
        for node in self._walk_dkt_product_nodes(payload):
            title = " ".join(str(node.get("webLabel") or node.get("productName") or node.get("name") or "").split())
            href = self._model_url(base_url, node.get("url") or node.get("productUrl") or node.get("pdpUrl"))
            if not title or not href or href in seen or not self.supports_url(href):
                continue
            score = _score_result(title, query)
            if score < 60:
                continue
            seen.add(href)
            results.append(
                {
                    "title": title[:160],
                    "url": href,
                    "price": self._dkt_price(node),
                    "image": _absolute_url(base_url, self._dkt_image(node)),
                    "score": score,
                    "store": self.name,
                }
            )
        results.sort(key=lambda item: -item["score"])
        return results[:12]
