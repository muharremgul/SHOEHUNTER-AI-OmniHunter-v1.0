"""Dedicated adapters for Turkish footwear and multi-brand retailers."""

from bs4 import BeautifulSoup

from stores.structured_retail import StructuredRetailEngine


class BarcinEngine(StructuredRetailEngine):
    name = "Barçın"
    slug = "barcin"
    domains = ["barcin.com"]
    search_path = "https://www.barcin.com/search?q={q}"
    product_pattern = None
    priority = 3
    js_search = True
    browser_wait_selector = "article, [class*='product-card'], [class*='product-item']"
    price_selectors = (
        "[data-testid='product-price']",
        ".product-detail [class*='sale-price']",
        ".product-detail [class*='current-price']",
        "[class*='productPrice'] [class*='sale']",
        ".product-price",
    )
    old_price_selectors = (
        ".product-detail [class*='old-price']",
        ".product-detail [class*='list-price']",
        "[class*='productPrice'] del",
        ".product-price del",
    )
    size_selectors = (
        "[data-testid*='size'] button",
        "[class*='size-selector'] button",
        "[class*='size-list'] button",
        "[class*='size-option']",
        "select[name*='size'] option",
    )
    search_card_selectors = ("article", "[class*='product-card']", "[class*='product-item']")

    def is_product_link(self, url):
        path = url.split("?", 1)[0].rstrip("/").lower()
        segment = path.rsplit("/", 1)[-1]
        blocked_prefixes = ("blog-", "kampanya-", "kategori-", "magaza-", "marka-")
        footwear_tokens = ("ayakkabi", "terlik", "sandalet", "bot", "cizme", "krampon")
        return (
            segment.count("-") >= 5
            and not segment.startswith(blocked_prefixes)
            and any(token in segment for token in footwear_tokens)
        )


class KoraySporEngine(StructuredRetailEngine):
    name = "Korayspor"
    slug = "korayspor"
    domains = ["korayspor.com"]
    search_path = "https://www.korayspor.com/arama?q={q}"
    product_pattern = r"(?i)/[^/?#]*(?:[a-z]{1,4}\d{3,}(?:-\d{2,4})?)/?$"
    priority = 4
    price_selectors = (
        "[itemprop='price']",
        ".product-detail-price .discounted-price",
        ".product-detail-price .current-price",
        ".product-price-new",
        ".product-price",
    )
    old_price_selectors = (
        ".product-detail-price .old-price",
        ".product-price-old",
        ".product-price del",
        "del",
    )
    size_selectors = (
        "[class*='size-selection'] button",
        "[class*='size-selection'] label",
        "[class*='variant-size'] button",
        "select[name*='size'] option",
        "select[name*='beden'] option",
    )
    search_card_selectors = (".product-item", ".product-card", "[class*='product-list'] article")


class FloEngine(StructuredRetailEngine):
    name = "FLO"
    slug = "flo"
    domains = ["flo.com.tr"]
    search_path = "https://www.flo.com.tr/search?q={q}"
    product_pattern = r"(?i)(?:/urun/|/product/|-[pu]-?\d+(?:$|[/?#])|_[a-z0-9]{4,}(?:$|[/?#]))"
    priority = 5
    js_search = True
    browser_wait_selector = "[data-testid*='product'], [class*='product-card']"
    supports_seller_data = True
    price_selectors = (
        "[data-testid='product-price']",
        "[data-testid*='sale-price']",
        "[class*='ProductPrice'] [class*='discount']",
        "[class*='product-price'] [class*='current']",
        "[itemprop='price']",
    )
    old_price_selectors = (
        "[data-testid*='old-price']",
        "[class*='ProductPrice'] [class*='old']",
        "[class*='product-price'] del",
    )
    size_selectors = (
        "[data-testid*='size'] input",
        "[data-testid*='size'] button",
        "[class*='size-list'] input",
        "[class*='size-list'] button",
        "[class*='quick'] [class*='size'] input",
    )
    seller_selectors = (
        "[data-testid*='seller']",
        "[class*='seller-name']",
        "[class*='merchant-name']",
    )
    shipping_selectors = (
        "[data-testid*='estimated-delivery']",
        "[class*='delivery-date']",
        "[class*='shipping-info']",
    )
    search_card_selectors = (
        "[data-testid='product-card']",
        "[data-testid*='product-list-item']",
        "[class*='product-card']",
    )


