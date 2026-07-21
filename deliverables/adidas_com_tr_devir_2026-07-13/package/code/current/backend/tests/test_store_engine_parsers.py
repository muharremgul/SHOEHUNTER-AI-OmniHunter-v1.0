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
    results = engine("sportive").parse_search(
        html, "Pegasus Premium", "https://www.sportive.com.tr/list/?search_text=pegasus"
    )
    assert len(results) == 1
    assert results[0]["price"] == 10199.9
    assert results[0]["image"] == "https://img.example/pegasus.jpg"
    assert results[0]["url"] == "https://www.sportive.com.tr/nike-pegasus-premium-kadin-kosu-ayakkabisi-hq2593-500/"


def test_sportive_product_ignores_generic_social_title():
    html = """
    <html>
      <head>
        <title>adidas Adizero Evo SL Erkek Gri Kosu Ayakkabisi KI3381 | Sportive</title>
        <meta property="og:title" content="Iste Sana Gore Sportif Bir Urun">
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Adizero Evo SL Erkek Gri Kosu Ayakkabisi KI3381",
          "brand": {"@type": "Brand", "name": "adidas"},
          "offers": {"@type": "Offer", "price": "7649", "availability": "https://schema.org/InStock"}
        }
        </script>
      </head>
      <body>
        <h1 data-testid="product-name">adidas Adizero Evo SL Erkek Gri Kosu Ayakkabisi KI3381</h1>
        <button id="42"><span>42</span></button>
      </body>
    </html>
    """
    result = engine("sportive").parse(html, "https://www.sportive.com.tr/adidas-adizero-evo-sl-ki3381")
    assert result["title"] == "adidas Adizero Evo SL Erkek Gri Kosu Ayakkabisi KI3381"
    assert result["model_code"] == "KI3381"
    assert result["brand"] == "adidas"
    assert result["current_price"] == 7649


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


def test_decathlon_parse_reads_apparel_sku_stock():
    html = """
    <html>
      <head>
        <meta property="og:title" content="Cocuk Tenis Termal Esofman Alti">
        <meta property="product:original_price:amount" content="490">
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Cocuk Tenis Termal Esofman Alti",
          "offers": [[{
            "@type": "Offer",
            "sku": "5057291",
            "price": 490,
            "priceCurrency": "TRY",
            "availability": "https://schema.org/InStock"
          }]]
        }
        </script>
      </head>
      <body>
        <script>
          window.__DATA__ = {"skus":[{"skuId":"5057291","size":"123-130cm 7-8 YAS"}]};
        </script>
      </body>
    </html>
    """
    result = engine("decathlon").parse(html, "https://www.decathlon.com.tr/p/test")
    assert result["current_price"] == 490
    assert result["stock_status"] == "in_stock"
    assert result["stock_count"] == 1
    assert result["sizes"][0]["name"] == "123-130cm 7-8 YAS"


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
    assert result["stock_status"] == "unknown"


def test_amazon_parse_reads_price_image_and_sizes():
    html = """
    <html>
      <head><title>Under Armour UA Charged Surge 4 Erkek Spor Ayakkabi</title></head>
      <body>
        <span id="productTitle">Under Armour UA Charged Surge 4 Erkek Spor Ayakkabi</span>
        <img id="landingImage" data-a-dynamic-image='{"https://m.media-amazon.com/images/I/61OAh281n3L._AC_SY500_.jpg":[500,500]}' />
        <div id="corePrice_feature_div"><span class="a-price"><span class="a-offscreen">2.911,33 TL</span></span></div>
        <div id="availability">Stokta var.</div>
        <script>
          var data = {
            "sortedDimValuesForAllDims": {
              "size_name": [
                {"dimensionValueDisplayText":"40 EU","dimensionValueState":"UNAVAILABLE","defaultAsin":"B0A"},
                {"dimensionValueDisplayText":"42 EU","dimensionValueState":"AVAILABLE","defaultAsin":"B0B"}
              ]
            }
          };
        </script>
      </body>
    </html>
    """
    result = engine("amazon").parse(html, "https://www.amazon.com.tr/dp/B0BZXXR3TM")
    assert result["current_price"] == 2911.33
    assert result["image"].startswith("https://m.media-amazon.com/images/I/")
    assert result["stock_status"] == "in_stock"
    assert result["stock_count"] == 1
    assert [s["name"] for s in result["sizes"]] == ["40 EU", "42 EU"]


