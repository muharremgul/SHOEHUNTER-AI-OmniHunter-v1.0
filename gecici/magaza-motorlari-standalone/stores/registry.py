"""Mağaza motoru kayıt defteri.

Eskiden bir listing'in hangi motorla kontrol edileceği
`"intersport" not in store_name.lower()` gibi bir string aramayla
belirleniyordu (batch_check_service.py). Bu, mağaza sayısı arttıkça
kırılgan bir yaklaşımdı ve isim değişirse (örn. "Intersport TR" gibi)
sessizce bozulabilirdi.

Artık her Store kaydı bir `driver_key` taşıyor ve bu dosya
driver_key -> StoreEngine sınıfı eşlemesini tek yerde tutuyor.
Yeni bir mağaza eklemek (örn. Sportive) tek satırla buraya kaydedilir.
"""
from stores.intersport import IntersportStore
from stores.sportive import SportiveStore
from stores.decathlon import DecathlonStore

_ENGINES = {
    IntersportStore.driver_key: IntersportStore,
    SportiveStore.driver_key: SportiveStore,
    DecathlonStore.driver_key: DecathlonStore,
}


def get_engine(driver_key: str):
    """driver_key için bir motor örneği döner, tanımlı değilse None."""
    engine_cls = _ENGINES.get(driver_key)
    return engine_cls() if engine_cls else None


def is_supported(driver_key: str) -> bool:
    return driver_key in _ENGINES


def supported_driver_keys():
    return list(_ENGINES.keys())
