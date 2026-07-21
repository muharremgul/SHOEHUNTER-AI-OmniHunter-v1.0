"""Local product-label, shoe-tongue and barcode recognition for Product Radar.

The image is processed in memory and is never persisted.  RapidOCR and ZXing
run on the ShoeHunter server, so this feature does not require a paid OCR API.
"""

from __future__ import annotations

import hashlib
import re
import threading
import unicodedata
from collections.abc import Iterable
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_IMAGE_BYTES = 12 * 1024 * 1024
MAX_IMAGE_PIXELS = 32_000_000
MAX_IMAGE_EDGE = 2600
SUPPORTED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}

Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


class LabelScanError(ValueError):
    """A safe, user-facing label scan validation error."""


_ocr_engine = None
_ocr_init_lock = threading.Lock()
_ocr_run_lock = threading.Lock()


BRAND_ALIASES = (
    ("under armour", "Under Armour"),
    ("underarmour", "Under Armour"),
    ("adidas", "Adidas"),
    ("adizero", "Adidas"),
    ("nike", "Nike"),
    ("nordmende", "Nordmende"),
    ("hisense", "Hisense"),
    ("new balance", "New Balance"),
    ("newbalance", "New Balance"),
    ("asics", "ASICS"),
    ("puma", "Puma"),
    ("salomon", "Salomon"),
    ("brooks", "Brooks"),
    ("columbia", "Columbia"),
    ("north face", "The North Face"),
    ("jack&jones", "Jack & Jones"),
    ("jack jones", "Jack & Jones"),
    ("jack and jones", "Jack & Jones"),
    ("skechers", "Skechers"),
    ("reebok", "Reebok"),
    ("converse", "Converse"),
    ("vans", "Vans"),
    ("fila", "Fila"),
    ("hoka", "HOKA"),
    ("on running", "On"),
    ("decathlon", "Decathlon"),
    ("kalenji", "Kalenji"),
    ("kipsta", "Kipsta"),
)

PRODUCT_CODE_PATTERNS = (
    re.compile(r"\b[A-Z]{2}\d{4}-\d{3}\b", re.I),  # Nike: HV8113-200
    re.compile(r"\b\d{7}-\d{3}\b"),  # Under Armour: 3027000-107
    re.compile(r"\b[A-Z]{2}\d{4}\b", re.I),  # Adidas: JH6206
    re.compile(r"\b[A-Z]\d{2}[A-Z]{2}\d{4}\b", re.I),  # TV/model codes
    re.compile(r"\b[A-Z]{1,4}\d{2,}[A-Z0-9-]{2,}\b", re.I),
)

CATEGORY_KEYWORDS = {
    "shoes": (
        "ayakkabi", "shoe", "running", "kosu", "trail", "zegama", "sneaker",
        "adizero", "evo sl", "footwear",
    ),
    "pants": ("pantolon", "pants", "trousers", "jean", "tayt", "leggings"),
    "outerwear": (
        "mont", "ceket", "jacket", "raincoat", "yagmurluk", "track top",
        "z.n.e", "z n e", "full zip", " fz",
    ),
    "tops": ("tisort", "t-shirt", "tshirt", "shirt", "sweatshirt", "hoodie", "ust giyim"),
    "kids": ("cocuk", "kids", "junior", "infant"),
}

NOISE_TERMS = (
    "made in", "fabrique", "fabricado", "hecho en", "adidas.com", "nike.com",
    "product warranty", "patents", "po ", "ean", "upc", "assm", "copyright",
    "fiyat gecerlilik", "yerli uretim", "aldin aldin", "usa", "cdn", "eur",
    " uk", " cm", " chn", "br ", "blanc", "white", "black/black",
)


def _ascii(value: str) -> str:
    value = str(value or "").replace("İ", "I").replace("ı", "i")
    return "".join(
        char for char in unicodedata.normalize("NFKD", value) if not unicodedata.combining(char)
    ).lower()


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip(" |:;,_")


def _get_ocr_engine():
    global _ocr_engine
    if _ocr_engine is None:
        with _ocr_init_lock:
            if _ocr_engine is None:
                try:
                    from rapidocr import RapidOCR
                except ImportError as exc:  # pragma: no cover - deployment guard
                    raise LabelScanError("Yerel OCR motoru kurulu degil") from exc
                _ocr_engine = RapidOCR()
    return _ocr_engine


