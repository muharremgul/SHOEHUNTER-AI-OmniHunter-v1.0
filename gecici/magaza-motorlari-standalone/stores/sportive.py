import json
import re

from bs4 import BeautifulSoup

from stores.base_store import BaseStore
from stores.http_utils import fetch_with_retry, DEFAULT_HEADERS

# Beden butonlarinin id'si dogrudan beden etiketidir (orn. "41", "42,5").
# Renk/varyant kucuk resim butonlari ise "N34", "N04" gibi harf+rakam ID
# tasir -- bu deseni tutmaz, boylece ikisi ayirt edilir.
_SIZE_ID_PATTERN = re.compile(r'^\d{2}(?:,\d)?$')


class SportiveStore(BaseStore):
    """Sportive.com.tr için mağaza motoru (v2 -- gerçek indirilmiş sayfa
    incelenerek düzeltildi).

    İlk sürüm `<meta property="og:price:amount">` arıyordu ve hiçbir zaman
    çalışmadı çünkü site bu etiketi `property=` değil `name=` özniteliğiyle
    yazıyor: `<meta name="og:price:amount" content="7649">`. Kullanıcının
    gönderdiği gerçek sayfa kaydı incelenerek düzeltildi ve DAHA GÜVENİLİR
    bir yapıya geçildi:

    - Fiyat: schema.org JSON-LD (`Product.offers.price`) -- standart, ve
      `og:price:amount` meta etiketine göre daha az kırılgan. Güven 0.9.
      Meta etiket (artık doğru `name=` ile) yedek olarak kullanılıyor.
    - Stok: her beden bir `<button id="{beden}">` -- tükenen bedenlerin
      İÇİNDE ayrıca "Tükendi" metnini taşıyan bir `<p>` var (bu string
      sitenin kendi i18n sözlüğünde "not_stock" anahtarına karşılık geliyor,
      yani kararlı bir sinyal). Bu artık Intersport'un `selectable`
      özniteliği kadar yapısal olduğu için güven 0.5 -> 0.85'e yükseltildi.
    """

    name = "Sportive"
    driver_key = "sportive"
    domains = ("sportive.com.tr",)

    def __init__(self):
        self.headers = DEFAULT_HEADERS

    def get_product_data(self, url: str, debug: bool = False) -> dict:
        response = fetch_with_retry(url, self.headers)
        if response is None:
            if debug:
                return self._empty_result({"fetch_error": True, "price_confidence": 0.0, "stock_confidence": 0.0})
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

            # --- 1. Fiyat: once JSON-LD (Product.offers.price), sonra meta ---
            for script in soup.find_all("script", type="application/ld+json"):
                if not script.string:
                    continue
                try:
                    data = json.loads(script.string)
                except (json.JSONDecodeError, TypeError):
                    continue
                if isinstance(data, dict) and data.get("@type") == "Product":
                    offers = data.get("offers")
                    if isinstance(offers, dict) and offers.get("price"):
                        try:
                            result["current_price"] = float(offers["price"])
                            debug_info["price_source"] = "json_ld:Product.offers.price"
                            debug_info["price_confidence"] = 0.9
                        except (ValueError, TypeError):
                            pass
                        break

            if result["current_price"] is None:
                # NOT: site bu etiketi `property=` DEĞİL `name=` ile yazıyor.
                price_tag = soup.find("meta", attrs={"name": "og:price:amount"})
                if price_tag and price_tag.get("content"):
                    try:
                        result["current_price"] = float(price_tag["content"])
                        debug_info["price_source"] = "meta[name=og:price:amount]"
                        debug_info["price_confidence"] = 0.7
                    except ValueError:
                        pass

            # --- 2. Stok: <button id="{beden}"> + içinde "Tükendi" <p> var mı ---
            sizes_data = []
            for button in soup.find_all("button", id=True):
                size_label = button["id"]
                if not _SIZE_ID_PATTERN.match(size_label):
                    continue  # renk/varyant butonu, beden değil

                sold_out = any("tükendi" in p.get_text(strip=True).lower() for p in button.find_all("p"))

                sizes_data.append({
                    "name": size_label,
                    "size": size_label,
                    "in_stock": not sold_out,
                    "sku": None,
                    "stock_source": 'button#id + <p>Tükendi</p>',
                })

            result["sizes"] = sizes_data
            result["stock_count"] = sum(1 for s in sizes_data if s["in_stock"])
            result["in_stock"] = result["stock_count"] > 0
            if sizes_data:
                debug_info["variant_container_found"] = True
                debug_info["stock_confidence"] = 0.85

            if debug:
                result["_debug"] = debug_info

            return result

        except Exception as e:
            print(f"Hata (parse): {e}")
            if debug:
                return self._empty_result({"parse_error": str(e), "price_confidence": 0.0, "stock_confidence": 0.0})
            return None

    @staticmethod
    def _empty_result(debug_info):
        return {
            "current_price": None, "old_price": None, "stock_count": 0,
            "sizes": [], "in_stock": False, "_debug": debug_info,
        }
