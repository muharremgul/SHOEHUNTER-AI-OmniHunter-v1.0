import json
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from engines import ENGINES, StoreEngine  # noqa: E402
from stores.marketplaces import HepsiburadaEngine, N11Engine  # noqa: E402
from stores.outdoor import (  # noqa: E402
    BrooksEngine,
    ColumbiaEngine,
    SalomonEngine,
    TheNorthFaceEngine,
)
from stores.retailers import (  # noqa: E402
    AsicsEngine,
    BarcinEngine,
    BoynerEngine,
    FloEngine,
    KoraySporEngine,
    KutupayisiEngine,
    SkechersEngine,
    SneaksUpEngine,
    SpxEngine,
    SuperStepEngine,
)
from stores.structured_retail import StructuredRetailEngine  # noqa: E402

DEDICATED_ENGINE_CASES = [
    pytest.param(
        "barcin",
        BarcinEngine,
        ["barcin.com"],
        "https://www.barcin.com/nike-dunk-low-retro-erkek-spor-ayakkabi-petrol-beyaz-petrol/",
        "https://www.barcin.com/nike-dunk-low-retro-erkek-spor-ayakkabi-siyah-beyaz-siyah/",
        id="barcin",
    ),
    pytest.param(
        "korayspor",
        KoraySporEngine,
        ["korayspor.com"],
        "https://www.korayspor.com/nike-ayakkabi-gunluk-v5-rnr-ii6292-006/",
        "https://www.korayspor.com/nike-ayakkabi-gunluk-v5-rnr-ii6292-007/",
        id="korayspor",
    ),
    pytest.param(
        "flo",
        FloEngine,
        ["flo.com.tr"],
        "https://www.flo.com.tr/urun/nike-wmns-nike-initiator-beyaz-kadin-sneaker-101903292",
        "https://www.flo.com.tr/urun/nike-wmns-nike-initiator-siyah-kadin-sneaker-101903293",
        id="flo",
    ),
    pytest.param(
        "superstep",
        SuperStepEngine,
        ["superstep.com.tr"],
        "https://www.superstep.com.tr/urun/nike-p-6000-se-erkek-beyaz-spor-ayakkabi/ib2986/",
        "https://www.superstep.com.tr/urun/nike-p-6000-se-erkek-siyah-spor-ayakkabi/ib2987/",
        id="superstep",
    ),
    pytest.param(
        "sneaksup",
        SneaksUpEngine,
        ["sneaksup.com"],
        "https://www.sneaksup.com/nike-air-force-1-07-dd8959-103",
        "https://www.sneaksup.com/nike-air-force-1-07-dd8959-104",
        id="sneaksup",
    ),
    pytest.param(
        "boyner",
        BoynerEngine,
        ["boyner.com.tr"],
        "https://www.boyner.com.tr/nike-ib1895-002-nike-downshifter-14-siyah-erkek-kosu-ayakkabisi-p-15838252",
        "https://www.boyner.com.tr/nike-ib1895-003-nike-downshifter-14-mavi-erkek-kosu-ayakkabisi-p-15838253",
        id="boyner",
    ),
    pytest.param(
        "spx",
        SpxEngine,
        ["spx.com.tr"],
        "https://www.spx.com.tr/xa-pro-3d-v9-siyah-l47271900-31075-2/",
        "https://www.spx.com.tr/xa-pro-3d-v9-mavi-l47271901-31076-2/",
        id="spx",
    ),
    pytest.param(
        "kutupayisi",
        KutupayisiEngine,
        ["kutupayisi.com"],
        "https://www.kutupayisi.com/urun/keen-targhee-iii-erkek-su-gecirmez-outdoor-bot-46-kahverengi-siyah",
        "https://www.kutupayisi.com/urun/keen-targhee-iii-erkek-su-gecirmez-outdoor-bot-46-mavi-siyah",
        id="kutupayisi",
    ),
    pytest.param(
        "hepsiburada",
        HepsiburadaEngine,
        ["hepsiburada.com"],
        "https://www.hepsiburada.com/nike-pegasus-41-p-HBCV000000ABC",
        "https://www.hepsiburada.com/nike-pegasus-41-mavi-p-HBCV000000ABD",
        id="hepsiburada",
    ),
    pytest.param(
        "n11",
        N11Engine,
        ["n11.com"],
        "https://www.n11.com/urun/nike-pegasus-41-123456",
        "https://www.n11.com/urun/nike-pegasus-41-mavi-123457",
        id="n11",
    ),
    pytest.param(
        "asics",
        AsicsEngine,
        ["asics.com.tr"],
        "https://www.asics.com.tr/gel-1130-1338",
        "https://www.asics.com.tr/gel-1130-1339",
        id="asics",
    ),
    pytest.param(
        "skechers",
        SkechersEngine,
        ["skechers.com.tr"],
        "https://www.skechers.com.tr/p-escape-plan-endless-pursuit-kadin-siyah-outdoor-ayakkabi-180061-bkhp",
        "https://www.skechers.com.tr/p-escape-plan-endless-pursuit-kadin-mavi-outdoor-ayakkabi-180061-blue",
        id="skechers",
    ),
    pytest.param(
        "brooks",
        BrooksEngine,
        ["brooksrunning.com.tr"],
        "https://www.brooksrunning.com.tr/p-glycerin-max-2-erkek-lacivert-kosu-ayakkabisi-1104791d485",
        "https://www.brooksrunning.com.tr/p-ghost-17-kadin-mavi-kosu-ayakkabisi-1204311b431",
        id="brooks",
    ),
    pytest.param(
        "columbia",
        ColumbiaEngine,
        ["columbia.com.tr"],
        "https://www.columbia.com.tr/siyah-firecamp-iii-waterproof-erkek-ayakkabi-p-42159",
        "https://www.columbia.com.tr/titanium-gri-konos-trs-erkek-ayakkabi-p-51085",
        id="columbia",
    ),
    pytest.param(
        "salomon",
        SalomonEngine,
        ["salomon.com.tr"],
        "https://www.salomon.com.tr/speedcross-6-erkek-patika-kosu-ayakkabisi-l41737900",
        "https://www.salomon.com.tr/speedcross-6-17456",
        id="salomon",
    ),
    pytest.param(
        "thenorthface",
        TheNorthFaceEngine,
        ["thenorthface.com.tr"],
        "https://www.thenorthface.com.tr/kadin-altamesa-300-patika-kosusu-ayakkabisi_134175",
        "https://www.thenorthface.com.tr/cocuk-altamesa-patika-kosusu-ayakkabisi_134209",
        id="thenorthface",
    ),
]


