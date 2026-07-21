import re
import unicodedata
from dataclasses import asdict, dataclass, field
from urllib.parse import parse_qsl, urlencode, urlparse

from rapidfuzz import fuzz

COLOR_TOKENS = {
    "siyah",
    "beyaz",
    "gri",
    "kirmizi",
    "mavi",
    "lacivert",
    "yesil",
    "sari",
    "turuncu",
    "pembe",
    "mor",
    "bej",
    "kahverengi",
    "black",
    "white",
    "grey",
    "gray",
    "red",
    "blue",
    "green",
    "yellow",
    "orange",
    "pink",
    "purple",
}
NOISE_TOKENS = {
    "ayakkabi",
    "ayakkabisi",
    "spor",
    "kosu",
    "urun",
    "model",
    "yeni",
    "sezon",
    "shoe",
    "shoes",
    "sneaker",
    "sneakers",
}
PROTECTED_TOKENS = {
    "gts",
    "gtx",
    "goretex",
    "max",
    "wide",
    "xwide",
    "premium",
    "woven",
    "trail",
    "road",
    "waterproof",
    "stealthfit",
}
GENDER_MAP = {
    "erkek": "men",
    "men": "men",
    "male": "men",
    "m": "men",
    "kadin": "women",
    "women": "women",
    "female": "women",
    "w": "women",
    "cocuk": "kids",
    "kids": "kids",
    "junior": "kids",
    "gs": "kids",
    "unisex": "unisex",
}
WIDTH_MAP = {
    "wide": "wide",
    "genis": "wide",
    "2e": "wide",
    "xwide": "extra_wide",
    "extra-wide": "extra_wide",
    "4e": "extra_wide",
    "standard": "standard",
    "normal": "standard",
}
STYLE_CODE_RE = re.compile(r"\b(?:[A-Z]{1,4}\d{3,7}(?:-\d{2,4})?|\d{5,8}[A-Z]{0,2})\b", re.I)
GTIN_RE = re.compile(r"\b(?:\d{8}|\d{12}|\d{13}|\d{14})\b")
GENERATION_RE = re.compile(r"^(?:v\d{1,2}|\d+\.\d+|\d{1,3})$", re.I)


def ascii_text(value):
    text = str(value or "").replace("\u0131", "i").replace("\u0130", "I")
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def tokenize(value):
    return re.findall(r"[a-z0-9]+(?:\.[0-9]+)?", ascii_text(value).lower())


