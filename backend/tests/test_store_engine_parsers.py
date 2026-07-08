from pathlib import Path
import json
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from engines import ENGINES, _looks_like_bot_challenge, _score_result


def engine(slug):
    return next(item for item in ENGINES if item.slug == slug)


def test_score_result_matches_query_tokens():
    assert _score_result("Nike Pegasus 41 Erkek Kosu Ayakkabisi", "Pegasus 41") >= 80


def test_bot_challenge_detection_catches_akamai_page():
    html = '<div id="sec-if-cpt-container"><div class="scf-akamai-logo-sec-abc"></div></div>'
    assert _looks_like_bot_challenge(html) is True


def test_sportive_parse_search_card_uses_local_score_helper():
    html = """
    <div class="product-card">
      <a href="/urun/nike-pegasus-41-erkek-kosu-ayakkabisi">
        <img src="/img/pegasus.jpg" alt="Nike Pegasus 41 Erkek Kosu Ayakkabisi">
      </a>
      <h2 class="product-title">Nike Pegasus 41 Erkek Kosu Ayakkabisi</h2>
      <span class="product-price">4.999,90 TL</span>
    </div>
    """
    results = engine("sportive").parse_search(html, "Pegasus 41", "https://www.sportive.com.tr/arama?q=Pegasus+41")
    assert len(results) == 1
    assert results[0]["score"] >= 80
    assert results[0]["price"] == 4999.9
    assert results[0]["store"] == "Sportive"


def test_sportive_parse_search_reads_next_flight_products():
    products = [
        {
            "name": "Nike Pegasus Premium Kadin Kosu Ayakkabisi HQ2593-500",
            "absolute_url": "/nike-pegasus-premium-kadin-kosu-ayakkabisi-hq2593-500/",
            "price": "10199.90",
            "retail_price": "11999",
            "in_stock": True,
            "stock": "1",
            "productimage_set": [{"image": "https://img.example/pegasus.jpg"}],
        },
        {
            "name": "Nike Pegasus Tukenmis Kosu Ayakkabisi",
            "absolute_url": "/nike-pegasus-tukenmis-kosu-ayakkabisi/",
            "price": "9999.90",
            "in_stock": False,
            "stock": "0",
        },
    ]
    payload = json.dumps({"products": products}).replace('"', '\\"')
    html = f'<script>self.__next_f.push([1,"{payload}"])</script>'
    results = engine("sportive").parse_search(html, "Pegasus Premium", "https://www.sportive.com.tr/list/?search_text=pegasus")
    assert len(results) == 1
    assert results[0]["price"] == 10199.9
    assert results[0]["image"] == "https://img.example/pegasus.jpg"
    assert results[0]["url"] == "https://www.sportive.com.tr/nike-pegasus-premium-kadin-kosu-ayakkabisi-hq2593-500/"


def test_decathlon_parse_search_card_uses_local_score_helper():
    html = """
    <article>
      <a href="/p/nike-pegasus-41-kosu-ayakkabisi">
        <img data-src="/pegasus.jpg" alt="Nike Pegasus 41 Kosu Ayakkabisi">
      </a>
      <h3>Nike Pegasus 41 Kosu Ayakkabisi</h3>
      <span class="price">3.499 TL</span>
    </article>
    """
    results = engine("decathlon").parse_search(html, "Pegasus 41", "https://www.decathlon.com.tr/arama?q=Pegasus+41")
    assert len(results) == 1
    assert results[0]["score"] >= 80
    assert results[0]["price"] == 3499
    assert results[0]["store"] == "Decathlon"


def test_decathlon_parse_reads_meta_image():
    html = """
    <html>
      <head>
        <meta property="og:title" content="Decathlon Kosu Ayakkabisi">
        <meta name="twitter:image" content="/images/decathlon-product.jpg">
        <meta property="product:price:amount" content="2499.99">
      </head>
    </html>
    """
    result = engine("decathlon").parse(html, "https://www.decathlon.com.tr/p/test")
    assert result["image"] == "https://www.decathlon.com.tr/images/decathlon-product.jpg"


def test_trendyol_generic_parse_reads_itemprop_image():
    html = """
    <html>
      <head>
        <meta property="og:title" content="Trendyol Kosu Ayakkabisi">
        <meta itemprop="image" content="https://cdn.example/trendyol-product.jpg">
        <meta itemprop="price" content="1899.90">
      </head>
    </html>
    """
    result = engine("trendyol").parse(html, "https://www.trendyol.com/marka/model-p-123")
    assert result["image"] == "https://cdn.example/trendyol-product.jpg"


def test_newbalance_search_reads_jsonld_itemlist_products():
    html = """
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "ItemList",
      "itemListElement": [{
        "@type": "ListItem",
        "position": 1,
        "item": {
          "@type": "Product",
          "name": "New Balance 1080 Beyaz Kadin Kosu Ayakkabi W10801L7",
          "image": ["https://img.example/1080.jpg"],
          "offers": {
            "@type": "Offer",
            "price": "9990.00",
            "priceCurrency": "TRY",
            "availability": "https://schema.org/InStock",
            "url": "https://www.newbalance.com.tr/urun/new-balance-1080-beyaz-kadin-kosu-ayakkabi"
          }
        }
      }]
    }
    </script>
    """
    results = engine("newbalance").parse_search(html, "New Balance 1080", "https://www.newbalance.com.tr/arama?q=1080")
    assert len(results) == 1
    assert results[0]["price"] == 9990
    assert results[0]["image"] == "https://img.example/1080.jpg"


def test_adidas_productgroup_parse_price_and_stock():
    html = """
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "ProductGroup",
      "hasVariant": [
        {
          "@type": "Product",
          "size": "42",
          "sku": "SKU42",
          "offers": {
            "@type": "Offer",
            "price": "6799.00",
            "availability": "https://schema.org/InStock",
            "priceSpecification": {"price": "7999.00", "priceType": "https://schema.org/StrikethroughPrice"}
          }
        },
        {
          "@type": "Product",
          "size": "43",
          "sku": "SKU43",
          "offers": {"@type": "Offer", "price": "6799.00", "availability": "https://schema.org/OutOfStock"}
        }
      ]
    }
    </script>
    """
    result = engine("adidas").parse(html, "https://www.adidas.com.tr/tr/test/JQ1616.html")
    assert result["current_price"] == 6799
    assert result["old_price"] == 7999
    assert result["stock_count"] == 1
    assert result["sizes"][0]["in_stock"] is True
    assert result["sizes"][1]["in_stock"] is False


def test_brand_size_parsers_return_in_stock_key():
    nike_html = '<label>EU 42.5</label><div data-testid="product-price">5.999 TL</div>'
    nike = engine("nike").parse(nike_html, "https://www.nike.com/tr/t/test/ABC")
    assert nike["sizes"][0]["in_stock"] is True

    puma_html = '<button data-attr-value="42"></button><span class="sales"><span class="value">4.299 TL</span></span>'
    puma = engine("puma").parse(puma_html, "https://tr.puma.com/tr/pd/test/123.html")
    assert puma["sizes"][0]["in_stock"] is True

    nb_html = '<div class="product-sizes"><label>42</label></div><div class="product-price">6.199 TL</div>'
    newbalance = engine("newbalance").parse(nb_html, "https://www.newbalance.com.tr/urun/test")
    assert newbalance["sizes"][0]["in_stock"] is True
