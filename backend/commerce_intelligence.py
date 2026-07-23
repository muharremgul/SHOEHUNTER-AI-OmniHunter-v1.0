"""Transparent commerce facts derived from already collected listing evidence.

This module deliberately does not guess missing prices or seller facts.  Every
derived value carries a completeness flag and short evidence/risk list so the UI
can distinguish a verified comparison from a merely cheap-looking offer.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlencode, urlparse

_PRICE_RE = re.compile(r"(?<!\d)(\d{1,3}(?:[.\s]\d{3})*(?:,\d{1,2})|\d+(?:[.,]\d{1,2})?)(?!\d)")
_GS1_AI_LENGTHS = {"01": 14, "11": 6, "15": 6, "16": 6, "17": 6}
_GS1_NAMES = {
    "01": "gtin",
    "10": "batch_lot",
    "11": "production_date_yymmdd",
    "15": "best_before_yymmdd",
    "16": "sell_by_yymmdd",
    "17": "expiry_yymmdd",
    "21": "serial",
    "22": "consumer_product_variant",
}
_GS1_PATH_QUALIFIERS = ("22", "10", "21")
_GS1_QUERY_ATTRIBUTES = ("11", "15", "16", "17")


def _number(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _parse_turkish_amount(text: str | None) -> float | None:
    """Read a TL amount without interpreting dates or delivery-day counts."""

    if not text:
        return None
    lowered = str(text).casefold()
    if any(token in lowered for token in ("ücretsiz", "ucretsiz", "bedava", "kargo bedava")):
        return 0.0
    if not any(token in lowered for token in ("tl", "₺", "kargo", "teslimat", "shipping")):
        return None
    for match in _PRICE_RE.finditer(lowered):
        raw = match.group(1).replace(" ", "")
        if "," in raw:
            raw = raw.replace(".", "").replace(",", ".")
        elif raw.count(".") > 1 or (raw.count(".") == 1 and len(raw.rsplit(".", 1)[1]) == 3):
            raw = raw.replace(".", "")
        amount = _number(raw)
        if amount is not None:
            return amount
    return None


def compute_total_cost(listing: dict[str, Any]) -> dict[str, Any]:
    """Compute payable cost only from explicit, auditable offer evidence."""

    shelf = _number(listing.get("last_price"))
    cart = _number(listing.get("last_cart_price"))
    cart_conditions = [str(item) for item in (listing.get("last_cart_price_conditions") or []) if item]
    price = shelf
    price_kind = "shelf"
    evidence: list[str] = []
    conditions: list[str] = []

    if cart is not None and (shelf is None or cart < shelf):
        if cart_conditions:
            conditions.extend(cart_conditions)
            evidence.append("Koşullu sepet fiyatı toplam maliyete uygulanmadı")
        else:
            price = cart
            price_kind = "cart"
            evidence.append("Koşulsuz doğrulanmış sepet fiyatı kullanıldı")
    if price is None:
        return {
            "amount": None,
            "currency": "TRY",
            "complete": False,
            "price_kind": None,
            "shipping_amount": None,
            "conditions": conditions,
            "evidence": evidence,
            "missing": ["product_price"],
        }

    shipping_text = listing.get("shipping")
    shipping = _parse_turkish_amount(shipping_text)
    missing: list[str] = []
    if shipping is None:
        missing.append("shipping_cost")
        amount = price
        evidence.append("Kargo tutarı bilinmiyor; gösterilen değer ürün fiyatıdır")
    else:
        amount = price + shipping
        evidence.append("Kargo tutarı açık metinden eklendi")

    for campaign in listing.get("campaigns") or []:
        if not isinstance(campaign, dict):
            continue
        if campaign.get("conditional") or campaign.get("type") in {"coupon", "membership", "bank"}:
            label = str(campaign.get("label") or campaign.get("type") or "kampanya")
            if label not in conditions:
                conditions.append(label)

    return {
        "amount": round(amount, 2),
        "currency": "TRY",
        "complete": not missing and not conditions,
        "price_kind": price_kind,
        "shipping_amount": shipping,
        "conditions": conditions,
        "evidence": evidence,
        "missing": missing,
    }


def compute_seller_trust(listing: dict[str, Any]) -> dict[str, Any]:
    """Return an explainable trust indicator, never a claim of seller safety."""

    marketplace_slugs = {"amazon", "hepsiburada", "n11", "trendyol", "pazarama"}
    store_slug = str(listing.get("store_slug") or "").casefold()
    marketplace = store_slug in marketplace_slugs
    official = listing.get("official_seller") is True
    seller = str(listing.get("seller") or "").strip()
    rating = _number(listing.get("seller_rating"))
    evidence: list[str] = []
    risks: list[str] = []

    if official:
        score = 90
        evidence.append("Sayfada resmî satıcı işareti bulundu")
    elif marketplace:
        score = 45
        risks.append("Marketplace teklifi; satıcı mağazadan bağımsız değerlendirilmelidir")
    else:
        score = 72
        evidence.append("Doğrudan mağaza alan adındaki teklif")

    if seller:
        score += 3
        evidence.append(f"Satıcı adı mevcut: {seller}")
    elif marketplace:
        score -= 15
        risks.append("Satıcı adı okunamadı")

    if rating is not None:
        normalized = rating * 10 if rating <= 10 else rating
        normalized = min(100.0, max(0.0, normalized))
        score += round((normalized - 70) * 0.2)
        evidence.append(f"Sayfadaki satıcı puanı: {rating:g}")
    elif marketplace:
        score -= 8
        risks.append("Satıcı puanı bilinmiyor")

    if listing.get("last_stock_status") in {"blocked", "error", "unknown"}:
        score -= 8
        risks.append("Teklifin güncelliği tam doğrulanamadı")
    if not listing.get("last_checked_at"):
        score -= 8
        risks.append("Başarılı kontrol zamanı yok")

    score = max(0, min(100, int(score)))
    band = "high" if score >= 80 else "medium" if score >= 60 else "low"
    return {
        "score": score,
        "band": band,
        "marketplace": marketplace,
        "seller": seller or None,
        "official_seller": official,
        "evidence": evidence,
        "risks": risks,
        "disclaimer": "Gösterge, mevcut sayfa kanıtlarını özetler; satıcı garantisi değildir.",
    }


def enrich_listing_commerce(listing: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(listing)
    enriched["total_cost"] = compute_total_cost(enriched)
    enriched["seller_trust"] = compute_seller_trust(enriched)
    return enriched


def _valid_gtin(value: str) -> bool:
    if not value.isdigit() or len(value) not in {8, 12, 13, 14}:
        return False
    digits = [int(char) for char in value]
    payload, check = digits[:-1], digits[-1]
    total = sum(digit * (3 if (len(payload) - index) % 2 else 1) for index, digit in enumerate(payload))
    return (10 - total % 10) % 10 == check


def parse_gs1_digital_link(value: str | None) -> dict[str, Any]:
    """Parse common GS1 Digital Link identifiers without opening the target URL."""

    result: dict[str, Any] = {"is_gs1_digital_link": False, "identifiers": {}, "warnings": []}
    if not value:
        return result
    parsed = urlparse(str(value).strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        result["warnings"].append("Geçerli bir HTTP(S) bağlantısı değil")
        return result

    segments = [unquote(part) for part in parsed.path.split("/") if part]
    identifiers: dict[str, str] = {}
    index = 0
    while index + 1 < len(segments):
        ai = segments[index]
        if ai in _GS1_NAMES:
            identifiers[ai] = segments[index + 1]
            index += 2
        else:
            index += 1
    query = parse_qs(parsed.query, keep_blank_values=False)
    for ai in _GS1_NAMES:
        if ai not in identifiers and query.get(ai):
            identifiers[ai] = query[ai][0]

    if "01" in identifiers:
        gtin = re.sub(r"\D", "", identifiers["01"])
        identifiers["01"] = gtin
        if not _valid_gtin(gtin):
            result["warnings"].append("GTIN kontrol basamağı doğrulanamadı")
    for ai, length in _GS1_AI_LENGTHS.items():
        if ai in identifiers and len(identifiers[ai]) != length:
            result["warnings"].append(f"AI ({ai}) beklenen uzunlukta değil")

    result["is_gs1_digital_link"] = "01" in identifiers
    result["identifiers"] = {
        name: identifiers.get(ai) for ai, name in _GS1_NAMES.items()
    }
    result["identifiers"] = {key: item for key, item in result["identifiers"].items() if item}
    return result


def parse_gs1_element_string(value: str | None) -> dict[str, Any]:
    """Parse human-readable GS1 element strings such as ``(01)...(17)...``.

    The parenthesized form is intentionally required here. Unbracketed scanner
    payloads need the full GS1 AI data table and FNC1 boundary handling and are
    therefore not guessed.
    """

    result: dict[str, Any] = {"is_gs1_element_string": False, "identifiers": {}, "warnings": []}
    text = str(value or "").strip()
    if not text:
        return result
    matches = list(re.finditer(r"\((\d{2,4})\)([^()]*)", text))
    if not matches:
        result["warnings"].append("Parantezli GS1 uygulama tanımlayıcısı bulunamadı")
        return result

    raw: dict[str, str] = {}
    for match in matches:
        ai = match.group(1)
        field = match.group(2).strip().replace("\x1d", "")
        if ai in _GS1_NAMES and field:
            raw[ai] = field
    if "01" in raw:
        raw["01"] = re.sub(r"\D", "", raw["01"])
        if not _valid_gtin(raw["01"]):
            result["warnings"].append("GTIN kontrol basamağı doğrulanamadı")
    for ai, length in _GS1_AI_LENGTHS.items():
        if ai in raw and len(raw[ai]) != length:
            result["warnings"].append(f"AI ({ai}) beklenen uzunlukta değil")
    result["is_gs1_element_string"] = "01" in raw
    result["identifiers"] = {
        name: raw[ai] for ai, name in _GS1_NAMES.items() if raw.get(ai)
    }
    return result


def build_gs1_digital_link(
    identifiers: dict[str, Any],
    *,
    resolver_base: str = "https://id.gs1.org",
) -> str:
    """Build a conservative GS1 Digital Link URI for a GTIN and qualifiers."""

    parsed_base = urlparse(str(resolver_base or "").strip())
    if parsed_base.scheme != "https" or not parsed_base.netloc or parsed_base.query or parsed_base.fragment:
        raise ValueError("resolver_base sorgusuz bir HTTPS adresi olmalı")

    reverse_names = {name: ai for ai, name in _GS1_NAMES.items()}
    raw = {}
    for key, value in (identifiers or {}).items():
        ai = key if key in _GS1_NAMES else reverse_names.get(str(key))
        clean = str(value or "").strip()
        if ai and clean:
            raw[ai] = clean
    gtin = re.sub(r"\D", "", raw.get("01", ""))
    if not _valid_gtin(gtin) or len(gtin) != 14:
        raise ValueError("Geçerli 14 haneli AI (01) GTIN gerekli")

    base_path = parsed_base.path.rstrip("/")
    parts = [base_path.rstrip("/"), "01", quote(gtin, safe="")]
    for ai in _GS1_PATH_QUALIFIERS:
        if raw.get(ai):
            parts.extend((ai, quote(raw[ai], safe="")))
    path = "/".join(part.strip("/") for part in parts if part != "")
    query = urlencode([(ai, raw[ai]) for ai in _GS1_QUERY_ATTRIBUTES if raw.get(ai)])
    return f"{parsed_base.scheme}://{parsed_base.netloc}/{path}" + (f"?{query}" if query else "")


def canonical_product_projection(product: dict[str, Any], listings: list[dict[str, Any]]) -> dict[str, Any]:
    """Expose the current storage model as explicit canonical/variant/identifier roles."""

    identity = product.get("identity") if isinstance(product.get("identity"), dict) else {}
    identifiers: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    def add_identifier(kind: str, value: Any, source: str, verified: bool = False) -> None:
        text = str(value or "").strip()
        key = (kind, text.casefold())
        if not text or key in seen:
            return
        seen.add(key)
        identifiers.append({"type": kind, "value": text, "source": source, "verified": verified})

    add_identifier("gtin", identity.get("gtin"), "product_identity", _valid_gtin(str(identity.get("gtin") or "")))
    add_identifier("mpn", identity.get("model_code") or product.get("model"), "product_identity")
    for listing in listings:
        add_identifier("mpn", listing.get("model_code"), f"listing:{listing.get('store_slug') or listing.get('store')}")
        gs1 = parse_gs1_digital_link(listing.get("url"))
        add_identifier("gtin", (gs1.get("identifiers") or {}).get("gtin"), "gs1_digital_link", True)

    variant_attributes = dict(product.get("attributes") or {})
    for key in ("color", "size", "gender", "age_group"):
        if identity.get(key) and key not in variant_attributes:
            variant_attributes[key] = identity[key]

    return {
        "canonical_product": {
            "id": product.get("id"),
            "canonical_key": product.get("canonical_key"),
            "family_key": product.get("family_key"),
            "brand": product.get("brand") or identity.get("brand"),
            "name": product.get("name"),
            "category": product.get("category"),
        },
        "product_variant": {
            "id": product.get("id"),
            "attributes": variant_attributes,
            "listing_ids": [item.get("id") for item in listings if item.get("id")],
        },
        "product_identifiers": identifiers,
        "identity_version": product.get("identity_version") or 1,
    }
