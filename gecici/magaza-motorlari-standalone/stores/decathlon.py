import re

from bs4 import BeautifulSoup

from stores.base_store import BaseStore
from stores.http_utils import fetch_with_retry, DEFAULT_HEADERS


class DecathlonStore(BaseStore):
    """Decathlon.com.tr için mağaza motoru.

    Gerçek bir decathlon.com.tr ürün sayfası incelenerek yazıldı. Diğer iki
    motora göre en net stok sinyaline sahip: her beden için sayfa açıkça
    "{beden} Stokta Mevcut" veya "{beden} Stokta Mevcut Değil" metnini
    gösteriyor (hem pozitif hem negatif durumu gerçek sayfada doğrulandı).

    - Fiyat: `product:price:amount` (varsa) yoksa `product:original_price:amount`
      meta etiketi. Güven 0.85.
    - Stok: "Stokta Mevcut" / "Stokta Mevcut Değil" metin örüntüsü.
      Hem pozitif hem negatif durum gerçek sayfada görüldüğü için Sportive'e
      göre daha yüksek güven (0.75).
    """

    name = "Decathlon"
    driver_key = "decathlon"
    domains = ("decathlon.com.tr",)

    def __init__(self):
        self.headers = DEFAULT_HEADERS

    def get_product_data(self, url: str, debug: bool = False) -> dict:
        response = fetch_with_retry(url, self.headers)
        if response is None:
            if debug:
                return self._empty_result(debug_info={"fetch_error": True, "price_confidence": 0.0, "stock_confidence": 0.0})
            return None

        try:
            soup = BeautifulSoup(response.text, "html.parser")

            result = {
                "current_price": None,
                "old_price": None,
                "stock_count": 0,
                "sizes": [],
                "in_stock": False,
            }
            debug_info = {
                "price_source": None,
                "price_confidence": 0.0,
                "variant_container_found": False,
                "stock_confidence": 0.0,
            }

            # --- Fiyat: once guncel satis fiyati, yoksa orijinal fiyat ---
            price_tag = soup.find("meta", attrs={"property": "product:price:amount"})
            source = "product:price:amount"
            if not price_tag or not price_tag.get("content"):
                price_tag = soup.find("meta", attrs={"property": "product:original_price:amount"})
                source = "product:original_price:amount"

            if price_tag and price_tag.get("content"):
                try:
                    result["current_price"] = float(price_tag["content"])
                    debug_info["price_source"] = source
                    debug_info["price_confidence"] = 0.85
                except ValueError:
                    pass

            # --- Stok: "Stokta Mevcut" / "Stokta Mevcut Değil" metin örüntüsü ---
            full_text = soup.get_text(" ", strip=True)

            sizes_data = []
            pattern = re.compile(r'(\d{2}(?:[.,]\d)?)\s*Stokta Mevcut(\s*Değil)?', re.IGNORECASE)
            for match in pattern.finditer(full_text):
                size_label = match.group(1)
                is_out_of_stock = bool(match.group(2))
                if any(s["name"] == size_label for s in sizes_data):
                    continue
                sizes_data.append({
                    "name": size_label,
                    "size": size_label,
                    "in_stock": not is_out_of_stock,
                    "sku": None,
                    "stock_source": "text_pattern:Stokta Mevcut",
                })

            if sizes_data:
                debug_info["variant_container_found"] = True
                debug_info["stock_confidence"] = 0.75

            result["sizes"] = sizes_data
            result["stock_count"] = sum(1 for s in sizes_data if s["in_stock"])
            result["in_stock"] = result["stock_count"] > 0

            if debug:
                result["_debug"] = debug_info

            return result

        except Exception as e:
            print(f"Hata (parse): {e}")
            if debug:
                return self._empty_result(debug_info={"parse_error": str(e), "price_confidence": 0.0, "stock_confidence": 0.0})
            return None

    @staticmethod
    def _empty_result(debug_info):
        return {
            "current_price": None, "old_price": None, "stock_count": 0,
            "sizes": [], "in_stock": False, "_debug": debug_info,
        }