class SuperStepEngine(StructuredRetailEngine):
    name = "SuperStep"
    slug = "superstep"
    domains = ["superstep.com.tr"]
    search_path = "https://www.superstep.com.tr/arama?q={q}"
    product_pattern = r"(?i)(?:/urun/|/product/|/p/|-[a-z]{1,5}\d{3,}(?:$|[/?#]))"
    priority = 6
    js_search = True
    browser_wait_selector = "[class*='product-card'], [class*='product-item']"
    price_selectors = (
        "[data-testid='product-price']",
        ".product-detail-price .sale-price",
        ".product-detail-price .current-price",
        ".product-price",
    )
    old_price_selectors = (
        ".product-detail-price .old-price",
        ".product-detail-price del",
        ".product-price del",
    )
    size_selectors = (
        "[class*='size-list'] button",
        "[class*='size-list'] label",
        "[class*='variant-size'] button",
        "select[name*='size'] option",
    )
    search_card_selectors = ("[class*='product-card']", "[class*='product-item']", "article")


class SneaksUpEngine(StructuredRetailEngine):
    name = "Sneaks Up"
    slug = "sneaksup"
    domains = ["sneaksup.com"]
    search_path = "https://www.sneaksup.com/search?q={q}"
    product_pattern = r"(?i)(?:/urun/|/products?/|/p/|-[a-z]{1,5}\d{3,}(?:-[a-z0-9]+)*(?:$|[/?#]))"
    priority = 7
    js_search = True
    browser_wait_selector = "[class*='product-card'], [class*='product-item']"
    price_selectors = (
        "[data-testid='product-price']",
        "[class*='product-detail'] [class*='sale-price']",
        "[class*='product-detail'] [class*='current-price']",
        ".product-price",
    )
    old_price_selectors = (
        "[class*='product-detail'] [class*='old-price']",
        "[class*='product-detail'] del",
        ".product-price del",
    )
    size_selectors = (
        "[data-testid*='size'] button",
        "[class*='size-option']",
        "[class*='size-list'] button",
        "select[name*='size'] option",
    )
    search_card_selectors = ("[class*='product-card']", "[class*='product-item']", "article")


class BoynerEngine(StructuredRetailEngine):
    name = "Boyner"
    slug = "boyner"
    domains = ["boyner.com.tr"]
    search_path = "https://www.boyner.com.tr/arama?q={q}"
    product_pattern = r"(?i)(?:/urun/|/p/|-[pu]-?\d+(?:$|[/?#]))"
    priority = 9
    js_search = True
    browser_wait_selector = "[data-testid*='product'], [class*='product-card']"
    supports_seller_data = True
    price_selectors = (
        "[data-testid='product-price']",
        "[data-testid*='sale-price']",
        "[class*='product-price'] [class*='discount']",
        "[class*='product-price'] [class*='current']",
        "[itemprop='price']",
    )
    old_price_selectors = (
        "[data-testid*='original-price']",
        "[class*='priceOldPrice']",
        "[class*='product-price'] [class*='old']",
        "[class*='product-price'] del",
    )
    cart_price_selectors = (
        "[class*='priceDiscountText'] + [class*='priceMain']",
        "[class*='priceMain']",
        "[class*='sepette']",
    )
    size_selectors = (
        "[data-testid*='size'] button",
        "[data-testid*='size'] input",
        "[class*='size-option']",
        "select[name*='size'] option",
    )
    seller_selectors = ("[data-testid*='seller']", "[class*='seller-name']", "[class*='merchant-name']")
    shipping_selectors = ("[data-testid*='delivery']", "[class*='delivery-info']", "[class*='shipping']")
    search_card_selectors = ("[data-testid='product-card']", "[class*='product-card']", "[class*='product-item']")

    def parse(self, html, url):
        result = super().parse(html, url)
        # Boyner's current page renders the normal price, "Sepette %…"
        # label and exact cart result as siblings. JSON-LD may expose the lower
        # value, so restore the visibly labelled normal price as current_price.
        if result.get("cart_price"):
            soup = BeautifulSoup(html, "lxml")
            shelf_price, selector = self._first_scoped_price(soup, ("[class*='priceOldPrice']",))
            if shelf_price and shelf_price > result["cart_price"]:
                result["current_price"] = shelf_price
                if result.get("old_price") == shelf_price:
                    result["old_price"] = None
                result["price_source"] = f"store_selector:{selector}"
                result["confidence"] = max(result.get("confidence") or 0, 0.94)
        return result