def _engine(slug):
    matches = [engine for engine in ENGINES if engine.slug == slug]
    assert len(matches) == 1, f"{slug} registry'de tam bir kez bulunmali"
    return matches[0]


def _shared_product_html(product_url, variant_url):
    product = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "Nike Air Zoom Pegasus 41 Erkek Kosu Ayakkabisi",
        "sku": "PEGASUS-41",
        "brand": {"@type": "Brand", "name": "Nike"},
        "image": "https://cdn.example.test/pegasus-41.jpg",
        "offers": {
            "@type": "Offer",
            "price": "3499.00",
            "priceCurrency": "TRY",
            "availability": "https://schema.org/InStock",
        },
    }
    return f"""
    <html>
      <head>
        <title>Nike Air Zoom Pegasus 41</title>
        <meta property="og:image" content="https://cdn.example.test/pegasus-41.jpg">
        <script type="application/ld+json">{json.dumps(product)}</script>
      </head>
      <body>
        <h1>Nike Air Zoom Pegasus 41 Erkek Kosu Ayakkabisi</h1>

        <div data-testid="product-price" data-price="3299.00">3.299,00 TL</div>
        <div data-test-id="price-current-price">3.299,00 TL</div>
        <meta itemprop="price" content="3299.00">
        <div class="product-detail product-detail-price">
          <span class="sale-price discounted-price current-price">3.299,00 TL</span>
        </div>
        <div class="product-price ProductPrice">
          <span class="current discount discountedPrice">3.299,00 TL</span>
        </div>
        <div class="newPrice"><ins>3.299,00 TL</ins></div>

        <div data-testid="size-picker" data-test-id="size-picker">
          <button data-size="42" data-in-stock="true">42</button>
          <button data-size="43" disabled>43</button>
          <input data-size="42" data-in-stock="true" value="42">
          <input data-size="43" value="43" disabled>
        </div>
        <div class="size-selector size-list size-selection beden skuVariantList">
          <button data-size="42" data-in-stock="true">42</button>
          <button data-size="43" disabled>43</button>
        </div>
        <div class="size-option" data-size="42" data-in-stock="true">42</div>
        <div class="size-option" data-size="43" aria-disabled="true">43</div>
        <select name="size">
          <option>Beden Sec</option>
          <option data-in-stock="true">42</option>
          <option disabled>43</option>
        </select>

        <button data-testid="add-to-cart">Sepete Ekle</button>
        <div class="renk color-option"><a href="{variant_url}">Mavi</a></div>

        <article data-testid="product-card" class="product-card product-item">
          <a href="{product_url}" title="Nike Air Zoom Pegasus 41 Erkek Kosu Ayakkabisi">
            <img src="https://cdn.example.test/pegasus-card.jpg" alt="Nike Air Zoom Pegasus 41">
            <h2>Nike Air Zoom Pegasus 41 Erkek Kosu Ayakkabisi</h2>
            <span data-price="3299.00">3.299,00 TL</span>
          </a>
        </article>
      </body>
    </html>
    """


