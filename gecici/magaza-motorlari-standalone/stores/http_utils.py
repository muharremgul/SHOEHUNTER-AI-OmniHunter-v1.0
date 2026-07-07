"""Tüm mağaza motorlarının ortak kullandığı ağ isteği yardımcıları.

Intersport için yazılmış retry mantığı, Sportive ve Decathlon eklenirken
üç yerde kopyalanmasın diye buraya taşındı (DRY).
"""
import time
import requests

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
}


def fetch_with_retry(url: str, headers: dict = None, max_retries: int = 3, backoff_seconds: float = 1.5):
    """Ağ isteğini kademeli bekleme ile en fazla `max_retries` kez dener.

    Sadece ağ/istek hatalarını (timeout, bağlantı kopması, 5xx vb.) kapsar;
    HTML ayrıştırma hataları burada retry edilmez.
    """
    session = requests.Session()
    last_exception = None
    used_headers = headers or DEFAULT_HEADERS

    for attempt in range(1, max_retries + 1):
        try:
            response = session.get(url, headers=used_headers, timeout=15)
            response.raise_for_status()
            return response
        except Exception as exc:
            last_exception = exc
            if attempt < max_retries:
                time.sleep(backoff_seconds * attempt)

    print(f"Hata (ag): {max_retries} denemeden sonra sayfa alinamadi - {last_exception}")
    return None
