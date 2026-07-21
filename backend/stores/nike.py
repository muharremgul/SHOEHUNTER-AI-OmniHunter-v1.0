from engines import StoreEngine, _finalize_stock_status
from bs4 import BeautifulSoup

class NikeEngine(StoreEngine):
    supports_sizes = True
    supports_variants = True

    def __init__(self):
        super().__init__()
        self.name = "Nike TR"
        self.slug = "nike"
        self.domains = ["nike.com"]
        self.search_path = "https://www.nike.com/tr/w?q={q}"
        self.product_pattern = r"/t/"
        self.priority = 20
        self.js_search = False
        # Nike TR requests'i bloklamadigi icin Playwright'a gerek yok
        self.use_browser = False 
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        }

    def parse(self, html, url):
        # Temel ayrıştırma (fiyat vs. bulmak icin engines.py'deki base fonksiyonu cagir)
        result = super().parse(html, url)
        soup = BeautifulSoup(html, "lxml")

        # Özel beden bulma mantigi (CSS selector)
        if not result.get("sizes"):
            sizes = []
            # Nike urun sayfasindaki beden etiketlerini bul ve disabled/sold-out durumunu ayir.
            for label in soup.select("label"):
                text = label.get_text(strip=True)
                if text.replace(',', '.').replace('EU', '').strip().replace('.5', '').isdigit():
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
                        "stock_source": "nike_label_disabled_check",
                    })
            
            if sizes:
                result["sizes"] = sizes
                _finalize_stock_status(result)

        # Fiyat bulunamadiysa HTML icinden metin bazli fiyat cikar
        if not result.get("current_price"):
            for div in soup.select('div[data-testid="product-price"]'):
                price_text = div.get_text(strip=True)
                from engines import parse_price_text
                p = parse_price_text(price_text)
                if p:
                    result["current_price"] = p
                    result["price_source"] = "nike_custom_div"
                    result["confidence"] = 0.8
                    break

        return result