@pytest.mark.parametrize(
    "slug,engine_class,domains,product_url,variant_url",
    DEDICATED_ENGINE_CASES,
)
def test_each_former_generic_and_outdoor_store_has_a_dedicated_registry_contract(
    slug, engine_class, domains, product_url, variant_url
):
    engine = _engine(slug)

    assert type(engine) is engine_class
    assert isinstance(engine, StructuredRetailEngine)
    assert engine.domains == domains
    assert engine.supports_url(product_url)
    assert engine.is_product_link(product_url)
    assert engine.supports_url(variant_url)
    assert engine.is_product_link(variant_url)
    assert not engine.supports_url(f"https://{domains[0]}.example.test/fake-product")


@pytest.mark.parametrize(
    "slug,engine_class,domains,product_url,variant_url",
    DEDICATED_ENGINE_CASES,
)
def test_dedicated_engines_parse_shared_structured_dom_stock_variant_and_search_fixture(
    slug, engine_class, domains, product_url, variant_url
):
    engine = _engine(slug)
    html = _shared_product_html(product_url, variant_url)

    product = engine.parse(html, product_url)

    assert product["title"]
    assert product["brand"] == "Nike"
    assert product["model_code"] == "PEGASUS-41"
    assert product["current_price"] in {3299.0, 3499.0}
    assert product["price_source"]
    assert product["image"] == "https://cdn.example.test/pegasus-41.jpg"
    sizes = {item["name"]: item["in_stock"] for item in product["sizes"]}
    assert sizes["42"] is True
    assert sizes["43"] is False
    assert product["stock_status"] == "in_stock"
    assert product["stock_count"] >= 1
    assert variant_url.rstrip("/") in {url.rstrip("/") for url in product["variant_urls"]}

    search_results = engine.parse_search(html, "Pegasus 41", engine.search_path or f"https://www.{domains[0]}/arama")
    match = next(item for item in search_results if item["url"].rstrip("/") == product_url.rstrip("/"))
    assert match["score"] >= 80
    assert match["price"] == 3299.0
    assert match["image"] == "https://cdn.example.test/pegasus-card.jpg"
    assert match["store"] == engine.name


