"""Dedicated public-page adapters for Turkish mainstream marketplaces."""

import re
from collections import Counter
from urllib.parse import unquote, urlparse

from engines import _score_result
from product_identity import canonicalize_product_url

from stores.structured_retail import MarketplaceEngine


class HepsiburadaEngine(MarketplaceEngine):
    name = "Hepsiburada"
    slug = "hepsiburada"
    domains = ["hepsiburada.com"]
    search_path = "https://www.hepsiburada.com/ara?q={q}"
    product_pattern = r"(?i)-p[m]?-[a-z0-9]+(?:$|[/?#])"
    priority = 14
    js_search = True
    use_browser = True
    browser_wait_selector = "[data-test-id='product-card-name'], [data-test-id='price-current-price'], h1"
    official_seller_tokens = ("hepsiburada",)
    price_selectors = (
        "[data-test-id='price-current-price']",
        "[data-testid='price-current-price']",
        "[data-test-id*='current-price']",
        "[class*='currentPrice']",
        "[itemprop='price']",
    )
    old_price_selectors = (
        "[data-test-id='price-old-price']",
        "[data-testid='price-old-price']",
        "[data-test-id*='original-price']",
        "[class*='originalPrice']",
        "[class*='oldPrice']",
    )
    size_selectors = (
        "[data-test-id*='variant'] button",
        "[data-test-id*='size'] button",
        "[data-testid*='variant'] button",
        "[class*='variant-list'] button",
        "[class*='size-list'] button",
        "select[name*='size'] option",
    )
    variant_selectors = (
        "[data-test-id*='variant'] a[href]",
        "[data-test-id*='color'] a[href]",
        "[class*='variant-list'] a[href]",
        "[class*='color'] a[href]",
    )
    seller_selectors = (
        "[data-test-id='merchant-name']",
        "[data-test-id*='seller-name']",
        "[data-testid*='merchant-name']",
        "[class*='seller-name']",
        "[class*='merchantName']",
    )
    seller_rating_selectors = (
        "[data-test-id*='merchant-rating']",
        "[data-test-id*='seller-rating']",
        "[class*='merchantRating']",
        "[class*='seller-rating']",
    )
    shipping_selectors = (
        "[data-test-id*='delivery']",
        "[data-test-id*='shipping']",
        "[class*='deliveryTime']",
        "[class*='shipping-info']",
        "[class*='kargo']",
    )
    stock_out_selectors = (
        "[data-test-id*='out-of-stock']",
        "[data-test-id*='notify-me']",
        "button[disabled][data-test-id*='add-to-cart']",
        "[class*='outOfStock']",
    )
    stock_in_selectors = (
        "button[data-test-id*='add-to-cart']:not([disabled])",
        "button[data-testid*='add-to-cart']:not([disabled])",
    )
    search_card_selectors = (
        "[data-test-id='product-card-name']",
        "li[class*='productListContent']",
        "[data-testid='product-card']",
        "[class*='product-card']",
    )
    search_link_selectors = (
        "a[data-test-id='product-card-name'][href]",
        "a[href*='-p-']",
        "a[href*='-pm-']",
        "a[href]",
    )


class N11Engine(MarketplaceEngine):
    name = "n11"
    slug = "n11"
    domains = ["n11.com"]
    search_path = "https://www.n11.com/arama?q={q}"
    product_pattern = r"(?i)/urun/"
    priority = 15
    # n11's public HTML search currently contains product cards.  Keeping it
    # out of the shared browser queue prevents valid results from being lost
    # behind slower JavaScript-only stores.  An empty HTML shell still gets
    # one normal browser-rendering fallback from StoreEngine.search().
    js_search = False
    use_browser = True
    search_browser_fallback = True
    browser_wait_selector = ".productName, .newPrice, [data-testid*='product']"
    official_seller_tokens = ("n11",)
    price_selectors = (
        ".newPrice ins",
        ".priceDetail ins",
        "[data-testid='product-price']",
        "[data-testid*='current-price']",
        "[class*='currentPrice']",
        "[itemprop='price']",
    )
    old_price_selectors = (
        ".oldPrice del",
        ".priceDetail del",
        "[data-testid*='old-price']",
        "[class*='oldPrice']",
    )
    size_selectors = (
        ".skuVariantList button",
        ".skuVariantList a",
        ".skuVariantList label",
        "[data-testid*='variant'] button",
        "[data-testid*='size'] button",
        "[class*='size-option']",
    )
    variant_selectors = (
        ".skuVariantList a[href]",
        "[data-testid*='color'] a[href]",
        "[class*='color'] a[href]",
        "[class*='variant'] a[href]",
    )
    seller_selectors = (
        ".unf-p-seller-name",
        ".sellerName",
        "[data-testid*='seller-name']",
        "[class*='seller-name']",
        "[class*='merchant-name']",
    )
    seller_rating_selectors = (
        ".unf-p-seller-rating",
        ".sellerPoint",
        "[data-testid*='seller-rating']",
        "[class*='seller-rating']",
    )
    shipping_selectors = (
        ".unf-p-shipping",
        "[data-testid*='delivery']",
        "[data-testid*='shipping']",
        "[class*='delivery']",
        "[class*='kargo']",
    )
    stock_out_selectors = (
        ".soldOut",
        ".outOfStock",
        "[data-testid*='out-of-stock']",
        "button[disabled][class*='addBasket']",
    )
    stock_in_selectors = (
        "button.addBasketUnify:not([disabled])",
        "button[class*='addBasket']:not([disabled])",
        "button[data-testid*='add-to-cart']:not([disabled])",
    )
    search_card_selectors = (
        "li.column",
        ".productItem",
        "[data-testid='product-card']",
        "[class*='product-card']",
    )
    search_link_selectors = ("a[href*='/urun/']", "a[href]")

    @staticmethod
    def _title_from_product_url(url):
        path = unquote(urlparse(url).path)
        match = re.search(r"/urun/([^/?#]+)", path, re.I)
        if not match:
            return ""
        slug = re.sub(r"-\d{5,}$", "", match.group(1))
        return re.sub(r"[-_]+", " ", slug).strip()

    def parse_search(self, html, query, base_url):
        results = super().parse_search(html, query, base_url)
        title_counts = Counter(str(item.get("title") or "").strip().casefold() for item in results)
        cleaned = []
        seen = set()
        for item in results:
            url = canonicalize_product_url(item.get("url"))
            if not url or url in seen:
                continue
            title = str(item.get("title") or "").strip()
            slug_title = self._title_from_product_url(url)
            if slug_title and (not title or title_counts[title.casefold()] > 1):
                title = slug_title
            score = _score_result(title, query)
            if score < 45:
                continue
            cleaned.append({**item, "url": url, "title": title[:200], "score": score})
            seen.add(url)
        cleaned.sort(key=lambda item: (-item["score"], item.get("price") or 10**12))
        return cleaned[:12]