def test_amazon_dimension_display_fallback_keeps_sizes():
    html = """
    <span id="productTitle">Test Amazon Ayakkabi</span>
    <div id="availability">Stok bilgisi varyant seciminde</div>
    <script>
      var data = {
        "dimensionValuesDisplayData": {
          "B0AAAAAAA1": ["41 EU"],
          "B0AAAAAAA2": ["42 EU"]
        }
      };
    </script>
    """
    result = engine("amazon").parse(html, "https://www.amazon.com.tr/dp/B0BZXXR3TM")
    assert [item["name"] for item in result["sizes"]] == ["41 EU", "42 EU"]
    assert all(item["in_stock"] is None for item in result["sizes"])
    assert result["stock_status"] == "unknown"


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


def test_adidas_search_reads_rendered_product_card():
    html = """
    <article class="glass-product-card">
      <a href="/tr/adizero-evo-sl-ayakkabi/JH6206.html" aria-label="Adizero Evo SL Ayakkabi">
        <img src="https://assets.adidas.com/images/adizero.jpg" alt="Adizero Evo SL Ayakkabi">
        <h2 class="product-name">Adizero Evo SL Ayakkabi</h2>
        <div class="price">4.999 TL</div>
      </a>
    </article>
    """
    results = engine("adidas").parse_search(html, "adizero evo sl", "https://www.adidas.com.tr/tr/search?q=adizero")
    assert len(results) == 1
    assert results[0]["url"] == "https://www.adidas.com.tr/tr/adizero-evo-sl-ayakkabi/JH6206.html"
    assert results[0]["price"] == 4999


def test_yalispor_search_reads_discounted_adizero_cards():
    html = """
    <div class="product-list-horizontal">
      <div class="item product" data-gta="{&quot;item_name&quot;:&quot;adidas Adizero Evo Sl M&quot;,&quot;product_image_url&quot;:&quot;https:\\/\\/minio.yalispor.com.tr\\/yalispor\\/images\\/adizero-black.jpg&quot;,&quot;price&quot;:10199,&quot;item_variant&quot;:&quot;Siyah&quot;}">
        <a href="https://www.yalispor.com.tr/adidas-adizero-evo-sl-m-erkek-spor-ayakkabi-siyah-3">
          <img data-rsrc="https://minio.yalispor.com.tr/yalispor/images/adizero-black.jpg" alt="adidas Adizero Evo Sl M Erkek Spor Ayakkabi Siyah">
          <span class="card-title">adidas Adizero Evo Sl M Erkek Spor Ayakkabi Siyah</span>
          <strong class="price">10.199,00 TL</strong>
        </a>
      </div>
      <div class="item product" data-gta="{&quot;item_name&quot;:&quot;adidas Adizero Evo Sl W&quot;,&quot;product_image_url&quot;:&quot;https:\\/\\/minio.yalispor.com.tr\\/yalispor\\/images\\/adizero-grey.jpg&quot;,&quot;price&quot;:4499.5,&quot;discount&quot;:4499.5,&quot;item_variant&quot;:&quot;Gri&quot;}">
        <a href="https://www.yalispor.com.tr/adidas-adizero-evo-sl-w-kadin-spor-ayakkabi-gri">
          <img data-rsrc="https://minio.yalispor.com.tr/yalispor/images/adizero-grey.jpg" alt="adidas Adizero Evo Sl W Kadin Spor Ayakkabi Gri">
          <span class="card-title">adidas Adizero Evo Sl W Kadin Spor Ayakkabi Gri</span>
          <span class="old-price">8.999,00 TL</span>
          <strong class="price kategoriUrunFiyat">4.499,50 TL</strong>
        </a>
      </div>
    </div>
    """
    results = engine("yalispor").parse_search(
        html,
        "adizero evo sl",
        "https://www.yalispor.com.tr/tum-urunler?q=adizero+evo+sl",
    )
    assert len(results) == 2
    assert results[0]["price"] == 4499.5
    assert results[0]["url"].endswith("/adidas-adizero-evo-sl-w-kadin-spor-ayakkabi-gri")
    assert results[0]["image"] == "https://minio.yalispor.com.tr/yalispor/images/adizero-grey.jpg"