def normalize_size(value):
    text = ascii_text(value).upper().strip().replace(",", ".")
    text = text.replace("\u2153", " 1/3").replace("\u2154", " 2/3")
    text = re.sub(r"\b(?:EU|EUR|NUMARA|BEDEN)\b", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    match = re.fullmatch(r"(\d{1,3})\s+([12])/3", text)
    if match:
        return f"{int(match.group(1))} {match.group(2)}/3"
    if re.fullmatch(r"\d{1,3}\.0", text):
        return text[:-2]
    return text


@dataclass
class ProductIdentity:
    raw_title: str
    normalized_title: str
    brand: str | None = None
    model_tokens: list[str] = field(default_factory=list)
    model_codes: list[str] = field(default_factory=list)
    gtins: list[str] = field(default_factory=list)
    generation: str | None = None
    gender: str | None = None
    width: str | None = None
    qualifiers: list[str] = field(default_factory=list)
    color_tokens: list[str] = field(default_factory=list)
    category: str | None = None

    def to_dict(self):
        return asdict(self)

    @property
    def canonical_key(self):
        parts = self.model_codes or self.model_tokens
        suffix = [self.generation, self.gender, self.width] + self.qualifiers
        return "|".join([p for p in parts + suffix if p])

    @property
    def family_key(self):
        parts = self.model_tokens + [self.generation, self.gender, self.width] + self.qualifiers
        return "-".join(dict.fromkeys(p for p in parts if p))[:160]


def identity_from_title(title, brand=None, url=None, category=None):
    tokens = tokenize(title)
    style_codes = [m.group(0).upper() for m in STYLE_CODE_RE.finditer(str(title or ""))]
    gtins = [m.group(0) for m in GTIN_RE.finditer(str(title or ""))]
    if url and "/dp/" in url:
        asin_match = re.search(r"/dp/([A-Z0-9]{10})", url, re.I)
        if asin_match:
            style_codes.append(asin_match.group(1).upper())

    gender = next((GENDER_MAP[token] for token in tokens if token in GENDER_MAP), None)
    width = next((WIDTH_MAP[token] for token in tokens if token in WIDTH_MAP), None)
    qualifiers = sorted({token for token in tokens if token in PROTECTED_TOKENS})
    colors = sorted({token for token in tokens if token in COLOR_TOKENS})
    generation = next((token for token in reversed(tokens) if GENERATION_RE.match(token)), None)
    brand_tokens = set(tokenize(brand))
    excluded = set(COLOR_TOKENS) | set(NOISE_TOKENS) | set(GENDER_MAP) | set(WIDTH_MAP)
    excluded |= {code.lower() for code in style_codes} | set(gtins) | brand_tokens
    model_tokens = [token for token in tokens if token not in excluded]
    model_tokens = list(dict.fromkeys(model_tokens))[:12]
    return ProductIdentity(
        raw_title=str(title or "").strip(),
        normalized_title=" ".join(tokens),
        brand=ascii_text(brand).lower().strip() or None,
        model_tokens=model_tokens,
        model_codes=sorted(set(style_codes)),
        gtins=sorted(set(gtins)),
        generation=generation,
        gender=gender,
        width=width,
        qualifiers=qualifiers,
        color_tokens=colors,
        category=category,
    )


def match_identities(expected, candidate, required_tokens=None, excluded_tokens=None):
    evidence = []
    required = set(tokenize(" ".join(required_tokens or [])))
    excluded = set(tokenize(" ".join(excluded_tokens or [])))
    candidate_tokens = set(tokenize(candidate.raw_title))
    if required and not required.issubset(candidate_tokens):
        return {"confidence": 0.0, "decision": "rejected", "evidence": ["required_token_missing"]}
    if excluded & candidate_tokens:
        return {"confidence": 0.0, "decision": "rejected", "evidence": ["excluded_token_present"]}

    exact_codes = set(expected.model_codes + expected.gtins) & set(candidate.model_codes + candidate.gtins)
    if exact_codes:
        confidence = 0.99
        evidence.append("exact_identifier:" + ",".join(sorted(exact_codes)))
    else:
        confidence = fuzz.token_set_ratio(expected.normalized_title, candidate.normalized_title) / 100
        evidence.append(f"title_similarity:{confidence:.2f}")

    for field_name in ("gender", "width", "generation"):
        left = getattr(expected, field_name)
        right = getattr(candidate, field_name)
        if left and right and left != right:
            return {
                "confidence": min(confidence, 0.35),
                "decision": "rejected",
                "evidence": evidence + [f"{field_name}_mismatch"],
            }

    expected_protected = set(expected.qualifiers)
    candidate_protected = set(candidate.qualifiers)
    if expected_protected != candidate_protected:
        return {
            "confidence": min(confidence, 0.55),
            "decision": "rejected",
            "evidence": evidence + ["protected_model_token_mismatch"],
        }

    if confidence >= 0.92:
        decision = "auto"
    elif confidence >= 0.75:
        decision = "review"
    else:
        decision = "rejected"
    return {"confidence": round(confidence, 4), "decision": decision, "evidence": evidence}


def canonicalize_product_url(url):
    parsed = urlparse(str(url or "").strip())
    if not parsed.scheme or not parsed.netloc:
        return str(url or "").strip()
    identity_query_keys = {"mc", "pid", "productid", "sku", "variant", "variantid"}
    identity_query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=False)
        if key.lower() in identity_query_keys
    ]
    identity_query.sort(key=lambda item: (item[0].lower(), item[1]))
    return parsed._replace(query=urlencode(identity_query), fragment="").geturl().rstrip("/")
