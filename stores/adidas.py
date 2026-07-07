import json
import requests
from bs4 import BeautifulSoup
from stores.base_store import BaseStore

class AdidasStore(BaseStore):
    name = "Adidas Türkiye"
    driver_key = "adidas"
    domains = ("adidas.com.tr",)

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
        }

    def get_product_data(self, url: str, debug: bool = False) -> dict:
        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            if response.status_code != 200:
                if debug:
                    return self._empty_result({"fetch_error": True, "status": response.status_code})
                return None
        except Exception as e:
            if debug:
                return self._empty_result({"fetch_error": True, "error": str(e)})
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

            for script in soup.find_all("script", type="application/ld+json"):
                if not script.string:
                    continue
                try:
                    data = json.loads(script.string)
                except (json.JSONDecodeError, TypeError):
                    continue

                if not isinstance(data, dict) or data.get("@type") != "ProductGroup":
                    continue

                variants = data.get("hasVariant", [])
                size_variants = [v for v in variants if v.get("size") and v.get("offers")]

                if not size_variants:
                    break

                sizes_data = []
                for v in size_variants:
                    offers = v["offers"]
                    availability = str(offers.get("availability", "")).lower()
                    in_stock = "instock" in availability

                    sizes_data.append({
                        "name": str(v["size"]),
                        "size": str(v["size"]),
                        "in_stock": in_stock,
                        "sku": v.get("sku"),
                        "stock_source": "json_ld:ProductGroup.hasVariant.offers.availability",
                    })

                in_stock_variants = [v for v in size_variants if "instock" in str(v["offers"].get("availability", "")).lower()]
                price_source_variant = in_stock_variants[0] if in_stock_variants else size_variants[0]
                offers = price_source_variant["offers"]

                try:
                    result["current_price"] = float(offers["price"])
                    debug_info["price_source"] = "json_ld:ProductGroup.hasVariant.offers.price"
                    debug_info["price_confidence"] = 0.9
                except (KeyError, TypeError, ValueError):
                    pass

                price_spec = offers.get("priceSpecification")
                if isinstance(price_spec, dict) and "strikethrough" in str(price_spec.get("priceType", "")).lower():
                    try:
                        result["old_price"] = float(price_spec["price"])
                    except (KeyError, TypeError, ValueError):
                        pass

                result["sizes"] = sizes_data
                result["stock_count"] = sum(1 for s in sizes_data if s["in_stock"])
                result["in_stock"] = result["stock_count"] > 0
                debug_info["variant_container_found"] = True
                debug_info["stock_confidence"] = 0.9
                break

            if debug:
                result["_debug"] = debug_info

            return result

        except Exception as e:
            if debug:
                return self._empty_result({"parse_error": str(e), "price_confidence": 0.0, "stock_confidence": 0.0})
            return None

    @staticmethod
    def _empty_result(debug_info):
        return {
            "current_price": None, "old_price": None, "stock_count": 0,
            "sizes": [], "in_stock": False, "_debug": debug_info,
        }
