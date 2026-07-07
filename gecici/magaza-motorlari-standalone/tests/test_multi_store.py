"""stores/sportive.py ve stores/decathlon.py testleri.

Fixture'lar gerçek sportive.com.tr ve decathlon.com.tr ürün sayfaları
incelenerek (web_fetch ile) hazırlandı -- bkz. dosya başındaki docstring'ler.
"""
import os
import unittest
from unittest.mock import patch, MagicMock

from stores.sportive import SportiveStore
from stores.decathlon import DecathlonStore
from stores.adidas import AdidasStore

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _load_fixture(name: str) -> str:
    with open(os.path.join(FIXTURES_DIR, name), "r", encoding="utf-8") as f:
        return f.read()


def _mock_response(html: str):
    resp = MagicMock()
    resp.text = html
    resp.raise_for_status = MagicMock(return_value=None)
    return resp


class TestSportiveStore(unittest.TestCase):
    """v2: kullanıcının gönderdiği gerçek sayfa kaydı (adidas-adizero-evo-sl...)
    incelenerek düzeltildi. İlk sürüm `<meta property="og:price:amount">`
    arıyordu ama site bunu `name=` ile yazıyor -- hiç çalışmamıştı."""

    def setUp(self):
        self.store = SportiveStore()

    def test_supports_url_dogru_domain(self):
        self.assertTrue(self.store.supports_url("https://www.sportive.com.tr/urun-x"))
        self.assertFalse(self.store.supports_url("https://www.intersport.com.tr/urun-x"))

    @patch("requests.Session.get")
    def test_fiyat_json_ld_offers_price_ten_okunur(self, mock_get):
        mock_get.return_value = _mock_response(_load_fixture("sportive_normal.html"))

        data = self.store.get_product_data("https://www.sportive.com.tr/test")

        self.assertEqual(data["current_price"], 7649.0)

    @patch("requests.Session.get")
    def test_meta_name_fallback_calisir_json_ld_yoksa(self, mock_get):
        mock_get.return_value = _mock_response(_load_fixture("sportive_all_sold_out.html"))

        data = self.store.get_product_data("https://www.sportive.com.tr/test")

        self.assertEqual(data["current_price"], 7999.0)

    @patch("requests.Session.get")
    def test_renk_varyant_butonlari_beden_sayilmaz(self, mock_get):
        mock_get.return_value = _mock_response(_load_fixture("sportive_normal.html"))

        data = self.store.get_product_data("https://www.sportive.com.tr/test")

        size_names = [s["name"] for s in data["sizes"]]
        self.assertNotIn("N34", size_names)  # renk butonu, beden degil

    @patch("requests.Session.get")
    def test_tukendi_p_etiketi_dogru_bedenleri_isaretler(self, mock_get):
        mock_get.return_value = _mock_response(_load_fixture("sportive_normal.html"))

        data = self.store.get_product_data("https://www.sportive.com.tr/test")

        sizes_by_name = {s["name"]: s["in_stock"] for s in data["sizes"]}
        self.assertTrue(sizes_by_name["41"])
        self.assertTrue(sizes_by_name["42"])
        self.assertFalse(sizes_by_name["46"])
        self.assertFalse(sizes_by_name["46,5"])

    @patch("requests.Session.get")
    def test_hepsi_tukenmisse_in_stock_false(self, mock_get):
        mock_get.return_value = _mock_response(_load_fixture("sportive_all_sold_out.html"))

        data = self.store.get_product_data("https://www.sportive.com.tr/test")

        self.assertEqual(data["stock_count"], 0)
        self.assertFalse(data["in_stock"])

    @patch("requests.Session.get")
    def test_debug_modu_yuksek_guven_dondurur(self, mock_get):
        """Artık gerçek buton yapısına dayandığı için güven 0.5 -> 0.85'e
        yükseltildi (Intersport'un yapısal selectable'ına daha yakın)."""
        mock_get.return_value = _mock_response(_load_fixture("sportive_normal.html"))

        data = self.store.get_product_data("https://www.sportive.com.tr/test", debug=True)

        self.assertEqual(data["_debug"]["price_confidence"], 0.9)
        self.assertEqual(data["_debug"]["stock_confidence"], 0.85)


