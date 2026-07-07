# v0.6'da aynı ürünleri mağazalar arasında eşleştirme burada olacak.
def similarity_score(a: str, b: str) -> float:
    a = a.lower().strip()
    b = b.lower().strip()
    if a == b:
        return 1.0
    if a in b or b in a:
        return 0.7
    return 0.0
