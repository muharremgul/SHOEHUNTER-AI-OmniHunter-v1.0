import re

_TR_MAP = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")

COLOR_WORDS = {
    "siyah", "beyaz", "mavi", "kirmizi", "turuncu", "mor", "pembe", "yesil", "gri", "lacivert",
    "bej", "kahverengi", "sari", "krem", "antrasit", "bordo", "haki", "gumus", "altin", "fume",
    "black", "white", "blue", "red", "orange", "purple", "pink", "green", "grey", "gray", "navy",
    "multi", "renkli", "petrol", "mint", "lila", "somon", "turkuaz", "ekru",
}
GENDER_WORDS = {"erkek", "kadin", "unisex", "cocuk", "kiz", "bebek", "men", "women", "mens", "womens", "kids", "genc"}
GENERIC_WORDS = {
    "kosu", "ayakkabisi", "ayakkabi", "spor", "sneaker", "yuruyus", "outdoor", "gunluk",
    "antrenman", "bot", "terlik", "sandalet", "shoes", "running", "tenis", "fitness",
    "yol", "kosusu", "yarim", "bilekli", "su", "gecirmez",
}
_SKIP = COLOR_WORDS | GENDER_WORDS | GENERIC_WORDS


def make_family_key(text):
    """Urun adindan renk/cinsiyet/genel kelimeleri cikarip aile anahtari uretir.
    GTS / Gore-Tex / Max gibi versiyon belirtecleri KORUNUR (ayri aile sayilir)."""
    if not text:
        return None
    t = str(text).translate(_TR_MAP).lower()
    tokens = re.findall(r"[a-z0-9.]+", t)
    keep = [tok for tok in tokens if tok not in _SKIP]
    key = " ".join(keep[:6]).strip()
    return key or None