def _load_image(data: bytes, content_type: str | None = None) -> Image.Image:
    if not data:
        raise LabelScanError("Bos fotograf gonderilemez")
    if len(data) > MAX_IMAGE_BYTES:
        raise LabelScanError("Fotograf en fazla 12 MB olabilir")
    if content_type and content_type.lower() not in SUPPORTED_CONTENT_TYPES:
        raise LabelScanError("Yalnizca JPG, PNG veya WebP fotograf kullanin")
    try:
        with Image.open(BytesIO(data)) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise LabelScanError("Gecerli bir urun fotografi okunamadi") from exc
    if image.width * image.height > MAX_IMAGE_PIXELS:
        raise LabelScanError("Fotografin cozunurlugu cok yuksek")
    if max(image.size) > MAX_IMAGE_EDGE:
        image.thumbnail((MAX_IMAGE_EDGE, MAX_IMAGE_EDGE), Image.Resampling.LANCZOS)
    return image


def _read_barcodes(image: Image.Image) -> list[dict]:
    try:
        import zxingcpp
    except ImportError as exc:  # pragma: no cover - deployment guard
        raise LabelScanError("Yerel barkod motoru kurulu degil") from exc
    found = []
    seen = set()
    for result in zxingcpp.read_barcodes(image, try_rotate=True, try_downscale=True, try_invert=True):
        value = _clean_text(result.text)
        if not value or value in seen:
            continue
        seen.add(value)
        found.append({"value": value, "format": str(result.format)})
    return found


def _ocr_once(image: Image.Image) -> list[dict]:
    import numpy as np

    engine = _get_ocr_engine()
    with _ocr_run_lock:
        output = engine(np.asarray(image))
    texts = getattr(output, "txts", None)
    scores = getattr(output, "scores", None)
    boxes = getattr(output, "boxes", None)
    texts = texts if texts is not None else ()
    scores = scores if scores is not None else ()
    boxes = boxes if boxes is not None else ()
    rows = []
    for index, text in enumerate(texts):
        clean = _clean_text(text)
        if not clean:
            continue
        box = boxes[index].tolist() if index < len(boxes) else None
        rows.append(
            {
                "text": clean,
                "confidence": round(float(scores[index]) if index < len(scores) else 0.0, 4),
                "box": box,
            }
        )
    return rows


def _text_quality(rows: Iterable[dict]) -> float:
    score = 0.0
    joined = " ".join(row["text"] for row in rows)
    folded = _ascii(joined)
    for row in rows:
        alpha_num = sum(char.isalnum() for char in row["text"])
        score += min(alpha_num, 24) * float(row.get("confidence") or 0)
    if _find_brand(folded):
        score += 60
    if _find_product_codes(joined):
        score += 80
    return score


def _read_text(image: Image.Image) -> tuple[list[dict], int]:
    original = _ocr_once(image)
    best_rows = original
    best_angle = 0
    best_quality = _text_quality(original)
    joined = " ".join(row["text"] for row in original)
    strong = bool(_find_product_codes(joined)) and len(original) >= 4
    if strong:
        return best_rows, best_angle

    # Labels are frequently photographed sideways or fully upside down in stores.
    # Keep the original pass first (the common/fast path), then try every remaining
    # quarter turn when that pass did not produce strong identity evidence.
    for angle in (90, 180, 270):
        rows = _ocr_once(image.rotate(angle, expand=True))
        quality = _text_quality(rows)
        if quality > best_quality:
            best_rows, best_angle, best_quality = rows, angle, quality
    return best_rows, best_angle


def _normalize_ocr_geometry(
    rows: list[dict],
    rotation: int,
    original_width: int,
    original_height: int,
) -> list[dict]:
    """Map OCR polygons back to the EXIF-normalized source image."""

    width = max(float(original_width), 1.0)
    height = max(float(original_height), 1.0)

    def source_point(x: float, y: float) -> tuple[float, float]:
        if rotation == 90:
            return width - y, x
        if rotation == 180:
            return width - x, height - y
        if rotation == 270:
            return y, height - x
        return x, y

    normalized_rows = []
    for row in rows:
        mapped = dict(row)
        polygon = row.get("box")
        if not isinstance(polygon, (list, tuple)) or len(polygon) < 3:
            normalized_rows.append(mapped)
            continue
        normalized = []
        for point in polygon:
            if not isinstance(point, (list, tuple)) or len(point) < 2:
                continue
            source_x, source_y = source_point(float(point[0]), float(point[1]))
            normalized.append(
                [
                    round(min(1.0, max(0.0, source_x / width)), 6),
                    round(min(1.0, max(0.0, source_y / height)), 6),
                ]
            )
        if len(normalized) >= 3:
            mapped["polygon_norm"] = normalized
        normalized_rows.append(mapped)
    return normalized_rows