MARKETPLACE_CASES = [
    pytest.param(
        "hepsiburada",
        "https://www.hepsiburada.com/nike-pegasus-41-p-HBCV000000ABC",
        """
        <div data-test-id="merchant-name">Hepsiburada Resmi Magaza</div>
        <div data-test-id="merchant-rating">9,8 / 10</div>
        <div data-test-id="delivery-info">Yarin ucretsiz teslimat</div>
        """,
        "Hepsiburada Resmi Magaza",
        id="hepsiburada-marketplace-fields",
    ),
    pytest.param(
        "n11",
        "https://www.n11.com/urun/nike-pegasus-41-123456",
        """
        <div class="unf-p-seller-name">n11 Resmi Magaza</div>
        <div class="unf-p-seller-rating">9,7 / 10</div>
        <div class="unf-p-shipping">Bugun ucretsiz kargo</div>
        """,
        "n11 Resmi Magaza",
        id="n11-marketplace-fields",
    ),
]


@pytest.mark.parametrize("slug,product_url,marketplace_html,expected_seller", MARKETPLACE_CASES)
def test_marketplaces_parse_seller_rating_shipping_and_campaign(
    slug, product_url, marketplace_html, expected_seller
):
    engine = _engine(slug)
    html = f"""
    <html><head>
      <meta property="og:title" content="Nike Pegasus 41">
      <meta itemprop="price" content="2999.00">
    </head><body>
      {marketplace_html}
      <div class="campaign-card">Sepette 200 TL kupon firsati</div>
      <button data-testid="add-to-cart">Sepete Ekle</button>
    </body></html>
    """

    product = engine.parse(html, product_url)

    assert product["seller"] == expected_seller
    assert product["seller_rating"] in {9.7, 9.8}
    assert product["shipping"]
    assert "ucretsiz" in product["shipping"].lower()
    assert product["official_seller"] is True
    assert any(
        campaign["type"] == "coupon" and "200 TL" in campaign["label"]
        for campaign in product["campaigns"]
    )


def test_brooks_accepts_capital_price_key_in_product_json_ld_offer():
    engine = _engine("brooks")
    product_url = "https://www.brooksrunning.com.tr/p-glycerin-22-110445"
    product = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "Brooks Glycerin 22",
        "offers": {
            "@type": "Offer",
            "Price": "5.999,00 TL",
            "priceCurrency": "TRY",
            "availability": "https://schema.org/InStock",
        },
    }
    html = f"""
    <html><head>
      <script type="application/ld+json">{json.dumps(product)}</script>
    </head><body><h1>Brooks Glycerin 22</h1></body></html>
    """

    result = engine.parse(html, product_url)

    assert result["current_price"] == 5999.0
    assert result["price_source"] == "brooks_json_ld_offer"
    assert result["confidence"] >= 0.8
    assert {candidate["source"] for candidate in result["debug"]["price_candidates"]} == {
        "brooks_json_ld_offer"
    }


def test_blocked_result_keeps_stock_and_availability_contract_explicit():
    result = StoreEngine().blocked_result("https://example.test/product", "access_challenge")

    assert result["stock_status"] == "blocked"
    assert result["availability"] == "blocked"
    assert result["in_stock"] is False
    assert result["stock_count"] == 0
    assert result["current_price"] is None
    assert result["debug"]["notes"] == ["access_challenge"]


def test_columbia_uses_catalog_and_sitemap_discovery_without_fake_search_route():
    engine = _engine("columbia")

    assert engine.search_path is None
    assert engine.discovery_method == "catalog+sitemap"
    assert engine.capabilities()["search"] is False
    assert engine.capabilities()["discovery_method"] == "catalog+sitemap"


@pytest.mark.parametrize(
    "slug,url",
    [
        ("barcin", "https://www.barcin.com/ayakkabi/"),
        ("barcin", "https://www.barcin.com/blog-spor-ayakkabi-secimi/"),
        ("korayspor", "https://www.korayspor.com/cinsiyet-unisex/ayakkabi/"),
        ("flo", "https://www.flo.com.tr/ayakkabi"),
        ("boyner", "https://www.boyner.com.tr/erkek-ayakkabi"),
        ("brooks", "https://www.brooksrunning.com.tr/yol-kosusu-ayakkabilari-c-a61001"),
        ("columbia", "https://www.columbia.com.tr/ayakkabi?pageIndex=1"),
        ("salomon", "https://www.salomon.com.tr/erkek-ayakkabi"),
        ("thenorthface", "https://www.thenorthface.com.tr/tum-ayakkabilar"),
    ],
)
def test_category_and_blog_urls_are_not_product_links(slug, url):
    assert _engine(slug).is_product_link(url) is False


