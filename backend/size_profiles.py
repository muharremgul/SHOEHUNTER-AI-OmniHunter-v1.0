from __future__ import annotations

from collections.abc import Iterable

from product_identity import normalize_size


CATEGORY_CATALOG = {
    "shoes": {"label": "Ayakkabı", "size_label": "Numara", "default_system": "EU"},
    "tops": {"label": "Tişört / Üst giyim", "size_label": "Beden", "default_system": "INT"},
    "pants": {"label": "Pantolon", "size_label": "Beden", "default_system": "WAIST_LENGTH"},
    "outerwear": {"label": "Dış giyim", "size_label": "Beden", "default_system": "INT"},
    "kids": {"label": "Çocuk giyim", "size_label": "Beden", "default_system": "AGE_HEIGHT"},
    "other": {"label": "Diğer", "size_label": "Ölçü / Beden", "default_system": "OTHER"},
}

_CATEGORY_KEYWORDS = {
    "shoes": ("ayakkabi", "ayakkabı", "sneaker", "bot", "sandalet", "terlik", "shoe"),
    "tops": ("tisort", "tişört", "t-shirt", "gömlek", "gomlek", "sweatshirt", "kazak", "bluz"),
    "pants": ("pantolon", "jean", "esofman alti", "eşofman altı", "tayt", "şort", "sort"),
    "outerwear": ("mont", "ceket", "kaban", "parka", "yağmurluk", "yagmurluk"),
}


def category_meta(category: str | None) -> dict:
    return CATEGORY_CATALOG.get(str(category or "").strip().lower(), CATEGORY_CATALOG["other"])


def size_label_for_category(category: str | None) -> str:
    return category_meta(category)["size_label"]


def infer_product_category(title: str | None, fallback: str | None = None) -> str | None:
    text = str(title or "").strip().lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return category
    return fallback


def normalize_sizes(values: Iterable[object] | None) -> list[str]:
    normalized = {normalize_size(value) for value in (values or []) if str(value or "").strip()}
    return sorted(item for item in normalized if item)


def prepare_household_members(rows: list[dict] | None, id_factory) -> list[dict]:
    """Return a bounded, normalized profile payload while preserving stable ids."""
    members = []
    seen_member_ids = set()
    for raw_member in (rows or [])[:20]:
        name = str(raw_member.get("name") or "").strip()
        if not name:
            continue
        member_id = str(raw_member.get("id") or id_factory()).strip()
        if member_id in seen_member_ids:
            member_id = id_factory()
        seen_member_ids.add(member_id)
        preferences = []
        seen_preference_ids = set()
        for raw_preference in (raw_member.get("preferences") or [])[:20]:
            sizes = normalize_sizes(raw_preference.get("sizes"))
            if not sizes:
                continue
            category = str(raw_preference.get("category") or "shoes").strip().lower()
            preference_id = str(raw_preference.get("id") or id_factory()).strip()
            if preference_id in seen_preference_ids:
                preference_id = id_factory()
            seen_preference_ids.add(preference_id)
            preferences.append(
                {
                    "id": preference_id,
                    "category": category,
                    "label": str(raw_preference.get("label") or category_meta(category)["label"]).strip()[:80],
                    "size_system": str(
                        raw_preference.get("size_system") or category_meta(category)["default_system"]
                    ).strip()[:30],
                    "sizes": sizes[:12],
                    "notes": str(raw_preference.get("notes") or "").strip()[:300],
                }
            )
        members.append(
            {
                "id": member_id,
                "name": name[:80],
                "relationship": str(raw_member.get("relationship") or "").strip()[:60],
                "preferences": preferences,
            }
        )
    return members


def resolve_profile_preferences(profile: dict | None, preference_ids: list[str] | None) -> list[dict]:
    wanted = {str(value) for value in (preference_ids or []) if value}
    if not wanted:
        return []
    resolved = []
    for member in (profile or {}).get("household_members") or []:
        for preference in member.get("preferences") or []:
            if str(preference.get("id")) not in wanted:
                continue
            sizes = normalize_sizes(preference.get("sizes"))
            if not sizes:
                continue
            category = str(preference.get("category") or "shoes")
            resolved.append(
                {
                    "member_id": member.get("id"),
                    "member_name": member.get("name"),
                    "relationship": member.get("relationship"),
                    "preference_id": preference.get("id"),
                    "category": category,
                    "category_label": category_meta(category)["label"],
                    "size_label": size_label_for_category(category),
                    "size_system": preference.get("size_system") or category_meta(category)["default_system"],
                    "sizes": sizes,
                    "notes": preference.get("notes") or "",
                }
            )
    return resolved


def merge_watch_sizes(manual_sizes: list[str] | None, snapshots: list[dict] | None) -> list[str]:
    values = list(manual_sizes or [])
    for snapshot in snapshots or []:
        values.extend(snapshot.get("sizes") or [])
    return normalize_sizes(values)


def available_size_labels(sizes: list[dict] | None) -> list[str]:
    labels = []
    seen = set()
    for row in sizes or []:
        label = row.get("name") or row.get("size")
        normalized = normalize_size(label)
        if not normalized or normalized in seen or row.get("in_stock") is not True:
            continue
        seen.add(normalized)
        labels.append(str(label).strip())
    return labels


def newly_available_size_labels(previous_sizes: list[dict] | None, current_sizes: list[dict] | None) -> list[str]:
    previous = {normalize_size(value) for value in available_size_labels(previous_sizes)}
    return [value for value in available_size_labels(current_sizes) if normalize_size(value) not in previous]


def matching_size_labels(wanted_sizes: list[str] | None, available_sizes: list[str] | None) -> list[str]:
    wanted = {normalize_size(value) for value in (wanted_sizes or []) if value}
    if not wanted:
        return list(available_sizes or [])
    return [value for value in (available_sizes or []) if normalize_size(value) in wanted]


def watch_audience_for_sizes(watch: dict | None, matched_sizes: list[str] | None) -> list[str]:
    matched = {normalize_size(value) for value in (matched_sizes or []) if value}
    audience = []
    for snapshot in (watch or {}).get("size_preferences") or []:
        if matched and not matched.intersection(normalize_sizes(snapshot.get("sizes"))):
            continue
        name = str(snapshot.get("member_name") or "").strip()
        if name and name not in audience:
            audience.append(name)
    return audience


def alert_size_text(values: list[str] | None) -> str:
    clean = [str(value).strip() for value in (values or []) if str(value or "").strip()]
    return ", ".join(dict.fromkeys(clean)) if clean else "Beden/numara doğrulanamadı"
