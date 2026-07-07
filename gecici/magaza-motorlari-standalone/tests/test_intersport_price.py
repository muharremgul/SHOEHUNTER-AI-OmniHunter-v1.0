"""
stores/intersport.py testleri.

Bu dosya hem `pytest tests/` hem de `python -m unittest` ile çalışır
(unittest.TestCase pytest tarafından otomatik keşfedilir).
"""
import os
import unittest
from unittest.mock import patch, MagicMock

import requests

from stores.intersport import IntersportStore

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _load_fixture(name: str) -> str:
    with open(os.path.join(FIXTURES_DIR, name), "r", encoding="utf-8") as f:
        return f.read()


def _mock_response(html: str, status_ok=True):
    resp = MagicMock()
    resp.text = html
    if status_ok:
        resp.raise_for_status = MagicMock(return_value=None)
    else:
        resp.raise_for_status = MagicMock(side_effect=requests.exceptions.HTTPError("500"))
    return resp


class TestParsePrice(unittest.TestCase):
    """Saf fonksiyon: TL fiyat metnini float'a çevirme."""

    def setUp(self):
        self.store = IntersportStore()

    def test_standart_bicim(self):
        self.assertEqual(self.store._parse_price("4.599,90 TL"), 4599.90)

    def test_lira_isareti(self):
        self.assertEqual(self.store._parse_price("₺ 1.250,00"), 1250.00)

    def test_bosluksuz(self):
        self.assertEqual(self.store._parse_price("999,00TL"), 999.00)

    def test_bos_metin_none_doner(self):
        self.assertIsNone(self.store._parse_price(""))
        self.assertIsNone(self.store._parse_price(None))

    def test_sayisal_olmayan_metin_none_doner(self):
        self.assertIsNone(self.store._parse_price("Stokta Yok"))


class TestGetProductData(unittest.TestCase):
    def setUp(self):
        self.store = IntersportStore()

    @patch("requests.Session.get")
    def test_normal_urun_fiyat_ve_bedenler(self, mock_get):
        mock_get.return_value = _mock_response(_load_fixture("intersport_normal.html"))

        data = self.store.get_product_data("https://www.intersport.com.tr/test")

        self.assertEqual(data["current_price"], 4599.90)
        self.assertIsNone(data["old_price"])
        sizes_by_name = {s["name"]: s["in_stock"] for s in data["sizes"]}
        self.assertTrue(sizes_by_name["42"])
        self.assertFalse(sizes_by_name["42.5"])
        self.assertTrue(sizes_by_name["43"])
        self.assertFalse(sizes_by_name["44"])
        self.assertEqual(data["stock_count"], 2)
        self.assertTrue(data["in_stock"])

    @patch("requests.Session.get")
    def test_sepet_indirimi_gercek_odeme_fiyatini_yakalar(self, mock_get):
        mock_get.return_value = _mock_response(_load_fixture("intersport_cart_discount.html"))

        data = self.store.get_product_data("https://www.intersport.com.tr/test")

        # Kullanıcı senaryosu (gelişmeler 2.md, Senaryo B): raf fiyatı 6299 TL
        # görünüyor ama sepette 3779 TL. Sistem gerçek ödeme fiyatını (sepet)
        # current_price yapmalı, raf fiyatını old_price'a koymalı.
        self.assertEqual(data["current_price"], 3779.00)
        self.assertEqual(data["old_price"], 6299.00)

    @patch("requests.Session.get")
    def test_15000_tl_ustu_dom_fiyati_artik_bozulmuyor(self, mock_get):
        """REGRESYON TESTİ (audit bulgusu #1):
        Eskiden fonksiyonun sonunda TÜM fiyatlara (DOM'dan doğru okunanlar
        dahil) '15.000 TL üstüyse 10'a böl' mantığı uygulanıyordu. Bu da
        gerçekten 16.500 TL olan bir ürünün fiyatını sessizce 1.650 TL'ye
        düşürüp yanlış kaydediyor, hedef fiyatı 'tutmuş' gibi görünüp sahte
        bir Telegram alarmı tetikleyebiliyordu. Bu test, düzeltmenin kalıcı
        olduğunu garanti eder.
        """
        mock_get.return_value = _mock_response(_load_fixture("intersport_high_price_dom.html"))

        data = self.store.get_product_data("https://www.intersport.com.tr/test")

        self.assertEqual(data["current_price"], 16500.00)

    @patch("requests.Session.get")
    def test_jsonld_olcek_bugu_hala_duzeltiliyor(self, mock_get):
        """JSON-LD'nin bilinen '37794.0' tarzı ölçek hatası hâlâ düzeltilmeli
        -- sadece bu düzeltmenin kapsamı artık JSON-LD yoluyla sınırlı."""
        mock_get.return_value = _mock_response(_load_fixture("intersport_jsonld_bug.html"))

        data = self.store.get_product_data("https://www.intersport.com.tr/test")

        # 37990.0 -> /10 -> 3799.0 (15000 altına düşünce durur)
        self.assertEqual(data["current_price"], 3799.0)

    @patch("requests.Session.get")
    def test_tukenen_urun_stok_sayisi_sifir(self, mock_get):
        mock_get.return_value = _mock_response(_load_fixture("intersport_out_of_stock.html"))

        data = self.store.get_product_data("https://www.intersport.com.tr/test")

        self.assertEqual(data["stock_count"], 0)
        self.assertFalse(data["in_stock"])


