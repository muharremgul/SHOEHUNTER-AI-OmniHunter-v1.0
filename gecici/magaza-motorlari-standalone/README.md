# Türkiye E-Ticaret Mağaza Motorları (Bağımsız Paket)

Bu, [ShoeHunterAI](.) projesinden çıkarılmış, **hiçbir Flask/SQLAlchemy/veritabanı
bağımlılığı olmayan**, tamamen bağımsız bir modüldür. Bir ürün URL'si verildiğinde
fiyat ve beden/stok bilgisini döndüren "mağaza motorları" (store engines) içerir.
Başka bir projede fiyat/stok takibi yapmak isteyen biri (insan ya da yapay zeka)
bu klasörü olduğu gibi alıp kullanabilir.

## Ne İşe Yarar

```python
from stores.intersport import IntersportStore

store = IntersportStore()
data = store.get_product_data("https://www.intersport.com.tr/urun/.../123456/")
print(data)
# {
#   "current_price": 4599.90,
#   "old_price": None,
#   "stock_count": 2,
#   "sizes": [{"name": "42", "in_stock": True, "sku": "SKU-042", ...}, ...],
#   "in_stock": True,
# }
```

`debug=True` verirseniz ek olarak `_debug` anahtarında ham veri ve 0.0-1.0 güven
skorları döner (bkz. "Güven Skorları" bölümü).

## Mimari

```
stores/
  base_store.py    -- Her motorun uyduğu soyut arayüz (BaseStore)
  http_utils.py     -- Ortak, retry'li HTTP GET (3 deneme, kademeli bekleme)
  registry.py       -- driver_key -> motor sınıfı eşleme tablosu
  intersport.py     -- IntersportStore  (driver_key="intersport")
  sportive.py       -- SportiveStore    (driver_key="sportive")
  decathlon.py      -- DecathlonStore   (driver_key="decathlon")
```

Yeni bir mağaza eklemek için:
1. `BaseStore`'dan türeyen yeni bir sınıf yazın (`name`, `driver_key`, `domains`, `get_product_data`).
2. `stores/registry.py`'deki `_ENGINES` sözlüğüne bir satır ekleyin.

```python
from stores.registry import get_engine, is_supported

if is_supported("intersport"):
    engine = get_engine("intersport")
    data = engine.get_product_data(url)
```

## Her Motorun Gerçek Durumu (ÖNEMLİ — dürüstçe okuyun)

Bu motorlar farklı güvenilirlik seviyelerinde. Birini yeni bir projede
kullanmadan önce mutlaka bu tabloyu okuyun:

| Motor | Fiyat kaynağı | Fiyat güveni | Stok kaynağı | Stok güveni | Nasıl doğrulandı |
|---|---|---|---|---|---|
| **Intersport** | DOM (sepet indirimi + raf fiyatı), JSON-LD fallback | 1.0 (DOM) / 0.6 (JSON-LD) | `<pz-variant-option selectable>` özniteliği | **0.95** | Gerçek sayfa + kullanıcı geri bildirimiyle üretimde uzun süre doğrulandı |
| **Adidas Türkiye** | schema.org `ProductGroup.hasVariant.offers.price` (JSON-LD) | 0.9 | `offers.availability` (her beden ayrı) | **0.9** | Gerçek sayfa dosyası (kullanıcı yükledi) incelendi; pozitif ("InStock") doğrulandı, negatif değer standart schema.org enum'undan makul çıkarım |
| **Decathlon** | `product:price:amount` / `product:original_price:amount` meta etiketleri | 0.85 | "Stokta Mevcut" / "Stokta Mevcut Değil" metin örüntüsü | **0.75** | Gerçek sayfa `web_fetch` ile incelendi; HEM pozitif HEM negatif durum gözlemlendi |
| **Sportive** | schema.org JSON-LD (`Product.offers.price`), meta `name=og:price:amount` fallback | 0.9 | `<button id="{beden}">` + içindeki "Tükendi" `<p>` etiketi | **0.85** | Gerçek sayfa dosyası (kullanıcı yükledi) incelendi. İlk sürüm `property=` yerine `name=` aranması gerektiğini kaçırmıştı — düzeltildi |

