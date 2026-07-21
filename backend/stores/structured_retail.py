"""Reusable, conservative building blocks for dedicated Turkish store adapters.

Every store still owns its URL contract and selector profile in a dedicated
class.  This module only centralises the defensive parsing rules shared by
those adapters: structured data first, scoped DOM fallbacks, size/stock
normalisation, campaign/seller details and product-card search parsing.

The adapter deliberately consumes only information already present in public
pages.  It does not solve challenges, impersonate users or rotate identities.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from engines import (
    StoreEngine,
    _absolute_url,
    _clean_image_url,
    _extract_variant_urls,
    _finalize_stock_status,
    _score_result,
    _search_image_from_card,
    _search_price_from_card,
    _search_title_from_card,
    parse_price_text,
)

_OUT_OF_STOCK_TOKENS = (
    "out-of-stock",
    "out_of_stock",
    "unavailable",
    "sold-out",
    "soldout",
    "disabled",
    "passive",
    "tukendi",
    "tükendi",
    "stokta-yok",
    "stokta yok",
    "temin edilemiyor",
)
_IN_STOCK_TOKENS = (
    "in-stock",
    "in_stock",
    "available",
    "selectable",
    "stokta",
    "mevcut",
)
_PLACEHOLDER_SIZE_TOKENS = (
    "beden seç",
    "beden sec",
    "numara seç",
    "numara sec",
    "size seç",
    "size sec",
    "seçiniz",
    "seciniz",
    "choose",
)


def _normalise_space(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _valid_price(value):
    price = parse_price_text(value)
    return price if price and 50 < price < 200000 else None


def _truthy_attribute(value):
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if text in {"true", "1", "yes", "evet", "available", "instock", "in_stock"}:
        return True
    if text in {"false", "0", "no", "hayir", "hayır", "unavailable", "outofstock", "out_of_stock"}:
        return False
    return None


def _looks_like_size(value) -> bool:
    """Reject navigation/campaign labels while retaining shoe size formats."""

    text = _normalise_space(value)
    if not text or len(text) > 28:
        return False
    lowered = text.lower()
    if any(token in lowered for token in _PLACEHOLDER_SIZE_TOKENS):
        return False
    if lowered in {"xs", "s", "m", "l", "xl", "xxl", "xxxl", "tek beden"}:
        return True
    if re.fullmatch(r"(?:eu|tr|uk|us)?\s*\d{1,2}(?:[.,]\d{1,2})?(?:\s*(?:1/3|2/3|½))?", lowered):
        number = re.search(r"\d{1,2}(?:[.,]\d{1,2})?", lowered)
        return bool(number and 1 <= float(number.group().replace(",", ".")) <= 60)
    if re.fullmatch(r"\d{1,2}\s*(?:-|/)\s*\d{1,2}", lowered):
        return True
    return False


def _json_nodes(value, depth=0, budget=None):
    """Yield bounded JSON nodes; public page state can otherwise be enormous."""

    if budget is None:
        budget = [800]
    if depth > 9 or budget[0] <= 0:
        return
    budget[0] -= 1
    if isinstance(value, dict):
        yield value
        for child in value.values():
            if isinstance(child, (dict, list)):
                yield from _json_nodes(child, depth + 1, budget)
    elif isinstance(value, list):
        for child in value[:100]:
            if isinstance(child, (dict, list)):
                yield from _json_nodes(child, depth + 1, budget)


class StructuredRetailEngine(StoreEngine):
    """A strong shared parser used by separately configured store engines."""

    parser_version = "3-structured-retail"
    supports_sizes = True
    supports_variants = True
    supports_cart_price = True
    supports_seller_data = False

    price_selectors: tuple[str, ...] = (
        "[data-testid='product-price']",
        "[data-test-id='product-price']",
        "[itemprop='price']",
        ".product-price .current-price",
        ".product-price .sale-price",
        ".price__current",
    )
    old_price_selectors: tuple[str, ...] = (
        "[data-testid='original-price']",
        "[data-test-id='original-price']",
        ".product-price .old-price",
        ".product-price .list-price",
        ".price__old",
        ".compare-at-price",
    )
    cart_price_selectors: tuple[str, ...] = ()
    size_selectors: tuple[str, ...] = (
        "[data-testid*='size'] button",
        "[data-test-id*='size'] button",
        "[class*='size-selector'] button",
        "[class*='size-selector'] label",
        "[class*='size-option']",
        "[class*='beden'] button",
        "[class*='beden'] label",
        "select[name*='size'] option",
        "select[name*='beden'] option",
    )
    variant_selectors: tuple[str, ...] = (
        "[data-testid*='color'] a[href]",
        "[data-test-id*='color'] a[href]",
        "[class*='color-option'] a[href]",
        "[class*='colour-option'] a[href]",
        "[class*='renk'] a[href]",
        "[class*='swatch'] a[href]",
    )
    seller_selectors: tuple[str, ...] = ()
    seller_rating_selectors: tuple[str, ...] = ()
    shipping_selectors: tuple[str, ...] = ()
    stock_out_selectors: tuple[str, ...] = (
        "[data-testid*='out-of-stock']",
        "[data-test-id*='out-of-stock']",
        ".out-of-stock",
        ".sold-out",
        "[class*='stock-out']",
    )
    stock_in_selectors: tuple[str, ...] = (
        "button[data-testid*='add-to-cart']:not([disabled])",
        "button[data-test-id*='add-to-cart']:not([disabled])",
        "button[class*='add-to-cart']:not([disabled])",
        "button[class*='sepete']:not([disabled])",
    )
    search_card_selectors: tuple[str, ...] = (
        "[data-testid='product-card']",
        "[data-test-id='product-card']",
        ".product-card",
        ".product-item",
        "article",
    )
    search_link_selectors: tuple[str, ...] = ("a[href]",)
    official_seller_tokens: tuple[str, ...] = ()
    embedded_script_ids: tuple[str, ...] = ("__NEXT_DATA__", "__NUXT_DATA__", "__APOLLO_STATE__")
    catalog_seed_urls: tuple[str, ...] = ()

    @staticmethod
    def _node_price(node):
        if not node:
            return None
        raw = node.get("data-price") or node.get("data-price-value") or node.get("content")
        return _valid_price(raw or node.get_text(" ", strip=True))

    def _first_scoped_price(self, soup, selectors):
        for selector in selectors:
            values = []
            for node in soup.select(selector)[:12]:
                price = self._node_price(node)
                if price:
                    values.append(price)
            if values:
                return min(values), selector
        return None, None

    def _highest_scoped_price(self, soup, selectors):
        for selector in selectors:
            values = []
            for node in soup.select(selector)[:12]:
                price = self._node_price(node)
                if price:
                    values.append(price)
            if values:
                return max(values), selector
        return None, None

    @staticmethod
    def _label_for_size_node(node, soup):
        candidates = [
            node.get("data-size"),
            node.get("data-size-name"),
            node.get("data-value-label"),
            node.get("aria-label"),
            node.get("title"),
        ]
        if node.name == "input":
            node_id = node.get("id")
            label = soup.find("label", attrs={"for": node_id}) if node_id else None
            if label:
                candidates.append(label.get_text(" ", strip=True))
            parent_label = node.find_parent("label")
            if parent_label:
                candidates.append(parent_label.get_text(" ", strip=True))
        candidates.extend([node.get_text(" ", strip=True), node.get("value")])
        for candidate in candidates:
            label = _normalise_space(candidate)
            label = re.sub(r"^(?:beden|numara|size)\s*[:\-]?\s*", "", label, flags=re.I)
            if _looks_like_size(label):
                return label
        return None

    @staticmethod
    def _size_stock(node, soup):
        related = [node]
        node_id = node.get("id")
        if node_id:
            linked_label = soup.find("label", attrs={"for": node_id})
            if linked_label:
                related.append(linked_label)
        linked_id = node.get("for") if node.name == "label" else None
        if linked_id:
            linked_control = soup.find(id=linked_id)
            if linked_control:
                related.append(linked_control)
        if node.name == "label":
            related.extend(node.find_all(["input", "button", "option"], limit=4))
        elif node.name in {"input", "option"}:
            parent_label = node.find_parent("label")
            if parent_label:
                related.append(parent_label)

        attr_values = " ".join(
            str(item.get(key) or "")
            for item in related
            for key in ("class", "data-stock-status", "data-availability", "data-state", "aria-label", "title")
        ).lower()
        if any(
            item.has_attr("disabled") or str(item.get("aria-disabled") or "").lower() == "true"
            for item in related
        ):
            return False
        for item in related:
            explicit_out = _truthy_attribute(item.get("data-out-of-stock"))
            if explicit_out is True:
                return False
            for key in ("data-in-stock", "data-available", "data-selectable"):
                explicit = _truthy_attribute(item.get(key))
                if explicit is not None:
                    return explicit
        if any(token in attr_values for token in _OUT_OF_STOCK_TOKENS):
            return False
        if any(token in attr_values for token in _IN_STOCK_TOKENS):
            return True
        return None

    def _extract_sizes(self, soup):
        by_label = {}
        sources = {}
        for selector in self.size_selectors:
            for node in soup.select(selector)[:120]:
                label = self._label_for_size_node(node, soup)
                if not label:
                    continue
                stock = self._size_stock(node, soup)
                current = by_label.get(label)
                if current is None or stock is True:
                    by_label[label] = stock
                    sources[label] = selector
        return [
            {
                "name": label,
                "size": label,
                "in_stock": in_stock,
                "sku": None,
                "stock_source": f"selector:{sources[label]}",
            }
            for label, in_stock in by_label.items()
        ]

    def _iter_public_state(self, soup):
        seen_raw = set()
        scripts = []
        for script_id in self.embedded_script_ids:
            script = soup.find("script", id=script_id)
            if script:
                scripts.append(script)
        scripts.extend(soup.find_all("script", type="application/json")[:12])
        for script in scripts:
            raw = (script.string or script.get_text() or "").strip()
            if not raw or len(raw) > 2_000_000 or raw in seen_raw:
                continue
            seen_raw.add(raw)
            try:
                payload = json.loads(raw)
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            yield from _json_nodes(payload)

    @staticmethod
    def _product_state_score(node):
        keys = {str(key).lower().replace("_", "") for key in node}
        score = 0
        if keys.intersection({"name", "productname", "title"}):
            score += 1
        if keys.intersection({"price", "saleprice", "sellingprice", "discountedprice", "currentprice"}):
            score += 2
        if keys.intersection({"sku", "productid", "productcode", "mpn", "variants", "variantoptions"}):
            score += 1
        return score

    @staticmethod
    def _state_value(node, *keys):
        normalised = {str(key).lower().replace("_", ""): value for key, value in node.items()}
        for key in keys:
            value = normalised.get(str(key).lower().replace("_", ""))
            if value not in (None, "", [], {}):
                return value
        return None

    def _state_identity_score(self, node, result, current_url):
        score = 0
        current = urlparse(current_url)
        current_path = current.path.rstrip("/").lower()
        current_compact = re.sub(r"[^a-z0-9]", "", current_path)

        candidate_url = self._state_value(node, "productUrl", "canonicalUrl", "seoUrl", "url", "href")
        if isinstance(candidate_url, str) and candidate_url.strip():
            candidate_parsed = urlparse(urljoin(current_url, candidate_url))
            if candidate_parsed.netloc.lower() != current.netloc.lower():
                return -100
            candidate = candidate_parsed.path.rstrip("/").lower()
            if candidate == current_path:
                score += 5
            elif candidate:
                # A product-like state object explicitly pointing at a different
                # same-site URL is usually a recommendation card.
                return -100

        candidate_id = self._state_value(node, "productId", "productCode", "sku", "mpn", "id")
        if candidate_id is not None:
            compact_id = re.sub(r"[^a-z0-9]", "", str(candidate_id).lower())
            if len(compact_id) >= 4 and compact_id in current_compact:
                score += 3

        candidate_name = self._state_value(node, "productName", "name", "title")
        if candidate_name and result.get("title"):
            similarity = _score_result(str(candidate_name), result["title"])
            if similarity >= 95:
                score += 3
            elif similarity >= 82:
                score += 2
        return score

    def _apply_public_state(self, soup, result, url):
        candidates = {}
        saw_product_state = False
        for node in self._iter_public_state(soup):
            state_score = self._product_state_score(node)
            if state_score < 3:
                continue
            saw_product_state = True
            identity_score = self._state_identity_score(node, result, url)
            if identity_score < 0:
                continue
            signature = (
                str(self._state_value(node, "productName", "name", "title") or "").strip().lower(),
                str(self._state_value(node, "productId", "productCode", "sku", "mpn", "id") or "")
                .strip()
                .lower(),
                str(
                    self._state_value(
                        node, "discountedPrice", "salePrice", "sellingPrice", "currentPrice", "price"
                    )
                    or ""
                ).strip(),
            )
            existing = candidates.get(signature)
            rank = (identity_score, state_score)
            if existing is None or rank > existing[0]:
                candidates[signature] = (rank, node)

        if not candidates:
            if saw_product_state and result.get("price_source") == "embedded_json":
                result["current_price"] = None
                result["old_price"] = None
                result["price_source"] = None
                result["confidence"] = 0.5
                result["debug"]["notes"].append("embedded_product_state_identity_mismatch")
            return

        ranked = sorted(candidates.values(), key=lambda item: item[0], reverse=True)
        (identity_score, _), best = ranked[0]
        tied_top_rank = len(ranked) > 1 and ranked[1][0] == ranked[0][0]
        if identity_score < 2 or tied_top_rank:
            if result.get("price_source") == "embedded_json":
                result["current_price"] = None
                result["old_price"] = None
                result["price_source"] = None
                result["confidence"] = 0.5
            note = "embedded_product_state_ambiguous" if tied_top_rank else "embedded_product_state_identity_unverified"
            result["debug"]["notes"].append(note)
            return

        def first(*keys):
            return self._state_value(best, *keys)

        state_price = _valid_price(first("discountedPrice", "salePrice", "sellingPrice", "currentPrice", "price"))
        if state_price:
            current_source = str(result.get("price_source") or "")
            weak_source = not result.get("current_price") or current_source == "embedded_json" or current_source.startswith(
                "selector:"
            )
            if weak_source:
                result["current_price"] = state_price
                result["price_source"] = "embedded_product_state"
                result["confidence"] = max(result["confidence"], 0.82)
                result["debug"]["price_candidates"].append(
                    {"source": "embedded_product_state", "value": state_price}
                )
            else:
                result["debug"]["price_candidates"].append(
                    {"source": "embedded_product_state_not_promoted", "value": state_price}
                )
        old_price = _valid_price(first("originalPrice", "oldPrice", "listPrice", "retailPrice", "marketPrice"))
        if old_price and result.get("current_price") and old_price > result["current_price"]:
            result["old_price"] = old_price
        if not result.get("title"):
            result["title"] = _normalise_space(first("productName", "name", "title"))[:200] or None
        result["model_code"] = result.get("model_code") or first("sku", "productCode", "mpn", "productId")
        brand = first("brandName", "brand")
        if isinstance(brand, dict):
            brand = brand.get("name")
        result["brand"] = result.get("brand") or (_normalise_space(brand) or None)
        image = first("imageUrl", "image", "images")
        if isinstance(image, list):
            image = image[0] if image else None
        if isinstance(image, dict):
            image = image.get("url") or image.get("src")
        result["image"] = result.get("image") or _clean_image_url(url, image)

        state_stock = first("inStock", "isInStock", "available", "isAvailable")
        explicit_stock = _truthy_attribute(state_stock)
        if explicit_stock is not None and not result.get("sizes"):
            result["stock_status"] = "in_stock" if explicit_stock else "out_of_stock"

        variants = first("variants", "variantOptions", "skus", "sizes")
        if isinstance(variants, list) and not result.get("sizes"):
            sizes = []
            seen = set()
            for variant in variants[:120]:
                if not isinstance(variant, dict):
                    continue
                label = None
                for key in ("size", "sizeName", "attributeValue", "value", "name", "label"):
                    if _looks_like_size(variant.get(key)):
                        label = _normalise_space(variant.get(key))
                        break
                if not label or label in seen:
                    continue
                in_stock = None
                for key in ("inStock", "isInStock", "available", "isAvailable", "selectable"):
                    if key in variant:
                        in_stock = _truthy_attribute(variant.get(key))
                        break
                if in_stock is None and "stock" in variant:
                    try:
                        in_stock = float(variant["stock"]) > 0
                    except (TypeError, ValueError):
                        pass
                sizes.append(
                    {
                        "name": label,
                        "size": label,
                        "in_stock": in_stock,
                        "sku": variant.get("sku") or variant.get("id"),
                        "stock_source": "embedded_product_state",
                    }
                )
                seen.add(label)
            if sizes:
                result["sizes"] = sizes
                result["debug"]["variant_source"] = "embedded_product_state"

    def _extract_text(self, soup, selectors, limit=240):
        for selector in selectors:
            node = soup.select_one(selector)
            if node:
                text = _normalise_space(node.get("content") or node.get_text(" ", strip=True))
                if text:
                    return text[:limit]
        return None

    def _extract_variants(self, soup, url):
        variants = list(_extract_variant_urls(soup, url))
        seen = {item.rstrip("/") for item in variants}
        current = url.split("?")[0].rstrip("/")
        current_domain = urlparse(current).netloc.lower().replace("www.", "")
        for selector in self.variant_selectors:
            for anchor in soup.select(selector)[:60]:
                href = anchor.get("href")
                if not href:
                    continue
                full = urljoin(url, href).split("?")[0].rstrip("/")
                domain = urlparse(full).netloc.lower().replace("www.", "")
                if domain != current_domain or full == current or full in seen:
                    continue
                if self.is_product_link(full):
                    variants.append(full)
                    seen.add(full)
        return variants

    def parse(self, html, url):
        result = super().parse(html, url)
        soup = BeautifulSoup(html, "lxml")

        self._apply_public_state(soup, result, url)

        current_price, current_selector = self._first_scoped_price(soup, self.price_selectors)
        if current_price:
            current_source = str(result.get("price_source") or "")
            weak_source = not result.get("current_price") or current_source == "embedded_json" or current_source.startswith(
                "selector:"
            )
            candidate_source = f"store_selector:{current_selector}"
            if weak_source:
                result["current_price"] = current_price
                result["price_source"] = candidate_source
                result["confidence"] = max(result["confidence"], 0.86)
            else:
                candidate_source += "_not_promoted"
            result["debug"]["price_candidates"].append({"source": candidate_source, "value": current_price})
        old_price, old_selector = self._highest_scoped_price(soup, self.old_price_selectors)
        if old_price and result.get("current_price") and old_price > result["current_price"]:
            result["old_price"] = old_price
            result["debug"]["price_candidates"].append(
                {"source": f"old_price_selector:{old_selector}", "value": old_price}
            )
        # Exact cart prices stay separate from the normal shelf price.  The
        # shared detector also records percentage/quantity/member/code offers
        # as conditional campaign metadata without creating a false price.
        self._apply_cart_offers(soup, result, self.cart_price_selectors)

        sizes = self._extract_sizes(soup)
        if sizes:
            result["sizes"] = sizes
            result["debug"]["variant_source"] = "store_size_selectors"

        out_text = self._extract_text(soup, self.stock_out_selectors)
        in_text = self._extract_text(soup, self.stock_in_selectors)
        if out_text and not any(item.get("in_stock") is True for item in result.get("sizes") or []):
            result["stock_status"] = "out_of_stock"
            result["debug"]["notes"].append(f"stok_disinda:{out_text[:80]}")
        elif in_text and not result.get("sizes"):
            result["stock_status"] = "in_stock"

        seller = self._extract_text(soup, self.seller_selectors, limit=160)
        if seller:
            result["seller"] = seller
        rating = self._extract_text(soup, self.seller_rating_selectors, limit=80)
        if rating:
            match = re.search(r"\d+(?:[.,]\d+)?", rating)
            if match:
                result["seller_rating"] = float(match.group().replace(",", "."))
        shipping = self._extract_text(soup, self.shipping_selectors)
        if shipping:
            result["shipping"] = shipping
        if result.get("seller") and self.official_seller_tokens:
            seller_lower = result["seller"].lower()
            result["official_seller"] = any(token.lower() in seller_lower for token in self.official_seller_tokens)

        result["variant_urls"] = self._extract_variants(soup, url)
        _finalize_stock_status(result)
        return result

    def _card_nodes(self, soup) -> Iterable:
        seen = set()
        for selector in self.search_card_selectors:
            for card in soup.select(selector)[:120]:
                identity = id(card)
                if identity not in seen:
                    seen.add(identity)
                    yield card

    def parse_search(self, html, query, base_url):
        results = list(super().parse_search(html, query, base_url))
        seen = {item["url"].split("?")[0].rstrip("/") for item in results}
        soup = BeautifulSoup(html, "lxml")
        for card in self._card_nodes(soup):
            anchor = None
            for selector in self.search_link_selectors:
                candidate = card.select_one(selector)
                if candidate and candidate.get("href"):
                    anchor = candidate
                    break
            if not anchor:
                continue
            full = _absolute_url(base_url, anchor.get("href"))
            if not full or not self.supports_url(full) or not self.is_product_link(full):
                continue
            parsed = urlparse(full)
            clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
            if clean in seen:
                continue
            title = _search_title_from_card(card, anchor)
            score = _score_result(title, query)
            if score < 45:
                continue
            results.append(
                {
                    "title": title[:200],
                    "url": clean,
                    "score": score,
                    "image": _search_image_from_card(card, anchor, base_url),
                    "price": _search_price_from_card(card),
                    "store": self.name,
                }
            )
            seen.add(clean)
        results.sort(key=lambda item: (-item["score"], item.get("price") or 10**12))
        return results[:12]


class MarketplaceEngine(StructuredRetailEngine):
    """Shared public-page fields used by dedicated marketplace adapters."""

    parser_version = "3-marketplace"
    supports_seller_data = True
    supports_sizes = True
    supports_variants = True
    seller_selectors = (
        "[data-testid*='seller-name']",
        "[data-test-id*='seller-name']",
        "[class*='seller-name']",
        "[class*='merchant-name']",
        "[class*='merchantName']",
        "[class*='satici'] [class*='name']",
    )
    seller_rating_selectors = (
        "[data-testid*='seller-rating']",
        "[data-test-id*='seller-rating']",
        "[class*='seller-rating']",
        "[class*='merchant-rating']",
    )
    shipping_selectors = (
        "[data-testid*='delivery']",
        "[data-test-id*='delivery']",
        "[class*='delivery']",
        "[class*='shipping']",
        "[class*='kargo']",
    )