def test_every_registered_store_reports_cart_offer_capability():
    # Google Shopping is an explicit discovery source in addition to the
    # 27 dedicated retailer engines.
    assert len(ENGINES) == 28
    retailer_engines = [engine for engine in ENGINES if engine.slug != "google_shopping"]
    assert len(retailer_engines) == 27
    assert all(engine.capabilities()["cart_price"] is True for engine in retailer_engines)
    assert _engine("google_shopping").capabilities()["cart_price"] is False


def test_exact_visible_cart_price_stays_separate_from_shelf_price():
    html = """
    <html><head>
      <meta property="og:title" content="Nike Kosu Ayakkabisi">
      <meta property="product:price:amount" content="3999.00">
    </head><body>
      <div class="sepette-fiyat">Sepette 3.399 TL</div>
    </body></html>
    """
    product = _engine("barcin").parse(
        html,
        "https://www.barcin.com/nike-kosu-ayakkabisi-erkek-siyah-model-kodu/",
    )

    assert product["current_price"] == 3999.0
    assert product["cart_price"] == 3399.0
    assert product["cart_price_confidence"] >= 0.9
    assert product["cart_price_conditions"] == []
    assert any(item.get("exact_price") == 3399.0 for item in product["campaigns"])


@pytest.mark.parametrize(
    "offer,expected_condition",
    [
        ("2 ve üzeri üründe sepette %10 indirim", "quantity"),
        ("2 ve Üzerine Sepette Ek %10 İndirim", "quantity"),
        ("1 Üründe Sepette %10 İndirim", "quantity"),
        ("OUTLET25 koduyla sepette 3.000 TL", "code_or_coupon"),
        ("45 ve üzeri bedenlerde sepette %20 indirim", "size"),
        ("Üyelere mobil uygulamada sepette %15 indirim", "membership"),
        ("Columbia Dünyası Üyelerine Sepette Ek %5 İndirim", "membership"),
    ],
)
def test_conditional_cart_offer_never_becomes_unconditional_price(offer, expected_condition):
    html = f"""
    <html><head><meta property="product:price:amount" content="3999.00"></head>
    <body><div class="campaign sepette-kampanya">{offer}</div></body></html>
    """
    product = _engine("spx").parse(html, "https://www.spx.com.tr/model-ayakkabi-abc123-1/")

    assert product["cart_price"] is None
    cart_campaign = next(item for item in product["campaigns"] if item["type"] == "cart")
    assert cart_campaign["conditional"] is True
    assert expected_condition in cart_campaign["conditions"]


def test_boyner_sibling_offer_restores_normal_price_and_exact_cart_price():
    html = """
    <html><head>
      <meta property="og:title" content="Kate Spade Ayakkabi">
      <script type="application/ld+json">
        {"@type":"Product","name":"Kate Spade Ayakkabi","offers":{"price":"16999"}}
      </script>
    </head><body>
      <div class="price_priceLeft__VRQGR">
        <p class="price_priceOldPrice__FM_Do">22.999 TL</p>
        <p class="price_priceDiscountText__rm96C">Sepette %26 İndirim</p>
        <h2 class="price_priceMain__DrVVQ">16.999 TL</h2>
      </div>
    </body></html>
    """
    product = _engine("boyner").parse(
        html,
        "https://www.boyner.com.tr/kate-spade-ayakkabi-p-15752389",
    )

    assert product["current_price"] == 22999.0
    assert product["cart_price"] == 16999.0
    assert product["old_price"] is None
    assert product["cart_price_conditions"] == []


def test_first_product_offer_wins_over_cheaper_recommendation_card():
    html = """
    <html><head><meta property="product:price:amount" content="3999.00"></head><body>
      <main><div class="sepette-main">Sepette 3.399 TL</div></main>
      <section aria-label="recommendations">
        <div class="sepette-card">Sepette 455,70 TL</div>
      </section>
    </body></html>
    """
    product = _engine("flo").parse(html, "https://www.flo.com.tr/urun/test-ayakkabi-123")

    assert product["cart_price"] == 3399.0


