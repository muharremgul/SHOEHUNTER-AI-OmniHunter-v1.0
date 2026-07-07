from abc import ABC, abstractmethod


class BaseStore(ABC):
    """Her mağaza motoru bu arayüzü uygular.

    Master Proje Tanımı §12'deki standart genişletildi: `driver_key` her
    motorun kendini tanıttığı sabit bir anahtardır (stores/registry.py bunu
    kullanır). `supports_url` ile bir linkin bu motora mı ait olduğu, isim
    eşleşmesi yerine URL'in kendisine bakarak anlaşılabilir.
    """

    name: str = "BaseStore"
    driver_key: str = "base"
    domains: tuple = ()

    def supports_url(self, url: str) -> bool:
        if not url:
            return False
        url_lower = url.lower()
        return any(domain in url_lower for domain in self.domains)

    @abstractmethod
    def get_product_data(self, url: str, debug: bool = False) -> dict:
        """Standart dönüş sözlüğü (Master Proje Tanımı §12):
        current_price, old_price, stock_count, sizes, in_stock.
        debug=True verilirse ek olarak "_debug" anahtarı da içerir.
        """
        raise NotImplementedError

    def search(self, query: str):
        """v0.6+ Zero-Link Search için ayrılmış -- şu an hiçbir motor bunu
        gerçek olarak uygulamıyor (bkz. CHANGELOG: bilinçli olarak kapsam dışı)."""
        raise NotImplementedError(f"{self.name} henüz arama desteklemiyor.")