def _find_brand(folded_text: str) -> str | None:
    for alias, canonical in BRAND_ALIASES:
        if alias in folded_text:
            return canonical
    return None


def _find_product_codes(text: str) -> list[str]:
    values = []
    seen = set()
    upper = text.upper().replace("–", "-").replace("—", "-")
    for pattern in PRODUCT_CODE_PATTERNS:
        for match in pattern.findall(upper):
            value = _clean_text(match).upper()
            if value in seen or any(value in existing for existing in seen) or _looks_like_date_or_metadata(value):
                continue
            seen.add(value)
            values.append(value)
    return values


def _brand_product_codes(brand: str | None, values: list[str]) -> list[str]:
    def most_specific_first(codes: list[str]) -> list[str]:
        return sorted(codes, key=lambda value: (len(value), "-" in value), reverse=True)

    if brand == "Adidas":
        exact = [value for value in values if re.fullmatch(r"[A-Z]{2}\d{4}", value)]
        return most_specific_first(exact or values)
    if brand == "Nike":
        exact = [value for value in values if re.fullmatch(r"[A-Z]{2}\d{4}-\d{3}", value)]
        return most_specific_first(exact or values)
    if brand == "Under Armour":
        exact = [value for value in values if re.fullmatch(r"\d{7}-\d{3}", value)]
        return most_specific_first(exact or values)
    return most_specific_first(values)


def _looks_like_date_or_metadata(value: str) -> bool:
    compact = re.sub(r"\D", "", value)
    if value.startswith(("PO", "EAN", "UPC", "ART")):
        return True
    return len(compact) >= 12


def _gtin_valid(value: str) -> bool:
    if not value.isdigit() or len(value) not in {8, 12, 13, 14}:
        return False
    body = [int(char) for char in value[:-1]]
    total = sum(digit * (3 if (len(body) - index) % 2 else 1) for index, digit in enumerate(body))
    return (10 - total % 10) % 10 == int(value[-1])


def _ocr_gtins(lines: list[str]) -> list[str]:
    digit_parts = [
        re.sub(r"\D", "", line)
        if re.fullmatch(r"[\d\s]+", line.strip())
        else ""
        for line in lines
    ]
    values = []
    seen = set()
    for index in range(len(digit_parts)):
        combined = ""
        for part in digit_parts[index : index + 4]:
            if not part or len(part) > 14:
                break
            combined += part
            if len(combined) in {8, 12, 13, 14} and _gtin_valid(combined) and combined not in seen:
                seen.add(combined)
                values.append(combined)
            if len(combined) >= 14:
                break
    return values


def _parse_price(value: str) -> float | None:
    compact = re.sub(r"\s+", "", value).replace("₺", "TL").upper()
    match = re.search(
        r"(\d{1,3}(?:[.]\d{3})+(?:,\d{1,2})?|\d{3,6}(?:,\d{1,2})?)\s*(?:TL|[^\d\s]{0,2}L)\b",
        compact,
    )
    if not match:
        return None
    number = match.group(1)
    if "." in number and re.search(r"\.\d{3}(?:\.|,|$)", number):
        number = number.replace(".", "")
    number = number.replace(",", ".")
    try:
        parsed = float(number)
    except ValueError:
        return None
    return parsed if 10 <= parsed <= 10_000_000 else None


def _find_prices(lines: list[str]) -> list[float]:
    prices = []
    for index, line in enumerate(lines):
        candidates = [line]
        if index + 1 < len(lines):
            candidates.append(f"{line} {lines[index + 1]}")
        for candidate in candidates:
            price = _parse_price(candidate)
            if price is not None and price not in prices:
                prices.append(price)
    return prices


def _normalize_size(value: str) -> str:
    value = value.strip().upper().replace(",", ".")
    value = re.sub(r"\s+", " ", value)
    return value[:-2] if value.endswith(".0") else value