**Neden bu fark önemli:** Intersport'un stok sinyali bir HTML özniteliğine (`selectable`)
dayanıyor — sayfa yeniden tasarlansa bile büyük ihtimalle kırılmaz, çünkü doğrudan
"bu seçenek seçilebilir mi" bilgisini taşıyor. Sportive ve Decathlon'unki ise
görünür METNE dayanıyor ("Tükendi" / "Stokta Mevcut") — çeviri/metin değişirse
(örn. "Stokta Yok" olarak değiştirilirse) kırılır. Bu yüzden production'da
gerçek alarm göndermeden önce, özellikle Sportive/Decathlon için, mutlaka
**Debug Lab tarzı bir doğrulama** yapıp güncel sonucu gözle kontrol edin.

## Kurulum

```bash
pip install -r requirements.txt   # sadece beautifulsoup4 + requests
```

## Testler

```bash
python -m pytest tests/
# veya
python -m unittest discover -s tests
```

18 test (Intersport 16, Sportive+Decathlon+paylaşımlı-retry 12 — bazıları
üst üste bindiği için toplamda 28 civarı, `-v` ile tam liste görünür).
Tüm testler gerçek ağ isteği ATMAZ; `unittest.mock` ile sahte HTTP yanıtları
kullanılır, fixture'lar (`tests/fixtures/*.html`) gerçek sayfa yapısına
dayanır.

## Bilinen Sınırlamalar (yeni bir projede kullanmadan önce bilin)

1. **JS-render edilen siteler**: Sportive gibi Next.js/SPA tabanlı sitelerde,
   `requests` ile çekilen HTML'in READ-ONLY (statik) kısmı yeterli oldu çünkü
   fiyat/stok bilgisi meta etiketlerinde/metinde server-side render ediliyordu.
   Ama bu her JS-ağırlıklı site için garanti değildir — bazı sitelerde veri
   SADECE client-side JavaScript çalıştırıldıktan sonra DOM'a eklenir, bu
   durumda `requests`+`BeautifulSoup` hiçbir şey bulamaz (boş/eksik sonuç
   döner, hata fırlatmaz — bu yüzden her yeni site için `debug=True` ile
   gerçek bir denemeden sonuç almadan güvenmeyin).
2. **Metin örüntüsü kırılganlığı**: Sportive/Decathlon'un stok tespiti,
   sitenin o an kullandığı TÜRKÇE kelimeye ("Tükendi", "Stokta Mevcut")
   bağımlı. Site bu metni değiştirirse (örn. "Ürün Kalmadı" derse) tespit
   sessizce yanlış sonuç verebilir — bu regex'leri period bir kontrol
   etmek gerekir.
3. **Rate limiting / bot koruması**: Bu motorlar `requests` ile basit bir
   GET yapıyor; Cloudflare/bot koruması olan siteler 403/429 dönebilir.
   `http_utils.fetch_with_retry` sadece ağ hatalarını (timeout, bağlantı
   kopması) yeniden dener — bir 403/429'u "başarılı ama yanlış" olarak
   görebilir (bu durumda `response.raise_for_status()` zaten hata fırlatır
   ve retry devreye girer, ama sürekli 403 dönen bir site için 3 deneme de
   işe yaramaz).
4. **Sadece ayakkabı/beden odaklı**: `sizes` alanı beden bazlı ürünler için
   tasarlandı. Beden içermeyen ürünlerde (örn. aksesuar) `sizes: []` döner,
   `WatchService` (bu pakette yok, ana projede) bunu "beden bilgisi yok, fiyat
   yeterli" olarak güvenli şekilde ele alıyor — ama bu paketi tek başına
   kullanan biri kendi "beden yoksa ne olacak" mantığını yazmalı.

## Lisans / Kaynak

ShoeHunterAI projesi (Muharrem Gül) için 2026-07 içinde, Claude (Anthropic)
tarafından gerçek sayfa incelemesi yapılarak hazırlandı. Intersport motoru
kullanıcının önceki oturumlarda geliştirdiği koda dayanır; Sportive ve
Decathlon motorları bu oturumda sıfırdan, gerçek sayfa gözlemiyle yazıldı.
