import sys
from pathlib import Path
from types import SimpleNamespace

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from discovery_sources import _sitemap_candidate_title, _title_from_product_url  # noqa: E402
from product_identity import identity_from_title, match_identities  # noqa: E402


def test_sitemap_title_keeps_adidas_product_slug_and_model_code():
    url = "https://www.adidas.com.tr/tr/adizero-evo-sl-ayakkabi/JH6206.html"

    title = _title_from_product_url(url)

    assert title == "adizero evo sl ayakkabi"


def test_adidas_sitemap_title_matches_evo_sl_watch():
    expected = identity_from_title("adidas adizero evo sl", brand="adidas")
    candidate = identity_from_title(
        _sitemap_candidate_title(
            SimpleNamespace(sitemap_title_prefix="adidas"),
            "https://www.adidas.com.tr/tr/adizero-evo-sl-ayakkabi/JH6206.html",
        ),
        brand="adidas",
    )

    match = match_identities(expected, candidate)

    assert match["decision"] == "auto"
    assert match["confidence"] >= 0.9