def test_cart_price_does_not_confuse_membership_price_in_same_card():
    html = """
    <html><head><meta property="product:price:amount" content="599.90"></head><body>
      <div data-testid="price-div" class="product-card-price">
        <div class="basket-promotion-price-label">Sepette %3 İndirim</div>
        <div data-testid="basket-promo-price-wrapper" class="basket-promo-price-wrapper">
          <div data-testid="discounted-price" class="discounted-price">
            <span>Sepette</span><span>581,90 TL</span><span>599,90 TL</span>
          </div>
        </div>
        <div class="ty-plus-strip-view">Trendyol Plus ile 552,80 TL</div>
      </div>
    </body></html>
    """
    product = _engine("flo").parse(html, "https://www.flo.com.tr/urun/test-ayakkabi-123")

    assert product["current_price"] == 599.9
    assert product["cart_price"] == 581.9
    assert product["cart_price"] != 552.8


def test_hidden_cart_price_template_is_not_promoted():
    html = """
    <html><head><meta property="product:price:amount" content="3999.00"></head><body>
      <div style="display:none">
        <span class="urunKampanyaAciklama">Sepetteki Son Fiyat 2.999 TL</span>
      </div>
    </body></html>
    """
    product = _engine("asics").parse(html, "https://www.asics.com.tr/test-645")

    assert product["cart_price"] is None


def test_intersport_keeps_shelf_and_cart_prices_as_distinct_values():
    html = """
    <html><head><meta property="og:title" content="Nike Pegasus"></head><body>
      <div class="product-price"><pz-price>3.999 TL</pz-price></div>
      <div class="product-item__offers">
        <span>SEPETTE %20 İNDİRİM</span>
        <div class="product-item__offer-price"><pz-price>3.199 TL</pz-price></div>
      </div>
    </body></html>
    """
    product = _engine("intersport").parse(
        html,
        "https://www.intersport.com.tr/urun/nike-pegasus/",
    )

    assert product["current_price"] == 3999.0
    assert product["cart_price"] == 3199.0
    assert product["price_source"] == "shelf"
    assert product["cart_price_source"].startswith("intersport:")


def test_trusted_product_json_ld_is_not_overwritten_by_related_card_price():
    engine = _engine("columbia")
    url = "https://www.columbia.com.tr/siyah-firecamp-iii-waterproof-erkek-ayakkabi-p-42159"
    html = """
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "Product",
      "name": "Firecamp III Waterproof Erkek Ayakkabi",
      "offers": {"@type": "Offer", "price": "8999.90", "availability": "https://schema.org/InStock"}
    }
    </script>
    <aside class="related-products">
      <div class="product-price">999,90 TL</div>
    </aside>
    """

    result = engine.parse(html, url)

    assert result["current_price"] == 8999.9
    assert result["price_source"] == "json_ld"
    assert any(candidate["source"].endswith("_not_promoted") for candidate in result["debug"]["price_candidates"])


def test_embedded_state_requires_current_product_identity_when_multiple_products_exist():
    engine = _engine("thenorthface")
    url = "https://www.thenorthface.com.tr/kadin-altamesa-300-patika-kosusu-ayakkabisi_134175"
    state = {
        "products": [
            {
                "name": "Related Vectiv Shoe",
                "productId": "999999",
                "productUrl": "/erkek-related-vectiv_999999",
                "price": 1999,
            },
            {
                "name": "Kadin Altamesa 300 Patika Kosusu Ayakkabisi",
                "productId": "134175",
                "productUrl": "/kadin-altamesa-300-patika-kosusu-ayakkabisi_134175",
                "price": 7499,
            },
        ]
    }
    html = f"""
    <meta property="og:title" content="Kadin Altamesa 300 Patika Kosusu Ayakkabisi">
    <script id="__NEXT_DATA__" type="application/json">{json.dumps(state)}</script>
    """

    result = engine.parse(html, url)

    assert result["current_price"] == 7499
    assert result["price_source"] == "embedded_product_state"
    assert result["model_code"] == "134175"


