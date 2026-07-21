import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from engines import (
    StoreEngine,
    _clean_image_url,
    _finalize_stock_status,
    _score_result,
    parse_price_text,
)


class KaptanSporEngine(StoreEngine):
    name = "Kaptan Spor"
    slug = "kaptanspor"
    domains = ["kaptanspor.com.tr"]
    search_path = "https://kaptanspor.com.tr/arama/?q={q}"
    product_pattern = r"-[Pp]\d+/?(?:$|[?#])"
    priority = 10

    def _parse_price(self, value):
        text = str(value or "").replace("\xa0", " ")
        match = re.search(r"\d[\d.,]*", text)
        if not match:
            return None
        token = match.group(0).rstrip(".,")
        if re.fullmatch(r"\d{1,3}(?:,\d{3})+\.\d{1,2}", token):
            return round(float(token.replace(",", "")), 2)
        return parse_price_text(token)

    def _image_from_card(self, card, base_url):
        image_el = card.select_one("img.img-product, .product-img img, img")
        if not image_el:
            return None
        for attr in ("data-src", "data-rsrc", "data-original", "data-lazy", "src"):
            image = _clean_image_url(base_url, image_el.get(attr))
            if image and not image.lower().endswith(("/load.gif", "/loading.gif")):
                return image
        return None

    def parse_search(self, html, query, base_url):
        soup = BeautifulSoup(html, "lxml")
        out = []
        seen = set()
        parsed_base = urlparse(base_url)
        site_root = f"{parsed_base.scheme}://{parsed_base.netloc}/"

        for card in soup.select(".card-product"):
            link = card.select_one("a.product-img[href], a.fw-6.link[href], a[href]")
            if not link:
                continue
            url = urljoin(site_root, link.get("href") or "").split("?", 1)[0]
            if url in seen or not self.supports_url(url) or not self.is_product_link(url):
                continue

            title_el = card.select_one("a.fw-6.link, .product-title, [class*='product-name']")
            title = title_el.get_text(" ", strip=True) if title_el else ""
            if not title:
                image_el = card.select_one("img.img-product, .product-img img, img")
                title = (image_el.get("alt") if image_el else "") or ""
            title = " ".join(title.split())
            score = _score_result(title, query)
            if len(title) < 8 or score < 50:
                continue

            price_el = card.select_one(
                ".cat-detail-products-box-fiyat-mevcut, .price-on-sale, .current-price"
            )
            price = self._parse_price(price_el.get_text(" ", strip=True)) if price_el else None
            seen.add(url)
            out.append(
                {
                    "title": title[:160],
                    "url": url,
                    "score": score,
                    "image": self._image_from_card(card, site_root),
                    "price": price,
                    "store": self.name,
                }
            )

        out.sort(key=lambda item: (-item["score"], item["price"] if item.get("price") is not None else 10**12))
        return out[:10]

    def _size_is_disabled(self, input_el, label_el):
        classes = " ".join(
            (input_el.get("class") or []) + ((label_el.get("class") or []) if label_el else [])
        ).lower()
        return (
            input_el.has_attr("disabled")
            or str(input_el.get("aria-disabled", "")).lower() == "true"
            or bool(label_el and label_el.has_attr("disabled"))
            or bool(label_el and str(label_el.get("aria-disabled", "")).lower() == "true")
            or any(token in classes for token in ("disabled", "sold", "unavailable", "tukendi"))
        )

    def parse(self, html, url):
        result = super().parse(html, url)
        soup = BeautifulSoup(html, "lxml")

        if result.get("title"):
            result["title"] = re.sub(
                r"\s+-\s+Kaptan Spor\s*\|.*$", "", result["title"], flags=re.IGNORECASE
            ).strip()

        if result.get("current_price") is None:
            price_el = soup.select_one(
                ".tf-product-info-price .price-on-sale, .price-on-sale, "
                ".cat-detail-products-box-fiyat-mevcut"
            )
            price = self._parse_price(price_el.get_text(" ", strip=True)) if price_el else None
            if price and 50 < price < 200000:
                result["current_price"] = price
                result["price_source"] = "kaptanspor:current_price"

        old_price_el = soup.select_one(
            ".tf-product-info-price .compare-at-price, .compare-at-price, "
            ".cat-detail-products-box-fiyat-eski"
        )
        old_price = self._parse_price(old_price_el.get_text(" ", strip=True)) if old_price_el else None
        if old_price and result.get("current_price") and old_price > result["current_price"]:
            result["old_price"] = old_price

        sizes = []
        seen_sizes = set()
        for input_el in soup.select("input.size-selector-input, input[name^='var'][type='radio']"):
            input_id = input_el.get("id")
            label_el = soup.find("label", attrs={"for": input_id}) if input_id else None
            if not label_el:
                label_el = input_el.find_parent("label")
            size = " ".join(label_el.get_text(" ", strip=True).split()) if label_el else ""
            if not size or len(size) > 24 or not re.search(r"\d", size) or size in seen_sizes:
                continue
            seen_sizes.add(size)
            sizes.append(
                {
                    "name": size,
                    "size": size,
                    "in_stock": not self._size_is_disabled(input_el, label_el),
                    "sku": input_el.get("value"),
                    "stock_source": "kaptanspor_size_selector",
                }
            )
        if sizes:
            result["sizes"] = sizes

        stock_rows = " ".join(
            element.get_text(" ", strip=True)
            for element in soup.select(".tf-attr-pa-size, [class*='stock-status'], [class*='stockStatus']")
        )
        unavailable_text = soup.find(
            string=re.compile(r"ge(?:c|\u00e7)ici olarak temin edilememektedir", re.IGNORECASE)
        )
        if re.search(r"stok durumu\s*stokta yok", stock_rows, re.IGNORECASE) or unavailable_text:
            result["stock_status"] = "out_of_stock"
            if not sizes:
                result["in_stock"] = False
        elif re.search(r"stok durumu\s*mevcut", stock_rows, re.IGNORECASE):
            result["stock_status"] = "in_stock"

        current = url.split("?", 1)[0].rstrip("/")
        variants = []
        seen_variants = set()
        for link in soup.select(".color-grid a[href]"):
            variant = urljoin(url, link.get("href") or "").split("?", 1)[0].rstrip("/")
            if (
                variant == current
                or variant in seen_variants
                or not self.supports_url(variant)
                or not self.is_product_link(variant)
            ):
                continue
            seen_variants.add(variant)
            variants.append(variant)
        if variants:
            result["variant_urls"] = variants

        if result.get("title") and result.get("current_price"):
            result["confidence"] = max(result.get("confidence") or 0, 0.85)
        _finalize_stock_status(result)
        return result
