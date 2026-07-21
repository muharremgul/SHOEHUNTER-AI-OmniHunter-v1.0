from engines import StoreEngine, _finalize_stock_status
from bs4 import BeautifulSoup
import re

class NewBalanceEngine(StoreEngine):
    supports_sizes = True
    supports_variants = True

    def __init__(self):
        super().__init__()
        self.name = "New Balance TR"
        self.slug = "newbalance"
        self.domains = ["newbalance.com.tr"]
        self.search_path = "https://www.newbalance.com.tr/arama?q={q}"
        self.product_pattern = r"/urun/"
        self.priority = 23
        self.js_search = False
        self.use_browser = False 
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        }

    def parse(self, html, url):
        result = super().parse(html, url)
        soup = BeautifulSoup(html, "lxml")

        # Özel beden bulma
        if not result.get("sizes"):
            sizes = []
            for label in soup.select('.product-size-container label, .product-sizes label'):
                text = label.get_text(strip=True)
                if text.replace('.', '').replace(',', '').isdigit():
                    classes = " ".join(label.get("class") or []).lower()
                    nested_input = label.find("input")
                    is_disabled = (
                        label.has_attr("disabled")
                        or str(label.get("aria-disabled", "")).lower() == "true"
                        or bool(nested_input and nested_input.has_attr("disabled"))
                        or any(token in classes for token in ("disabled", "sold-out", "soldout", "unavailable"))
                    )
                    sizes.append({
                        "name": text,
                        "size": text,
                        "in_stock": not is_disabled,
                        "sku": None,
                        "stock_source": "newbalance_label_disabled_check",
                    })
            
            if sizes:
                result["sizes"] = sizes
                _finalize_stock_status(result)

        # Özel fiyat bulma
        if not result.get("current_price"):
            price_elem = soup.select_one('.price-sales') or soup.select_one('.product-price')
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                from engines import parse_price_text
                p = parse_price_text(price_text)
                if p:
                    result["current_price"] = p
                    result["price_source"] = "nb_custom"
                    result["confidence"] = 0.8

        return result