def test_yalispor_product_reads_available_sizes_from_body_size_only():
    html = """
    <html>
      <head>
        <meta property="og:title" content="adidas Adizero Evo Sl M Erkek Spor Ayakkabi Gri">
        <meta property="product:price:amount" content="4499.50">
      </head>
      <body>
        <div id="body-size">
          <label>Beden</label>
          <div class="btn-group-toggle product-size" data-toggle="buttons">
            <label class="fs-16 h-28 sizePadding rounded-0 btn btn-outline-secondary mr-1">
              <input type="radio" name="size" value="1289940" autocomplete="off"> 40.5
            </label>
          </div>
          <select name="size" placeholder="Beden">
            <option value="0">Beden Seciniz</option>
            <option value="1289940">40.5</option>
          </select>
        </div>
        <div id="stock-notify-1288183">
          <div class="btn-group-toggle product-size" data-toggle="buttons">
            <label><input type="radio" name="deger_id" value="1288185">41.5</label>
            <label><input type="radio" name="deger_id" value="1288186">42</label>
          </div>
        </div>
      </body>
    </html>
    """
    result = engine("yalispor").parse(
        html, "https://www.yalispor.com.tr/adidas-adizero-evo-sl-m-erkek-spor-ayakkabi-gri-3"
    )
    assert result["stock_status"] == "in_stock"
    assert result["stock_count"] == 1
    assert result["sizes"] == [
        {
            "name": "40.5",
            "size": "40.5",
            "in_stock": True,
            "sku": "1289940",
            "stock_source": "yalispor_body_size",
        }
    ]


def test_kaptanspor_search_reads_discount_price_and_lazy_image():
    html = """
    <div class="card-product">
      <a class="product-img" href="adidas-erkek-adizero-evo-sl-gri-kosu-ayakkabisi-ki3381-P2642">
        <img class="img-product" src="/images/load.gif"
             data-src="images/product/click/KI3381_1.jpg"
             alt="adidas Erkek Adizero Evo SL Gri Kosu Ayakkabisi KI3381">
      </a>
      <div class="cat-detail-products-box-fiyat">
        <div class="cat-detail-products-box-fiyat-mevcut"><span>5,099.50</span> TL</div>
        <div class="cat-detail-products-box-fiyat-eski"><span>10,199.00</span> TL</div>
      </div>
      <a class="fw-6 link" href="adidas-erkek-adizero-evo-sl-gri-kosu-ayakkabisi-ki3381-P2642">
        adidas Erkek Adizero Evo SL Gri Kosu Ayakkabisi KI3381
      </a>
    </div>
    """
    results = engine("kaptanspor").parse_search(
        html,
        "adizero evo sl",
        "https://kaptanspor.com.tr/arama/?q=adizero+evo+sl",
    )
    assert len(results) == 1
    assert results[0]["price"] == 5099.5
    assert results[0]["image"] == "https://kaptanspor.com.tr/images/product/click/KI3381_1.jpg"
    assert results[0]["url"].endswith("ki3381-P2642")
    assert results[0]["store"] == "Kaptan Spor"