class TestDebugMode(unittest.TestCase):
    """Debug Lab özelliği (Faz 5): debug=True verildiğinde ham fiyat
    kaynakları ve güven skorları döner."""

    def setUp(self):
        self.store = IntersportStore()

    @patch("requests.Session.get")
    def test_normal_urunde_dom_fiyati_yuksek_guvenle_isaretlenir(self, mock_get):
        mock_get.return_value = _mock_response(_load_fixture("intersport_normal.html"))

        data = self.store.get_product_data("https://www.intersport.com.tr/test", debug=True)

        self.assertIn("_debug", data)
        self.assertEqual(data["_debug"]["price_source"], "shelf")
        self.assertEqual(data["_debug"]["price_confidence"], 1.0)
        self.assertTrue(data["_debug"]["variant_container_found"])
        self.assertGreaterEqual(data["_debug"]["stock_confidence"], 0.9)

    @patch("requests.Session.get")
    def test_jsonld_fiyati_dusuk_guvenle_isaretlenir(self, mock_get):
        mock_get.return_value = _mock_response(_load_fixture("intersport_jsonld_bug.html"))

        data = self.store.get_product_data("https://www.intersport.com.tr/test", debug=True)

        self.assertEqual(data["_debug"]["price_source"], "json_ld")
        self.assertLess(data["_debug"]["price_confidence"], 1.0)

    @patch("requests.Session.get")
    def test_varyant_konteyneri_bulunamazsa_stok_guveni_sifir(self, mock_get):
        html = "<html><body><div class='product-price'><span class='price__current'>1.000,00 TL</span></div></body></html>"
        mock_get.return_value = _mock_response(html)

        data = self.store.get_product_data("https://www.intersport.com.tr/test", debug=True)

        # Beden konteyneri hiç yoksa "stokta yok" ile karıştırılmamalı --
        # gerçekte bilmiyoruz, bu yüzden güven 0.0 olmalı.
        self.assertFalse(data["_debug"]["variant_container_found"])
        self.assertEqual(data["_debug"]["stock_confidence"], 0.0)

    def test_debug_false_iken_debug_anahtari_hic_gelmez(self):
        with patch("requests.Session.get") as mock_get:
            mock_get.return_value = _mock_response(_load_fixture("intersport_normal.html"))
            data = self.store.get_product_data("https://www.intersport.com.tr/test")
        self.assertNotIn("_debug", data)


class TestRetryMechanism(unittest.TestCase):
    """Audit bulgusu #2: belgelenen '3 deneme' retry mekanizması eskiden
    kodda yoktu. Bu testler yeni eklenen retry davranışını doğrular."""

    def setUp(self):
        self.store = IntersportStore()

    @patch("time.sleep", return_value=None)  # testleri yavaşlatmasın
    @patch("requests.Session.get")
    def test_ilk_iki_deneme_basarisiz_ucuncude_basarili(self, mock_get, mock_sleep):
        ok_response = _mock_response(_load_fixture("intersport_normal.html"))
        mock_get.side_effect = [
            requests.exceptions.ConnectionError("bağlantı koptu"),
            requests.exceptions.Timeout("zaman aşımı"),
            ok_response,
        ]

        data = self.store.get_product_data("https://www.intersport.com.tr/test")

        self.assertIsNotNone(data)
        self.assertEqual(data["current_price"], 4599.90)
        self.assertEqual(mock_get.call_count, 3)

    @patch("time.sleep", return_value=None)
    @patch("requests.Session.get")
    def test_uc_deneme_de_basarisizsa_none_doner_sahte_alarm_yok(self, mock_get, mock_sleep):
        mock_get.side_effect = requests.exceptions.ConnectionError("site çöktü")

        data = self.store.get_product_data("https://www.intersport.com.tr/test")

        self.assertIsNone(data)
        self.assertEqual(mock_get.call_count, 3)


if __name__ == "__main__":
    unittest.main()
