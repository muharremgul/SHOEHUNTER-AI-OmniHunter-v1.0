from engines import StoreEngine
from bs4 import BeautifulSoup
import re

class PumaEngine(StoreEngine):
    def __init__(self):
        super().__init__()
        # Puma bot korumasi (403) yapmadigi icin standart http ile baslayabiliriz
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
            for btn in soup.select('button[data-attr-value]'):
                val = btn.get('data-attr-value', '').strip()
                # 40, 41, 42 gibi sayilari topla
                if val.replace('.', '').replace(',', '').isdigit() and len(val) <= 4:
                    sizes.append({"name": val, "stock": True})
            
            if sizes:
                result["sizes"] = sizes
                result["in_stock"] = True
                result["stock_count"] = len(sizes)

        # Özel fiyat bulma
        if not result.get("current_price"):
            price_elem = soup.select_one('.sales .value') or soup.select_one('[data-price-value]')
            if price_elem:
                price_text = price_elem.get('data-price-value') or price_elem.get_text(strip=True)
                from engines import parse_price_text
                p = parse_price_text(price_text)
                if p:
                    result["current_price"] = p
                    result["price_source"] = "puma_custom"
                    result["confidence"] = 0.8

        return result