def _find_sizes(lines: list[str], category: str) -> list[str]:
    text = "\n".join(lines).upper().replace(",", ".")
    values = []

    for match in re.finditer(r"\b(?:EU|EUR|FR)\s*[:/-]?\s*(3[4-9]|4\d)(?:[.]\d+|\s+1/3|\s+2/3)?\b", text):
        values.append(_normalize_size(match.group(0).split(maxsplit=1)[-1]))

    # Some Adidas box labels use F (France/EU) next to the EU size.
    for index, line in enumerate(lines):
        clean = line.strip().upper()
        match = re.fullmatch(r"(?:F|FR)\s*(3[4-9]|4\d)(?:[.]\d+)?", clean)
        if match:
            values.append(_normalize_size(match.group(1)))
        if clean in {"EU", "EUR", "FR", "F"}:
            nearby = list(reversed(lines[max(0, index - 3) : index])) + lines[index + 1 : index + 4]
            for nearby_line in nearby:
                number = re.fullmatch(r"(3[4-9]|4\d)(?:[.]\d+)?", nearby_line.strip())
                if number:
                    values.append(_normalize_size(number.group(0)))
                    break

    clothing = r"(?:4XL|3XL|2XL|XXXL|XXL|XL|L|M|S|XS|XXS|\d{3})"
    for match in re.finditer(rf"\b(?:USA|EU|D|F)\s*[:/-]?\s*({clothing})\b", text):
        size = _normalize_size(match.group(1))
        if category != "shoes" or not size.isdigit():
            values.append(size)
    if category in {"tops", "pants", "outerwear", "kids"} and not values:
        for line in lines:
            if re.fullmatch(clothing, line.strip().upper()):
                values.append(_normalize_size(line))

    return list(dict.fromkeys(values))[:6]


def _infer_category(text: str, product_codes: list[str]) -> str:
    folded = f" {_ascii(text)} "
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in folded for keyword in keywords):
            return category
    if any(re.fullmatch(r"[A-Z]{2}\d{4}-\d{3}|\d{7}-\d{3}", code) for code in product_codes):
        return "shoes"
    return "other"


def _descriptive_lines(lines: list[str], product_codes: list[str]) -> list[str]:
    codes = {code.upper() for code in product_codes}
    selected = []
    for line in lines:
        folded = _ascii(line)
        upper = line.upper()
        if upper in codes or any(term in folded for term in NOISE_TERMS):
            continue
        if _parse_price(line) is not None or _gtin_valid(re.sub(r"\D", "", line)):
            continue
        if len(line) < 3 or not any(char.isalpha() for char in line):
            continue
        if "�" in line or any(not (char.isalnum() or char in " .-/&+\"") for char in line):
            continue
        if sum(char.isdigit() for char in line) > len(line) * 0.45:
            continue
        if _find_brand(folded) and len(folded.split()) <= 2:
            continue
        if re.fullmatch(r"[A-Z]{1,3}", upper) or re.fullmatch(r"[A-Z/ ]+\d{1,3}", upper):
            continue
        if folded not in {_ascii(item) for item in selected}:
            selected.append(line)
    return selected[:8]


def _build_query(brand: str | None, codes: list[str], descriptive: list[str]) -> str:
    keywords = (
        "adizero", "evo", "zegama", "trail", "z.n.e", "z n e", "track top",
        "bisiklet", "jant", "tv", "qled", "ayakkabi", "running",
    )
    useful = [line for line in descriptive if any(word in _ascii(line) for word in keywords)]
    if not useful:
        useful = descriptive[:2]
    parts = []
    if brand:
        parts.append(brand)
    parts.extend(useful[:3])
    if codes and codes[0].lower() not in " ".join(parts).lower():
        parts.append(codes[0])
    query = _clean_text(" ".join(parts))
    return query[:160]


