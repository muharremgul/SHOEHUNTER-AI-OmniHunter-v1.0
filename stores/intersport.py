import json
import requests
from bs4 import BeautifulSoup
import re

class IntersportStore:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
        }

    def _parse_price(self, text):
        if not text: return None
        text = text.upper().replace("TL", "").replace("₺", "").strip()
        text = text.replace(".", "")
        text = text.replace(",", ".")
        text = re.sub(r'[^\d.]', '', text)
        try:
            return float(text)
        except:
            return None

    def get_product_data(self, url: str) -> dict:
        try:
            session = requests.Session()
            response = session.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            result = {
                "current_price": None,
                "old_price": None,
                "stock_count": 0,
                "sizes": [],
                "in_stock": False
            }

            # =======================================================
            # 1. FİYAT AVCISI (Sepet İndirimi & JSON Bug Koruması)
            # =======================================================
            cart_price = None
            cart_offers_block = soup.select_one(".product-item__offers")
            if cart_offers_block:
                price_elem = cart_offers_block.select_one(".product-item__offer-price pz-price, .product-item__offer-price")
                if price_elem:
                    cart_price = self._parse_price(price_elem.get_text(strip=True))

            shelf_price = None
            shelf_elem = soup.select_one(".price.-has-discount pz-price, .product-price .price pz-price, .price__current, .product-price")
            if shelf_elem:
                shelf_price = self._parse_price(shelf_elem.get_text(strip=True))

            if cart_price:
                result["current_price"] = cart_price
                result["old_price"] = shelf_price
            elif shelf_price:
                result["current_price"] = shelf_price

            if not result["current_price"]:
                for script in soup.find_all("script", type="application/ld+json"):
                    if not script.string: continue
                    try:
                        data = json.loads(script.string.strip())
                        items = data if isinstance(data, list) else [data]
                        for item in items:
                            if isinstance(item, dict) and item.get("@type") == "Product":
                                offers = item.get("offers", [])
                                if isinstance(offers, dict): offers = [offers]
                                for offer in offers:
                                    if "price" in offer:
                                        val = float(offer["price"])
                                        # Intersport 37794.0 Bug'ını düzeltme
                                        while val > 15000:
                                            val = val / 10
                                        result["current_price"] = val
                                        break
                    except: pass
                    if result["current_price"]: break

            if result["current_price"] and result["current_price"] > 15000:
                while result["current_price"] > 15000:
                    result["current_price"] /= 10

            # =======================================================
            # 2. BEDEN AVCISI (KUSURSUZ ÇALIŞAN ESKİ SÜRÜME DÖNÜŞ)
            # Yalnızca <pz-variant> ve <pz-variant-option> okur.
            # =======================================================
            sizes_data = []
            beden_container = soup.find("pz-variant", attrs={"key": "integration_beden"})

            if beden_container:
                for opt in beden_container.find_all("pz-variant-option"):
                    label = opt.get("label") or opt.get("value") or opt.get_text(strip=True)
                    if not label:
                        continue
                    # Gerçek stok kontrolü: Sadece "selectable" özelliği olanlar stoktadır!
                    in_stock = opt.has_attr("selectable")
                    
                    sizes_data.append({
                        "name": label,
                        "size": label,
                        "in_stock": in_stock,
                        "sku": opt.get("data-product-sku"),
                    })

            result["sizes"] = sizes_data
            result["stock_count"] = sum(1 for s in sizes_data if s["in_stock"])
            result["in_stock"] = result["stock_count"] > 0

            return result

        except Exception as e:
            print(f"Hata: {e}")
            return None