def test_kaptanspor_product_reads_sizes_stock_old_price_and_variants():
    html = """
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "Product",
      "name": "adidas Erkek Adizero Evo SL Gri Kosu Ayakkabisi KI3381",
      "sku": "KI3381",
      "image": "https://kaptanspor.com.tr/images/product/click/KI3381_1.jpg",
      "offers": {
        "@type": "Offer",
        "price": "5099.50",
        "priceCurrency": "TRY",
        "availability": "https://schema.org/InStock"
      }
    }
    </script>
    <div class="tf-product-info-price">
      <div class="price-on-sale">5,099.50 TL</div>
      <div class="compare-at-price">10,199.00 TL</div>
    </div>
    <div id="size-selector-sizes-container-6522">
      <input class="size-selector-input calculate" id="option6522_1" name="var6522"
             type="radio" value="66569394">
      <label for="option6522_1">42</label>
      <input class="size-selector-input calculate" id="option6522_2" name="var6522"
             type="radio" value="66569395" disabled>
      <label for="option6522_2">44</label>
    </div>
    <table><tr class="tf-attr-pa-size"><td>Stok Durumu</td><td>Mevcut</td></tr></table>
    <div class="color-grid">
      <a href="/adidas-erkek-adizero-evo-sl-beyaz-ayakkabi-P2602">Beyaz</a>
      <a href="/adidas-erkek-adizero-evo-sl-gri-kosu-ayakkabisi-ki3381-P2642">Gri</a>
    </div>
    """
    url = "https://kaptanspor.com.tr/adidas-erkek-adizero-evo-sl-gri-kosu-ayakkabisi-ki3381-P2642"
    result = engine("kaptanspor").parse(html, url)
    assert result["current_price"] == 5099.5
    assert result["old_price"] == 10199
    assert result["model_code"] == "KI3381"
    assert result["stock_status"] == "in_stock"
    assert result["stock_count"] == 1
    assert [size["in_stock"] for size in result["sizes"]] == [True, False]
    assert result["variant_urls"] == [
        "https://kaptanspor.com.tr/adidas-erkek-adizero-evo-sl-beyaz-ayakkabi-P2602"
    ]
    assert engine("kaptanspor").capabilities()["sizes"] is True


def test_kaptanspor_out_of_stock_signal_overrides_price():
    html = """
    <meta property="og:title" content="adidas Galaxy 7 M ID8759 - Kaptan Spor | Test">
    <meta property="product:price:amount" content="1749.50">
    <table><tr class="tf-attr-pa-size"><td>Stok Durumu</td><td>Stokta Yok</td></tr></table>
    <p>Bu urun gecici olarak temin edilememektedir</p>
    """
    result = engine("kaptanspor").parse(
        html, "https://kaptanspor.com.tr/adidas-galaxy-7-id8759-P1119"
    )
    assert result["stock_status"] == "out_of_stock"
    assert result["in_stock"] is False


def test_intersport_jsonld_keeps_real_five_digit_price():
    html = """
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "Product",
      "name": "Test Kosu Ayakkabisi",
      "offers": {"@type": "Offer", "price": "19999", "availability": "https://schema.org/InStock"}
    }
    </script>
    """
    result = engine("intersport").parse(html, "https://www.intersport.com.tr/urun/test/test/")
    assert result["current_price"] == 19999


def test_brand_size_parsers_respect_disabled_sizes():
    nike_html = """
    <label class="disabled">EU 41</label>
    <label>EU 42.5</label>
    <div data-testid="product-price">5.999 TL</div>
    """
    nike = engine("nike").parse(nike_html, "https://www.nike.com/tr/t/test/ABC")
    assert [size["in_stock"] for size in nike["sizes"]] == [False, True]
    assert nike["stock_count"] == 1

    nb_html = """
    <div class="product-sizes">
      <label aria-disabled="true">42</label>
      <label>43</label>
    </div>
    <div class="product-price">6.199 TL</div>
    """
    newbalance = engine("newbalance").parse(nb_html, "https://www.newbalance.com.tr/urun/test")
    assert [size["in_stock"] for size in newbalance["sizes"]] == [False, True]
    assert newbalance["stock_count"] == 1


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
