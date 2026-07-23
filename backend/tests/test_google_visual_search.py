import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from stores.google_lens import GoogleLensEngine  # noqa: E402
from stores.google_shopping import GoogleShoppingEngine  # noqa: E402


def test_lens_parser_emits_canonical_and_ui_compatibility_fields():
    html = """
    <a href="https://shop.example/products/jr5220">
      <img src="https://img.example/jr5220.jpg">
      <span>Adidas Trail Running JR5220</span>
      <span>2.499 TL</span>
      <span>Örnek Mağaza</span>
    </a>
    """

    results = GoogleLensEngine().parse_lens_html(html)

    assert len(results) == 1
    assert results[0]["title"] == "Adidas Trail Running JR5220"
    assert results[0]["current_price"] == 2499.0
    assert results[0]["url"] == results[0]["link"]
    assert results[0]["image"] == results[0]["image_url"]


def test_shopping_parser_does_not_treat_product_code_as_price():
    html = """
    <a href="/shopping/product/123">
      <img src="https://img.example/jr5220.jpg">
      <span>Adidas Trail Running JR5220</span>
      <span>2.499 TL</span>
      <span>Örnek Mağaza</span>
    </a>
    """

    results = GoogleShoppingEngine().parse_shopping_html(
        html,
        "https://www.google.com/search?tbm=shop&q=JR5220",
    )

    assert len(results) == 1
    assert results[0]["title"] == "Adidas Trail Running JR5220"
    assert results[0]["current_price"] == 2499.0
    assert results[0]["url"] == results[0]["link"]
    assert results[0]["image"] == results[0]["image_url"]
