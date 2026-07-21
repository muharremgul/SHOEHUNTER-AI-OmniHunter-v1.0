# v0.6'da ürün adından otomatik mağaza arama burada başlayacak.
def normalize_query(query: str) -> str:
    return " ".join(query.lower().strip().split())
