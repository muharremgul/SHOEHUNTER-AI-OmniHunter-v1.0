"""Dedicated Turkish adapters for requested running and outdoor brands."""

from engines import _finalize_stock_status, _first_offer, extract_json_ld_products, parse_price_text

from stores.structured_retail import StructuredRetailEngine


class BrooksEngine(StructuredRetailEngine):
    name = "Brooks Türkiye"
    slug = "brooks"
    domains = ["brooksrunning.com.tr"]
    search_path = "https://www.brooksrunning.com.tr/arama?q={q}"
    product_pattern = r"(?i)/p-[^/?#]+-[a-z0-9]+(?:$|[/?#])"
    priority = 26
    js_search = True
    browser_wait_selector = "[class*='product-card'], [class*='product-detail'], h1"
    price_selectors = (
        "[itemprop='price']",
        "[class*='product-detail'] [class*='sale-price']",
        "[class*='product-detail'] [class*='current-price']",
        "[class*='product-price']",
    )
    old_price_selectors = (
        "[class*='product-detail'] [class*='old-price']",
        "[class*='product-price'] del",
        "[class*='product-price'] s",
    )
    size_selectors = (
        "[class*='size-selector'] button",
        "[class*='size-selector'] label",
        "[class*='size-option']",
        "[class*='beden'] button",
        "select[name*='size'] option",
        "select[name*='beden'] option",
    )
    variant_selectors = (
        "[class*='color-option'] a[href]",
        "[class*='variant-color'] a[href]",
        "[class*='renk'] a[href]",
    )
    search_card_selectors = ("[class*='product-card']", "[class*='product-item']", "article")

    def parse(self, html, url):
        result = super().parse(html, url)
        # Brooks currently publishes a non-standard capitalised `Price` key
        # inside an otherwise useful Product JSON-LD offer.
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "lxml")
        for product in extract_json_ld_products(soup):
            offer = _first_offer(product.get("offers"))
            if not isinstance(offer, dict):
                continue
            raw_price = offer.get("price") if offer.get("price") is not None else offer.get("Price")
            price = parse_price_text(raw_price)
            if price and 50 < price < 200000:
                existing_price = result.get("current_price")
                if not existing_price or price < existing_price:
                    if existing_price and existing_price > price:
                        result["old_price"] = max(result.get("old_price") or 0, existing_price)
                    result["current_price"] = price
                    result["price_source"] = "brooks_json_ld_offer"
                    result["confidence"] = max(result["confidence"], 0.8)
                elif price > existing_price:
                    result["old_price"] = max(result.get("old_price") or 0, price)
                else:
                    result["price_source"] = "brooks_json_ld_offer"
                    result["confidence"] = max(result["confidence"], 0.8)
                result["debug"]["price_candidates"].append(
                    {"source": "brooks_json_ld_offer", "value": price}
                )
                availability = str(offer.get("availability") or "").lower()
                if "outofstock" in availability:
                    result["stock_status"] = "out_of_stock"
                elif "instock" in availability:
                    result["stock_status"] = "in_stock"
                break
        _finalize_stock_status(result)
        return result


class ColumbiaEngine(StructuredRetailEngine):
    name = "Columbia Türkiye"
    slug = "columbia"
    domains = ["columbia.com.tr"]
    # The public site exposes no stable query route.  Product discovery uses
    # the existing catalogue/sitemap fallback instead of inventing an API.
    search_path = None
    product_pattern = r"(?i)-p-\d+(?:$|[/?#])"
    priority = 27
    js_search = False
    discovery_method = "catalog+sitemap"
    catalog_seed_urls = (
        "https://www.columbia.com.tr/ayakkabi?pageIndex=1",
        "https://www.columbia.com.tr/ayakkabi?pageIndex=2",
    )
    browser_wait_selector = "[class*='product-card'], [class*='product-detail'], h1"
    price_selectors = (
        "[data-testid='product-price']",
        "[class*='product-detail'] [class*='sale-price']",
        "[class*='product-detail'] [class*='current-price']",
        "[class*='product-price']",
        "[itemprop='price']",
    )
    old_price_selectors = (
        "[class*='product-detail'] [class*='old-price']",
        "[class*='product-price'] del",
        "[class*='product-price'] s",
    )
    size_selectors = (
        "[data-testid*='size'] button",
        "[class*='size-selector'] button",
        "[class*='size-selector'] label",
        "[class*='size-option']",
        "select[name*='size'] option",
    )
    variant_selectors = (
        "[data-testid*='color'] a[href]",
        "[class*='color-option'] a[href]",
        "[class*='swatch'] a[href]",
    )
    search_card_selectors = ("[class*='product-card']", "[class*='product-item']", "article")


class SalomonEngine(StructuredRetailEngine):
    name = "Salomon Türkiye"
    slug = "salomon"
    domains = ["salomon.com.tr"]
    search_path = "https://www.salomon.com.tr/Arama?q={q}"
    product_pattern = r"(?i)/(?:[^/?#]+-)+(?:[a-z]\d{8}|\d{4,})(?:$|[/?#])"
    priority = 28
    js_search = True
    browser_wait_selector = ".ItemOrj, [class*='product-card'], [class*='product-detail'], h1"
    price_selectors = (
        "[itemprop='price']",
        ".ProductPrice .discountPrice",
        ".ProductPrice .currentPrice",
        "[class*='product-price'] [class*='sale']",
        "[class*='product-price']",
    )
    old_price_selectors = (
        ".ProductPrice .oldPrice",
        "[class*='product-price'] [class*='old']",
        "[class*='product-price'] del",
    )
    size_selectors = (
        "[class*='size-selection'] button",
        "[class*='size-selection'] label",
        "[class*='size-option']",
        "[class*='beden'] button",
        "select[name*='size'] option",
        "select[name*='beden'] option",
    )
    variant_selectors = (
        "[class*='color-option'] a[href]",
        "[class*='variant-color'] a[href]",
        "[class*='renk'] a[href]",
    )
    search_card_selectors = (".ItemOrj", "[class*='product-card']", "[class*='product-item']", "article")


class TheNorthFaceEngine(StructuredRetailEngine):
    name = "The North Face Türkiye"
    slug = "thenorthface"
    domains = ["thenorthface.com.tr"]
    search_path = "https://www.thenorthface.com.tr/search?q={q}"
    product_pattern = r"(?i)/[^/?#]+_\d+(?:$|[/?#])"
    priority = 29
    js_search = True
    browser_wait_selector = "[class*='product-card'], [class*='product-detail'], h1"
    price_selectors = (
        "[data-testid='product-price']",
        "[class*='product-detail'] [class*='sale-price']",
        "[class*='product-detail'] [class*='current-price']",
        "[class*='product-price']",
        "[itemprop='price']",
    )
    old_price_selectors = (
        "[class*='product-detail'] [class*='old-price']",
        "[class*='product-price'] del",
        "[class*='product-price'] s",
    )
    size_selectors = (
        "[data-testid*='size'] button",
        "[class*='size-selector'] button",
        "[class*='size-selector'] label",
        "[class*='size-option']",
        "select[name*='size'] option",
    )
    variant_selectors = (
        "[data-testid*='color'] a[href]",
        "[class*='color-option'] a[href]",
        "[class*='swatch'] a[href]",
    )
    search_card_selectors = ("[class*='product-card']", "[class*='product-item']", "article")
