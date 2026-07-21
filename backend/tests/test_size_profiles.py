import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from size_profiles import (
    alert_size_text,
    available_size_labels,
    infer_product_category,
    merge_watch_sizes,
    newly_available_size_labels,
    prepare_household_members,
    resolve_profile_preferences,
    watch_audience_for_sizes,
)


def test_household_profile_supports_two_shoe_sizes_and_apparel_sizes():
    counter = iter(["member-1", "shoe-pref", "top-pref"])
    members = prepare_household_members(
        [
            {
                "name": "Ali",
                "relationship": "Çocuk",
                "preferences": [
                    {"category": "shoes", "sizes": ["42", "43", "42"], "size_system": "EU"},
                    {"category": "tops", "sizes": ["M", "L"], "size_system": "INT"},
                ],
            }
        ],
        lambda: next(counter),
    )
    assert members[0]["preferences"][0]["sizes"] == ["42", "43"]
    assert members[0]["preferences"][1]["sizes"] == ["L", "M"]


def test_selected_profiles_merge_with_manual_radar_sizes_and_preserve_audience():
    profile = {
        "household_members": [
            {
                "id": "m1",
                "name": "Ayşe",
                "preferences": [
                    {"id": "p1", "category": "shoes", "size_system": "EU", "sizes": ["38", "39"]}
                ],
            }
        ]
    }
    snapshots = resolve_profile_preferences(profile, ["p1"])
    assert merge_watch_sizes(["40"], snapshots) == ["38", "39", "40"]
    watch = {"size_preferences": snapshots}
    assert watch_audience_for_sizes(watch, ["39"]) == ["Ayşe"]


def test_newly_available_sizes_only_returns_real_in_stock_transitions():
    previous = [
        {"name": "42", "in_stock": True},
        {"name": "43", "in_stock": False},
    ]
    current = [
        {"name": "42", "in_stock": True},
        {"name": "43", "in_stock": True},
        {"name": "44", "in_stock": False},
    ]
    assert available_size_labels(current) == ["42", "43"]
    assert newly_available_size_labels(previous, current) == ["43"]
    assert alert_size_text([]) == "Beden/numara doğrulanamadı"


def test_product_category_inference_is_not_limited_to_shoes():
    assert infer_product_category("Nike Pegasus Koşu Ayakkabısı") == "shoes"
    assert infer_product_category("Pamuklu Basic Tişört") == "tops"
    assert infer_product_category("Erkek Jean Pantolon") == "pants"
    assert infer_product_category("Su Geçirmez Outdoor Mont") == "outerwear"
