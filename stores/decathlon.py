import re
import requests
from bs4 import BeautifulSoup
from stores.base_store import BaseStore

class DecathlonStore(BaseStore):
    name = "Decathlon"
    driver_key = "decathlon"
    domains = ("decathlon.com.tr",)

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
        }

    def get_product_data(self, url: str, debug: bool = False) -> dict:
        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            # 403 dahil hatali durumlarda None donmemesi icin status_code kontrolu
            if response.status_code != 200:
                if debug:
                    return self._empty_result(debug_info={"fetch_error": True, "status": response.status_code})
                return None
        except Exception as e:
            if debug:
                return self._empty_result(debug_info={"fetch_error": True, "error": str(e)})
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
            if debug:
                return self._empty_result(debug_info={"parse_error": str(e)})
            return None

    @staticmethod
    def _empty_result(debug_info):
        return {
            "current_price": None, "old_price": None, "stock_count": 0,
            "sizes": [], "in_stock": False, "_debug": debug_info,
        }