def test_ambiguous_embedded_products_do_not_promote_the_cheapest_related_price():
    engine = _engine("columbia")
    url = "https://www.columbia.com.tr/siyah-firecamp-iii-waterproof-erkek-ayakkabi-p-42159"
    state = {
        "products": [
            {"name": "Related Shoe One", "productId": "11111", "price": 999},
            {"name": "Related Shoe Two", "productId": "22222", "price": 1999},
        ]
    }
    html = f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(state)}</script>'

    result = engine.parse(html, url)

    assert result["current_price"] is None
    assert result["price_source"] is None
    assert "embedded_product_state_ambiguous" in result["debug"]["notes"]


def test_single_unrelated_embedded_product_state_does_not_promote_its_price():
    engine = _engine("columbia")
    url = "https://www.columbia.com.tr/siyah-firecamp-iii-waterproof-erkek-ayakkabi-p-42159"
    state = {
        "product": {
            "name": "Newton Ridge Plus II Bot",
            "productId": "99999",
            "price": 12999,
        }
    }
    html = f"""
    <meta property="og:title" content="Firecamp III Waterproof Erkek Ayakkabi">
    <script id="__NEXT_DATA__" type="application/json">{json.dumps(state)}</script>
    """

    result = engine.parse(html, url)

    assert result["current_price"] is None
    assert result["price_source"] is None
    assert "embedded_product_state_identity_unverified" in result["debug"]["notes"]


def test_tied_same_name_embedded_states_with_different_ids_and_prices_are_not_promoted():
    engine = _engine("columbia")
    url = "https://www.columbia.com.tr/siyah-firecamp-iii-waterproof-erkek-ayakkabi-p-42159"
    state = {
        "products": [
            {
                "name": "Firecamp III Waterproof Erkek Ayakkabi",
                "productId": "11111",
                "price": 7999,
            },
            {
                "name": "Firecamp III Waterproof Erkek Ayakkabi",
                "productId": "22222",
                "price": 8999,
            },
        ]
    }
    html = f"""
    <meta property="og:title" content="Firecamp III Waterproof Erkek Ayakkabi">
    <script id="__NEXT_DATA__" type="application/json">{json.dumps(state)}</script>
    """

    result = engine.parse(html, url)

    assert result["current_price"] is None
    assert result["price_source"] is None
    assert "embedded_product_state_ambiguous" in result["debug"]["notes"]


def test_embedded_product_state_with_external_product_url_is_rejected():
    engine = _engine("columbia")
    url = "https://www.columbia.com.tr/siyah-firecamp-iii-waterproof-erkek-ayakkabi-p-42159"
    state = {
        "product": {
            "name": "Firecamp III Waterproof Erkek Ayakkabi",
            "productId": "42159",
            "productUrl": "https://catalog.example.test/firecamp-iii-p-42159",
            "price": 7499,
        }
    }
    html = f"""
    <meta property="og:title" content="Firecamp III Waterproof Erkek Ayakkabi">
    <script id="__NEXT_DATA__" type="application/json">{json.dumps(state)}</script>
    """

    result = engine.parse(html, url)

    assert result["current_price"] is None
    assert result["price_source"] is None
    assert "embedded_product_state_identity_mismatch" in result["debug"]["notes"]


def test_size_label_checks_linked_disabled_input_and_keeps_unknown_stock_unknown():
    engine = _engine("brooks")
    url = "https://www.brooksrunning.com.tr/p-glycerin-max-2-erkek-lacivert-kosu-ayakkabisi-1104791d485"
    html = """
    <div class="size-selector">
      <input id="size-42" type="radio" disabled><label for="size-42">42</label>
      <label data-size="43">43</label>
      <label data-size="44" data-in-stock="true">44</label>
    </div>
    """

    result = engine.parse(html, url)
    sizes = {item["name"]: item["in_stock"] for item in result["sizes"]}

    assert sizes == {"42": False, "43": None, "44": True}
    assert result["stock_count"] == 1
    assert result["stock_status"] == "in_stock"