class TestDecathlonStore(unittest.TestCase):
    def setUp(self):
        self.store = DecathlonStore()

    def test_supports_url_dogru_domain(self):
        self.assertTrue(self.store.supports_url("https://www.decathlon.com.tr/p/urun-x"))
        self.assertFalse(self.store.supports_url("https://www.sportive.com.tr/urun-x"))

    @patch("requests.Session.get")
    def test_fiyat_original_price_metadan_okunur(self, mock_get):
        mock_get.return_value = _mock_response(_load_fixture("decathlon_normal.html"))

        data = self.store.get_product_data("https://www.decathlon.com.tr/p/test")

        self.assertEqual(data["current_price"], 3250.0)

    @patch("requests.Session.get")
    def test_indirimliyse_guncel_fiyat_tercih_edilir(self, mock_get):
        """product:price:amount varsa (indirimli/guncel satis fiyati),
        product:original_price:amount yerine o kullanilmali."""
        mock_get.return_value = _mock_response(_load_fixture("decathlon_discounted.html"))

        data = self.store.get_product_data("https://www.decathlon.com.tr/p/test")

        self.assertEqual(data["current_price"], 2990.0)

    @patch("requests.Session.get")
    def test_stokta_mevcut_degil_dogru_isaretlenir(self, mock_get):
        mock_get.return_value = _mock_response(_load_fixture("decathlon_normal.html"))

        data = self.store.get_product_data("https://www.decathlon.com.tr/p/test")

        sizes_by_name = {s["name"]: s["in_stock"] for s in data["sizes"]}
        self.assertTrue(sizes_by_name["39"])
        self.assertTrue(sizes_by_name["46"])
        self.assertFalse(sizes_by_name["47"])
        self.assertEqual(data["stock_count"], 8)

    @patch("requests.Session.get")
    def test_debug_modu_daha_yuksek_stok_guveni(self, mock_get):
        """Decathlon'da hem pozitif hem negatif stok metni gerçek sayfada
        doğrulandığı için Sportive'den daha yüksek güven verilmeli."""
        mock_get.return_value = _mock_response(_load_fixture("decathlon_normal.html"))

        data = self.store.get_product_data("https://www.decathlon.com.tr/p/test", debug=True)

        self.assertEqual(data["_debug"]["stock_confidence"], 0.75)
        self.assertGreater(data["_debug"]["stock_confidence"], 0.5)  # Sportive'den yuksek