class SpxEngine(StructuredRetailEngine):
    name = "SPX"
    slug = "spx"
    domains = ["spx.com.tr"]
    search_path = "https://www.spx.com.tr/arama?q={q}"
    product_pattern = r"(?i)(?:/urun/|/product/|-[a-z]{1,5}\d{3,}(?:-[a-z0-9]+)*(?:$|[/?#]))"
    priority = 11
    js_search = True
    browser_wait_selector = "[class*='product-card'], [class*='product-item']"
    price_selectors = (
        "[data-testid='product-price']",
        ".product-detail-price .sale-price",
        ".product-detail-price .current-price",
        ".product-price",
    )
    old_price_selectors = (
        ".product-detail-price .old-price",
        ".product-detail-price del",
        ".product-price del",
    )
    size_selectors = (
        "[class*='size-list'] button",
        "[class*='size-option']",
        "[class*='beden'] button",
        "select[name*='size'] option",
    )
    search_card_selectors = ("[class*='product-card']", "[class*='product-item']", "article")


class KutupayisiEngine(StructuredRetailEngine):
    name = "Kutupayısı"
    slug = "kutupayisi"
    domains = ["kutupayisi.com"]
    search_path = "https://www.kutupayisi.com/arama?q={q}"
    product_pattern = r"(?i)(?:/urun/|/product/|-[a-z]{1,5}\d{3,}(?:$|[/?#]))"
    priority = 12
    js_search = True
    browser_wait_selector = "[class*='product-card'], [class*='product-item']"
    price_selectors = (
        "[itemprop='price']",
        ".product-detail-price .sale-price",
        ".product-detail-price .current-price",
        ".product-price",
    )
    old_price_selectors = (
        ".product-detail-price .old-price",
        ".product-price-old",
        ".product-price del",
    )
    size_selectors = (
        "[class*='size-list'] button",
        "[class*='size-option']",
        "[class*='variant'] label",
        "select[name*='size'] option",
    )
    search_card_selectors = ("[class*='product-card']", "[class*='product-item']", "article")


class AsicsEngine(StructuredRetailEngine):
    name = "ASICS TR"
    slug = "asics"
    domains = ["asics.com.tr"]
    # The current Turkish storefront exposes product/catalog pages but no
    # verified stable search route. Discovery therefore uses the sitemap layer.
    search_path = None
    product_pattern = r"(?i)(?:/p/|/urun/|/[a-z0-9-]+-\d{3,})(?:$|[/?#])"
    priority = 24
    js_search = False
    use_browser = True
    discovery_method = "catalog+sitemap"
    catalog_seed_urls = (
        "https://www.asics.com.tr/erkek-kosu-ayakkabilari",
        "https://www.asics.com.tr/kadin-kosu-ayakkabilari",
    )
    browser_wait_selector = "[data-testid*='product'], [class*='product']"
    price_selectors = (
        "[data-testid='product-price']",
        "[class*='product-price'] [class*='sales']",
        "[class*='product-price'] [class*='current']",
        "[itemprop='price']",
    )
    old_price_selectors = (
        "[class*='product-price'] [class*='standard']",
        "[class*='product-price'] [class*='old']",
        "[class*='product-price'] del",
    )
    size_selectors = (
        "[data-testid*='size'] button",
        "[class*='size-selector'] button",
        "[class*='size-selector'] input",
        "[class*='size-option']",
        "select[name*='size'] option",
    )
    search_card_selectors = ("[data-testid='product-card']", "[class*='product-card']", "[class*='product-tile']")


class SkechersEngine(StructuredRetailEngine):
    name = "Skechers TR"
    slug = "skechers"
    domains = ["skechers.com.tr"]
    search_path = "https://www.skechers.com.tr/arama?q={q}"
    product_pattern = r"(?i)(?:/p-|/urun/|/product/)"
    priority = 25
    js_search = True
    use_browser = True
    browser_wait_selector = "[class*='product-card'], [class*='product-detail']"
    price_selectors = (
        "[data-testid='product-price']",
        "[class*='product-detail'] [class*='sale-price']",
        "[class*='product-detail'] [class*='current-price']",
        "[itemprop='price']",
    )
    old_price_selectors = (
        "[class*='product-detail'] [class*='old-price']",
        "[class*='product-detail'] del",
        ".product-price del",
    )
    size_selectors = (
        "[class*='size-selector'] button",
        "[class*='size-selector'] label",
        "[class*='size-option']",
        "select[name*='size'] option",
    )
    search_card_selectors = ("[class*='product-card']", "[class*='product-item']", "article")
