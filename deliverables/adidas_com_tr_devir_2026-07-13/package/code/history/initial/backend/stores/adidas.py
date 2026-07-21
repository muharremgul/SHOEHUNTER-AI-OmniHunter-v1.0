"""Adidas.com.tr özel mağaza motoru.

Kullanıcının yazdığı JSON-LD (ProductGroup) tabanlı mantık kullanılarak
asenkron yapıya entegre edilmiştir.
"""
import json
import sys
import os
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engines import StoreEngine, _extract_variant_urls


class AdidasEngine(StoreEngine):
    name = "Adidas Türkiye"
    slug = "adidas"
    domains = ["adidas.com.tr"]
    search_path = "https://www.adidas.com.tr/tr/search?q={q}"
    product_pattern = r"/[A-Z]{2}\d{4}\.html"
    priority = 21
    js_search = True
    use_browser = True  # Adidas Cloudflare 403 hatasi verdigi icin Playwright kullanimi sarttir

    def parse(self, html, url):
        soup = BeautifulSoup(html, "lxml")
        result = self.base_result(url)
        dbg = result["debug"]

        # Ortak baslik ve meta veri ayristirma (StoreEngine icerisinden)
        self.parse_common_meta(soup, result)

        # Kullanicinin yazdigi kusursuz JSON-LD (ProductGroup) ayristirma mantigi
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
            # Gercek beden varyantlari (size ve offers)
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
                result["price_source"] = "json_ld:ProductGroup.hasVariant.offers.price"
                result["confidence"] = 0.9
                dbg["price_candidates"].append({"source": "json_ld", "value": result["current_price"]})
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
            
            if sizes_data:
                dbg["notes"].append(f"adidas_stock: {result['stock_count']}/{len(sizes_data)} beden stokta (json_ld)")
            break

        # Sitedeki diger renk/model linklerini de topluyoruz
        result["variant_urls"] = _extract_variant_urls(soup, url)

        return result