class TestAdidasStore(unittest.TestCase):
    """Kullanıcının gönderdiği gerçek sayfa kaydı (Terrex Agravic Speed
    Ultra - Mor) incelenerek yazıldı. 4 site arasında en yapılandırılmış
    veri kaynağı: ProductGroup + hasVariant JSON-LD, her beden için gerçek
    fiyat + stok durumu ayrı ayrı geliyor."""

    def setUp(self):
        self.store = AdidasStore()

    def test_supports_url_dogru_domain(self):
        self.assertTrue(self.store.supports_url("https://www.adidas.com.tr/urun.html"))
        self.assertFalse(self.store.supports_url("https://www.sportive.com.tr/urun-x"))

    @patch("requests.Session.get")
    def test_fiyat_stoktaki_ilk_varyanttan_okunur(self, mock_get):
        mock_get.return_value = _mock_response(_load_fixture("adidas_normal.html"))

        data = self.store.get_product_data("https://www.adidas.com.tr/JQ1616.html")

        self.assertEqual(data["current_price"], 5669.0)

    @patch("requests.Session.get")
    def test_strikethrough_eski_fiyat_dogru_okunur(self, mock_get):
        mock_get.return_value = _mock_response(_load_fixture("adidas_normal.html"))

        data = self.store.get_product_data("https://www.adidas.com.tr/JQ1616.html")

        self.assertEqual(data["old_price"], 12599.0)

    @patch("requests.Session.get")
    def test_renk_ozeti_girdileri_beden_sayilmaz(self, mock_get):
        """hasVariant listesindeki diğer renklere işaret eden özet
        girdilerin (size/offers'sız) beden olarak sayılmaması gerekir."""
        mock_get.return_value = _mock_response(_load_fixture("adidas_normal.html"))

        data = self.store.get_product_data("https://www.adidas.com.tr/JQ1616.html")

        size_names = [s["name"] for s in data["sizes"]]
        self.assertEqual(len(size_names), 4)  # 6 hasVariant - 2 renk ozeti = 4 gercek beden

    @patch("requests.Session.get")
    def test_outofstock_dogru_isaretlenir(self, mock_get):
        mock_get.return_value = _mock_response(_load_fixture("adidas_normal.html"))

        data = self.store.get_product_data("https://www.adidas.com.tr/JQ1616.html")

        sizes_by_name = {s["name"]: s["in_stock"] for s in data["sizes"]}
        self.assertTrue(sizes_by_name["36"])
        self.assertFalse(sizes_by_name["38"])  # OutOfStock
        self.assertTrue(sizes_by_name["44"])

    @patch("requests.Session.get")
    def test_indirimsiz_urunde_old_price_none(self, mock_get):
        mock_get.return_value = _mock_response(_load_fixture("adidas_no_discount.html"))

        data = self.store.get_product_data("https://www.adidas.com.tr/AB1234.html")

        self.assertEqual(data["current_price"], 3200.0)
        self.assertIsNone(data["old_price"])

    @patch("requests.Session.get")
    def test_debug_modu_yuksek_guven_dondurur(self, mock_get):
        mock_get.return_value = _mock_response(_load_fixture("adidas_normal.html"))

        data = self.store.get_product_data("https://www.adidas.com.tr/JQ1616.html", debug=True)

        self.assertEqual(data["_debug"]["price_confidence"], 0.9)
        self.assertEqual(data["_debug"]["stock_confidence"], 0.9)


class TestRetryReuseAcrossStores(unittest.TestCase):
    """stores/http_utils.py'nin ortak retry mantığının her iki yeni
    motorda da çalıştığını doğrular (audit: DRY refactor sonrası regresyon)."""

    @patch("time.sleep", return_value=None)
    @patch("requests.Session.get")
    def test_sportive_de_retry_calisir(self, mock_get, mock_sleep):
        import requests
        mock_get.side_effect = [
            requests.exceptions.ConnectionError("koptu"),
            _mock_response(_load_fixture("sportive_normal.html")),
        ]

        data = SportiveStore().get_product_data("https://www.sportive.com.tr/test")

        self.assertIsNotNone(data)
        self.assertEqual(mock_get.call_count, 2)

    @patch("time.sleep", return_value=None)
    @patch("requests.Session.get")
    def test_decathlon_da_retry_calisir(self, mock_get, mock_sleep):
        import requests
        mock_get.side_effect = [
            requests.exceptions.ConnectionError("koptu"),
            _mock_response(_load_fixture("decathlon_normal.html")),
        ]

        data = DecathlonStore().get_product_data("https://www.decathlon.com.tr/p/test")

        self.assertIsNotNone(data)
        self.assertEqual(mock_get.call_count, 2)

    @patch("time.sleep", return_value=None)
    @patch("requests.Session.get")
    def test_adidas_da_retry_calisir(self, mock_get, mock_sleep):
        import requests
        mock_get.side_effect = [
            requests.exceptions.ConnectionError("koptu"),
            _mock_response(_load_fixture("adidas_normal.html")),
        ]

        data = AdidasStore().get_product_data("https://www.adidas.com.tr/JQ1616.html")

        self.assertIsNotNone(data)
        self.assertEqual(mock_get.call_count, 2)


if __name__ == "__main__":
    unittest.main()