def parse_label_text(text_blocks: list[dict], barcodes: list[dict] | None = None) -> dict:
    """Convert OCR/barcode evidence into an editable Product Radar suggestion."""
    lines = [_clean_text(row.get("text")) for row in text_blocks if _clean_text(row.get("text"))]
    raw_text = "\n".join(lines)
    folded = _ascii(raw_text)
    brand = _find_brand(folded)
    joined_fragments = " ".join(
        f"{line}{lines[index + 1].split()[0]}"
        for index, line in enumerate(lines[:-1])
        if line.endswith("-") and lines[index + 1].split()
    )
    product_codes = _brand_product_codes(brand, _find_product_codes(f"{raw_text}\n{joined_fragments}"))
    barcode_rows = list(barcodes or [])
    barcode_values = [row["value"] for row in barcode_rows if row.get("value")]
    for value in _ocr_gtins(lines):
        if value not in barcode_values:
            barcode_values.append(value)
            barcode_rows.append({"value": value, "format": "OCR-GTIN"})
    category = _infer_category(raw_text, product_codes)
    sizes = _find_sizes(lines, category)
    prices = _find_prices(lines)
    descriptive = _descriptive_lines(lines, product_codes)
    query = _build_query(brand, product_codes, descriptive)

    evidence_count = sum(bool(value) for value in (brand, product_codes, barcode_values, query))
    mean_ocr = (
        sum(float(row.get("confidence") or 0) for row in text_blocks) / len(text_blocks)
        if text_blocks else 0
    )
    confidence = min(0.99, 0.28 + evidence_count * 0.14 + mean_ocr * 0.28)
    warnings = []
    if not product_codes and not barcode_values:
        warnings.append("Urun kodu veya barkod bulunamadi; urun adini mutlaka kontrol edin.")
    if not query:
        warnings.append("Radar arama metni otomatik olusturulamadi.")
    elif confidence < 0.68:
        warnings.append("Okuma guveni dusuk; Radar'a eklemeden once alanlari duzeltin.")

    identifiers = {}
    if product_codes:
        identifiers["product_code"] = product_codes[0]
    decoded_gtins = [
        row["value"]
        for row in barcode_rows
        if row.get("format") != "OCR-GTIN" and _gtin_valid(str(row.get("value") or ""))
    ]
    decoded_qr = [
        row["value"]
        for row in barcode_rows
        if "QR" in str(row.get("format") or "").upper()
    ]
    if decoded_gtins:
        identifiers["barcode"] = decoded_gtins[0]
    if decoded_qr:
        identifiers["qr"] = decoded_qr[0]
    # B5: Auto-detect GS1 Digital Link from QR codes
    if decoded_qr:
        try:
            from commerce_intelligence import parse_gs1_digital_link
            gs1 = parse_gs1_digital_link(decoded_qr[0])
            if gs1.get("is_gs1_digital_link"):
                gs1_ids = gs1.get("identifiers") or {}
                if gs1_ids.get("gtin") and "barcode" not in identifiers:
                    identifiers["barcode"] = gs1_ids["gtin"]
                    identifiers["gtin"] = gs1_ids["gtin"]
                if gs1_ids.get("batch_lot"):
                    identifiers["batch_lot"] = gs1_ids["batch_lot"]
                if gs1_ids.get("serial"):
                    identifiers["serial"] = gs1_ids["serial"]
        except Exception:
            pass  # GS1 parsing is best-effort
    # Carry style/model codes as separate identifiers for the search plan
    if len(product_codes) > 1:
        identifiers["style_code"] = product_codes[1]

    return {
        "brand": brand,
        "product_codes": product_codes,
        "barcodes": barcode_rows,
        "sizes": sizes,
        "prices": prices,
        "category": category,
        "descriptive_lines": descriptive,
        "raw_text": raw_text[:6000],
        "confidence": round(confidence, 3),
        "warnings": warnings,
        "suggested_watch": {
            "raw_query": query,
            "brand": brand,
            "model": product_codes[0] if product_codes else None,
            "category": category,
            "desired_sizes": sizes,
            "target_price": prices[-1] if prices else None,
            "input_origin": "label_scan",
            "source_identifiers": identifiers,
        },
    }


def scan_product_label(data: bytes, content_type: str | None = None) -> dict:
    """Read an uploaded image and return a reviewable Product Radar suggestion."""
    image = _load_image(data, content_type)
    barcodes = _read_barcodes(image)
    text_blocks, rotation = _read_text(image)
    text_blocks = _normalize_ocr_geometry(text_blocks, rotation, image.width, image.height)
    if not text_blocks and not barcodes:
        raise LabelScanError("Fotografta okunabilir yazi, barkod veya QR kod bulunamadi")
    parsed = parse_label_text(text_blocks, barcodes)
    parsed["image"] = {"width": image.width, "height": image.height, "ocr_rotation": rotation}
    parsed["text_blocks"] = text_blocks[:120]
    parsed["processing"] = {
        "mode": "local",
        "image_stored": False,
        "paid_api_used": False,
        "content_sha256": hashlib.sha256(bytes(data)).hexdigest(),
    }
    return parsed
