from engines import StoreEngine
from bs4 import BeautifulSoup

class NikeEngine(StoreEngine):
    def __init__(self):
        super().__init__()
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
            # Nike urun sayfasindaki beden butonlarini (genellikle div veya button) bulmaya calis
            # Heuristic: icinde 35, 36, ... 45 gibi rakam barindiran ufak kutular
            for label in soup.select('label:not([disabled])'):
                text = label.get_text(strip=True)
                if text.replace(',', '.').replace('EU', '').strip().replace('.5', '').isdigit():
                    sizes.append({"name": text, "stock": True})
            
            if sizes:
                result["sizes"] = sizes
                result["in_stock"] = True
                result["stock_count"] = len(sizes)

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
