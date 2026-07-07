import json
import re

from bs4 import BeautifulSoup

from stores.base_store import BaseStore
from stores.http_utils import fetch_with_retry, DEFAULT_HEADERS


class IntersportStore(BaseStore):
    name = "Intersport"
    driver_key = "intersport"
    domains = ("intersport.com.tr",)

    def __init__(self):
        self.headers = DEFAULT_HEADERS

    def _parse_price(self, text):
        if not text:
            return None
        text = text.upper().replace("TL", "").replace("₺", "").strip()
        text = text.replace(".", "")
        text = text.replace(",", ".")
        text = re.sub(r'[^\d.]', '', text)
        try:
            return float(text)
        except ValueError:
            return None

    def get_product_data(self, url: str, debug: bool = False) -> dict:
        response = fetch_with_retry(url, self.headers)
        if response is None:
            if debug:
                return {
                    "current_price": None, "old_price": None, "stock_count": 0,
                    "sizes": [], "in_stock": False,
                    "_debug": {"fetch_error": True, "price_confidence": 0.0, "stock_confidence": 0.0},
                }
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
                "cart_price_raw": None,
                "shelf_price_raw": None,
                "json_ld_price_raw": None,
                "price_source": None,     # "cart" | "shelf" | "json_ld" | None
                "price_confidence": 0.0,
                "variant_container_found": False,
                "stock_confidence": 0.0,
            }

            # =======================================================
            # 1. FIYAT AVCISI (Sepet Indirimi & JSON Bug Korumasi)
            # =======================================================
            cart_price = None
            cart_offers_block = soup.select_one(".product-item__offers")
            if cart_offers_block:
                price_elem = cart_offers_block.select_one(
                    ".product-item__offer-price pz-price, .product-item__offer-price"
                )
                if price_elem:
                    raw_text = price_elem.get_text(strip=True)
                    debug_info["cart_price_raw"] = raw_text
                    cart_price = self._parse_price(raw_text)

            shelf_price = None
            shelf_elem = soup.select_one(
                ".price.-has-discount pz-price, .product-price .price pz-price, "
                ".price__current, .product-price"
            )
            if shelf_elem:
                raw_text = shelf_elem.get_text(strip=True)
                debug_info["shelf_price_raw"] = raw_text
                shelf_price = self._parse_price(raw_text)

            if cart_price:
                result["current_price"] = cart_price
                result["old_price"] = shelf_price
                debug_info["price_source"] = "cart"
                debug_info["price_confidence"] = 1.0
            elif shelf_price:
                result["current_price"] = shelf_price
                debug_info["price_source"] = "shelf"
                debug_info["price_confidence"] = 1.0

            # DOM'dan hicbir fiyat okunamadiysa JSON-LD'ye dus.
            # ONEMLI: Asagidaki /10 duzeltmesi SADECE bu JSON-LD blogunun icinde
            # uygulanir (audit bulgusu #1 -- eskiden fonksiyon sonunda TUM
            # fiyatlara uygulanip DOM'dan dogru okunan >15.000 TL fiyatlari da
            # bozuyordu).
            if not result["current_price"]:
                for script in soup.find_all("script", type="application/ld+json"):
                    if not script.string:
                        continue
                    try:
                        data = json.loads(script.string.strip())
                        items = data if isinstance(data, list) else [data]
                        for item in items:
                            if isinstance(item, dict) and item.get("@type") == "Product":
                                offers = item.get("offers", [])
                                if isinstance(offers, dict):
                                    offers = [offers]
                                for offer in offers:
                                    if "price" in offer:
                                        raw_val = offer["price"]
                                        debug_info["json_ld_price_raw"] = raw_val
                                        val = float(raw_val)
                                        # Intersport JSON-LD'nin bilinen "37794.0" olcek bug'i
                                        while val > 15000:
                                            val = val / 10
                                        result["current_price"] = val
                                        debug_info["price_source"] = "json_ld"
                                        # JSON-LD, DOM'a göre daha az güvenilir kaynak
                                        # (bilinen ölçek hatası geçmişi olduğu için).
                                        debug_info["price_confidence"] = 0.6
                                        break
                    except Exception:
                        pass
                    if result["current_price"]:
                        break

            # =======================================================
            # 2. BEDEN AVCISI
            # Yalnizca <pz-variant> ve <pz-variant-option> okur.
            # =======================================================
            sizes_data = []
            beden_container = soup.find("pz-variant", attrs={"key": "integration_beden"})

            if beden_container:
                debug_info["variant_container_found"] = True
                for opt in beden_container.find_all("pz-variant-option"):
                    label = opt.get("label") or opt.get("value") or opt.get_text(strip=True)
                    if not label:
                        continue
                    # Gercek stok kontrolu: Sadece "selectable" ozelligi olanlar stoktadir!
                    in_stock = opt.has_attr("selectable")

                    sizes_data.append({
                        "name": label,
                        "size": label,
                        "in_stock": in_stock,
                        "sku": opt.get("data-product-sku"),
                        "stock_source": "pz-variant-option[selectable]",
                    })
                # Konteyner bulunduysa ve en az bir beden okunduysa, "selectable"
                # doğrudan bir yapısal sinyal olduğu için yüksek güven veriyoruz.
                debug_info["stock_confidence"] = 0.95 if sizes_data else 0.3
            else:
                # Konteyner hiç bulunamadıysa (sayfa yapısı değişmiş olabilir)
                # bunu "stok yok" ile karıştırmamak lazım -- gerçekte bilmiyoruz.
                debug_info["stock_confidence"] = 0.0

            result["sizes"] = sizes_data
            result["stock_count"] = sum(1 for s in sizes_data if s["in_stock"])
            result["in_stock"] = result["stock_count"] > 0

            if debug:
                result["_debug"] = debug_info

            return result

        except Exception as e:
            print(f"Hata (parse): {e}")
            if debug:
                return {
                    "current_price": None, "old_price": None, "stock_count": 0,
                    "sizes": [], "in_stock": False,
                    "_debug": {"parse_error": str(e), "price_confidence": 0.0, "stock_confidence": 0.0},
                }
            return None
