"""Deterministic, identifier-first search plans for Product Radar watches.

The label scanner already stores identifiers separately from the human-readable
query.  This module turns all of that evidence into a bounded search plan so a
barcode or style code is not silently ignored by store discovery.
"""

import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import Any

from product_identity import ascii_text

MAX_SEARCH_QUERIES = 8
_SPACE_RE = re.compile(r"\s+")
_BARCODE_KEYS = ("barcode", "gtin", "ean", "upc")
_PRODUCT_CODE_KEYS = ("product_code", "model_code", "style_code", "sku")
_ALIAS_KEYS = ("enriched_aliases", "search_aliases", "aliases", "identity_aliases")


@dataclass(frozen=True)
class SearchQuery:
    query: str
    kind: str
    exact_identifier: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _clean(value: Any) -> str:
    return _SPACE_RE.sub(" ", str(value or "").strip())


def _dedupe_key(value: str) -> str:
    return _clean(ascii_text(value)).casefold()


def _iter_values(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        cleaned = _clean(value)
        if cleaned:
            yield cleaned
        return
    if isinstance(value, dict):
        for item in value.values():
            yield from _iter_values(item)
        return
    if isinstance(value, (list, tuple, set)):
        for item in value:
            yield from _iter_values(item)


def _identifier_values(source_identifiers: dict[str, Any], keys: tuple[str, ...]) -> list[str]:
    wanted = set(keys)
    output = []
    for key, value in source_identifiers.items():
        if str(key).strip().casefold() not in wanted:
            continue
        output.extend(_iter_values(value))
    return output


def _alias_values(watch: dict[str, Any]) -> list[str]:
    output = []
    for key in _ALIAS_KEYS:
        output.extend(_iter_values(watch.get(key)))
    identifiers = watch.get("source_identifiers") or {}
    for key in _ALIAS_KEYS:
        output.extend(_iter_values(identifiers.get(key)))
    return output


def build_search_plan(watch: dict[str, Any], limit: int = MAX_SEARCH_QUERIES) -> list[SearchQuery]:
    """Build a stable, bounded and case-insensitively deduplicated query plan.

    Exact style/SKU identifiers are intentionally first, followed by barcodes.
    Contextual and enriched names are only used after those high-precision
    lanes.  This makes a label such as ``TRAIL RUNNING JR5220`` search ``JR5220``
    instead of relying only on generic OCR words.
    """

    source_identifiers = watch.get("source_identifiers") or {}
    product_codes = _identifier_values(source_identifiers, _PRODUCT_CODE_KEYS)
    barcodes = _identifier_values(source_identifiers, _BARCODE_KEYS)
    identity = watch.get("identity") if isinstance(watch.get("identity"), dict) else {}
    product_codes.extend(_iter_values(watch.get("known_model_codes")))
    product_codes.extend(_iter_values(identity.get("model_codes")))
    barcodes.extend(_iter_values(identity.get("gtins")))
    brand = _clean(watch.get("brand"))
    model = _clean(watch.get("model"))
    raw_query = _clean(watch.get("raw_query") or watch.get("query"))
    aliases = _alias_values(watch)

    candidates: list[SearchQuery] = []
    candidates.extend(SearchQuery(value, "product_code", True) for value in product_codes)
    candidates.extend(SearchQuery(value, "barcode", True) for value in barcodes)
    if brand:
        candidates.extend(SearchQuery(f"{brand} {value}", "brand_product_code") for value in product_codes)
    candidates.extend(SearchQuery(value, "enriched_alias") for value in aliases)
    if raw_query:
        candidates.append(SearchQuery(raw_query, "raw_query"))
    if brand and model:
        candidates.append(SearchQuery(f"{brand} {model}", "brand_model"))
    elif model:
        candidates.append(SearchQuery(model, "model"))

    output = []
    seen = set()
    bounded_limit = max(1, min(int(limit or MAX_SEARCH_QUERIES), MAX_SEARCH_QUERIES))
    for item in candidates:
        query = _clean(item.query)
        key = _dedupe_key(query)
        if not key or key in seen:
            continue
        seen.add(key)
        output.append(SearchQuery(query, item.kind, item.exact_identifier))
        if len(output) >= bounded_limit:
            break
    return output


def plan_as_dicts(plan: Iterable[SearchQuery]) -> list[dict[str, Any]]:
    return [item.to_dict() for item in plan]
