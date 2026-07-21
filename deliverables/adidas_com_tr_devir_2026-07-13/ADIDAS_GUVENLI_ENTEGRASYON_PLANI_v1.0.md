# Adidas Güvenli Entegrasyon Planı v1.0

**Kısa çağırma adı:** `Adidas Güvenli Entegrasyon Planı v1.0`

**Daha sonra kullanılacak uygulama komutu:**

> Adidas Güvenli Entegrasyon Planı v1.0'ı uygulamaya geçir.

**Durum:** Denetim tamamlandı, uygulama yapılmadı.

**Tarih:** 13 Temmuz 2026

## 1. Amaç

Bu plan, `adidas.com.tr` entegrasyonunda yaşanan HTTP 403, yerel Playwright
`WinError 5`, canlı fiyatın okunamaması, beden/stok verisinin gelmemesi ve
sitemap başarısının gerçek ürün okuma başarısı gibi görünmesi sorunlarını,
mevcut çalışan sistemi bozmadan çözmek için hazırlanmıştır.

Plan, başka platformun sunduğu aşağıdaki çözüm paketi denetlendikten sonra
oluşturulmuştur:

- `Adidas_Cozum_Raporu.md`
- `adidas.py`
- `engines.py`
- `browser_runtime.py`
- `test_adidas_schema_robustness.py`
- `files.zip` SHA-256:
  `0DB13C022F37D1F1798B19BADD71F116AF10C1C3A191A58B099324E4A0B88111`

ZIP içindeki beş dosya, ayrı sağlanan dosyalarla SHA-256 düzeyinde birebir
aynıdır. Gizli veya farklı bir alt dosya bulunmamıştır.

## 2. Yönetici Sonucu

Önerilen çözümün mimari yönü kısmen doğrudur, fakat dosyalar mevcut halleriyle
uygulanmamalıdır.

Olumlu bölümler:

- JSON-LD `ProductGroup` verisini kök nesne dışında liste ve `@graph` içinde de
  arama fikri doğrudur.
- Tekil `Product` ve DOM fiyatı için ayrı `price_source` ve düşük güven değeri
  kullanılması doğru bir veri sınıflandırma yaklaşımıdır.
- `browser_wait_selector` alanının opt-in olması diğer mağazaların varsayılan
  davranışını korur.
- Bot korumasını atlatmaya yönelik proxy rotasyonu, CAPTCHA çözücü veya
  fingerprint sahteciliği eklenmemiştir.

Ancak çözüm şu haliyle:

- Mevcut ortamımızdaki HTTP 403 sorununu çözmez.
- Playwright'ın Windows'ta başlatılamadığı `WinError 5` sorununu çözmez.
- Gerçek beden veya stok verisinin yüklenmesini beklemez.
- Yanlış ürün veya önerilen ürün fiyatını ana fiyat olarak seçebilir.
- Geçerli bir `offers: [...]` JSON-LD yapısında parser'ı çökertebilir.
- Düşük güvenli yanlış fiyatın fiyat geçmişine ve yüzde 3 indirim alarmına
  girmesini engellemez.

## 3. Doğrulanan Test Sonuçları

Önerinin kendi belirttiği test grubu izole kopyada doğrulandı:

- 31 test geçti.

Önerilen üç kaynak dosyası gerçek backend'in geçici tam kopyasına uygulanarak
mevcut test takımımız da çalıştırıldı:

- 53 test geçti.
- 1 canlı mağaza testi varsayılan olarak devre dışı bırakıldı.
- Proje kaynak dosyalarında değişiklik yapılmadı.

Bu sonuçlar geriye dönük temel uyumluluğu gösterir; canlı Adidas erişiminin,
doğru fiyatın veya beden stoğunun çalıştığını göstermez.

Ek olumsuz senaryo testlerinde üç kusur doğrulandı:

1. Sayfada önerilen ürünün `5.999 TL` fiyatı gerçek `10.199 TL` fiyattan önce
   yer aldığında parser `5.999 TL` değerini seçti.
2. JSON-LD içinde önce başka ürün, sonra sayfanın gerçek ürünü olduğunda parser
   başka ürünün `2.999 TL` fiyatını seçti.
3. Bir varyantın `offers` alanı liste olduğunda parser
   `AttributeError: 'list' object has no attribute 'get'` hatasıyla durdu.

## 4. Kritik Bulgular

### P1 - Yanlış fiyat ve sahte alarm riski

Önerilen `_price_from_page_text()` şu genel seçiciyi kullanır:

```text
[class*='price']
```

BeautifulSoup bir elemanın kullanıcıya görünür olup olmadığını bilemez. Bu
seçici eski fiyatı, taksit tutarını, önerilen ürün fiyatını, gizli şablon
fiyatını veya başka bir ürün kartını seçebilir.

Tekil `Product` yedeğinde de bulunan ilk ürün kullanılmaktadır. Ürünün URL'si,
SKU/model kodu veya sayfanın kanonik URL'siyle eşleşme yapılmamaktadır.

Mevcut `services.py`, düşük güvenli fiyatı engellemez:

- Fiyat `last_price` olarak kaydedilir.
- Fiyat geçmişine girebilir.
- Önceki fiyata göre yüzde 3 veya daha fazla düşükse genel fiyat düşüş alarmı
  oluşturabilir.

Bu nedenle düşük `confidence` etiketi tek başına güvenlik sağlamaz.

### P1 - Geçerli offers listesinde çökme

Önerilen Adidas parser'ı `offers` alanını doğrudan sözlük kabul eder. JSON-LD
özellikleri tek değer veya liste biçiminde bulunabilir. Ortak `engines.py`
içinde sözlük ve listeyi işleyen `_first_offer()` yardımcısı zaten vardır;
Adidas parser'ı bunu kullanmalıdır.

### P1 - Ana erişim sorunu çözülmüyor

Önerilen `browser_runtime.py`, ana sayfa cevabı 400 veya üzerindeyse bekleme ve
parser başlamadan hata üretir. Bu nedenle HTTP 403 aynı şekilde devam eder.

Başka platformun kendi fetch altyapısıyla 200 cevabı alması, bizim bilgisayar,
IP, TLS/HTTP izi veya Playwright ortamımız için kanıt değildir. Aynı makinede
HTTP ve Playwright yolları ayrı ayrı ölçülmelidir.

`WinError 5`, uzaktaki Adidas cevabı değil yerel tarayıcı süreci/izin hatasıdır
ve ayrı çözülmelidir.

### P2 - Bekleme beden veya stok beklemiyor

Önerilen bekleme seçicisi JSON-LD veya fiyat elemanı beklemektedir:

```text
script[type='application/ld+json'], [data-testid*='price'], [class*='gl-price']
```

Fiyat sayfada zaten varsa, bedenler hâlâ placeholder durumundayken işlem devam
edebilir. Beden/stok için gerçek DOM seçicisi veya ilgili XHR/fetch cevabı
beklenmelidir.

Mevcut `networkidle` beklemesi en fazla 7 saniye, önerilen ek bekleme 5 saniye
olabilir. AI Arama ayrıntı zenginleştirmesi ise 14 saniyede kesilmektedir. Bu
süreler birlikte ele alınmazsa Adidas zenginleştirmesi daha sık zaman aşımına
uğrayabilir.

### P2 - Şema taraması tam derin tarama değil

`_find_product_nodes()` yalnız liste, `@graph`, `mainEntity`, `item` ve
`product` anahtarlarını dolaşmaktadır. Rastgele iç içe bir nesne veya farklı
şema sarmalayıcısı kaçabilir. Ayrıca ilk bulunan ürünün sayfanın ana ürünü
olduğu varsayılmaktadır.

### P3 - backup_service notu gerçek proje için geçerli değil

Çözüm raporu, devir ZIP'inde `backup_service.py` bulunmadığı için bazı testleri
çalıştıramadığını belirtmiştir. Bu dosya mevcut gerçek projemizde vardır. Bu
öneri uygulama görevi olarak kabul edilmemelidir; devir paketi bilinçli olarak
yalnız Adidas ile ilişkili dosyaları içeriyordu.

## 5. Güvenli Uygulama Planı

### Aşama 0 - Koruma noktası

1. Mevcut çalışma ağacındaki kullanıcı değişiklikleri korunur.
2. Uygulamadan önce yerel Git koruma commit'i veya açıkça adlandırılmış bir
   koruma dalı oluşturulur.
3. Mevcut test sonucu kaydedilir.
4. Gerçek `.env`, token ve veritabanı hiçbir test paketine kopyalanmaz.

### Aşama 1 - Aynı ortamda erişim teşhisi

Aynı Adidas URL'si aynı bilgisayarda şu yollarla ayrı ölçülür:

1. Mevcut güvenli `httpx` istemcisi.
2. Playwright Chromium.
3. AI Arama yolu.
4. Radar ayrıntı zenginleştirme yolu.

Her ölçümde şu alanlar kaydedilir:

- HTTP durumu.
- Son URL.
- Süre.
- Bot/challenge sınıfı.
- HTML boyutu.
- Fiyat bulundu mu?
- Beden/stok bulundu mu?
- Yerel süreç hatası mı, uzak sunucu hatası mı?

HTTP yolu çalışıyor ama Playwright çalışmıyorsa Adidas için doğrudan HTTP-first
stratejisi değerlendirilir. İki yol da 403 veriyorsa parser değişikliğinin bu
sorunu çözemeyeceği açıkça raporlanır.

### Aşama 2 - Güvenli JSON-LD parser

1. JSON-LD sözlük ve listeleri döngü/derinlik/adet sınırıyla genel olarak
   dolaşılır.
2. `ProductGroup` ana kaynak olarak tercih edilir.
3. `hasVariant` tek nesne veya liste olabilir.
4. `offers` sözlük, liste veya iç içe `AggregateOffer` olabilir.
5. Mevcut `_first_offer()` benzeri ortak yardımcı kullanılır.
6. Fiyat `float()` yerine mevcut yerel fiyat ayrıştırıcısıyla okunur.
7. Tekil `Product` yalnız aşağıdaki kanıtlardan biriyle sayfaya bağlanır:
   - Ürün URL'si mevcut/kanonik URL ile eşleşir.
   - SKU/model kodu URL'deki model koduyla eşleşir.
   - `mainEntity` olduğu açıkça belirtilmiştir ve çelişen ürün yoktur.
8. Eşleşmeyen önerilen ürünler, ürün listeleri ve aksesuarlar yok sayılır.
9. Stok yalnız bilinen availability değerlerinden üretilir; bilinmeyen durum
   otomatik olarak `out_of_stock` sayılmaz.

### Aşama 3 - DOM fiyat yedeği

1. Genel `[class*='price']` seçicisi kullanılmaz.
2. Ham, gizli bilgileri temizlenmiş gerçek Adidas HTML'i üzerinden ana ürün
   fiyat seçicisi belirlenir.
3. Eski fiyat, taksit, kampanya, önerilen ürün ve mini sepet alanları açıkça
   dışlanır.
4. Birden fazla çelişkili fiyat varsa sistem tahmin yapmaz; fiyat `None` kalır
   ve debug kanıtı kaydedilir.
5. DOM fiyatı JSON-LD veya iki tutarlı ardışık okumayla doğrulanmadan otomatik
   fiyat alarmına kaynak olmaz.

### Aşama 4 - Güven seviyesinin davranışa bağlanması

`confidence` yalnız görüntülenen bir sayı olmaktan çıkarılıp davranış kuralına
bağlanır:

- Doğrulanmış ProductGroup fiyatı normal güncelleme ve alarm akışına girebilir.
- URL/model koduyla eşleşmiş tekil Product fiyatı temkinli kabul edilir; stok
  kanıtı sayılmaz.
- DOM metninden bulunan düşük güvenli fiyat aday olarak saklanır; tek okumayla
  `last_price` değerini değiştirmez ve yüzde 3 alarmı üretmez.
- Manuel fiyat, canlı fiyat ve aday fiyat ayrı kaynak sınıfları olarak korunur.

Kesin eşikler uygulama sırasında mevcut kullanıcı deneyimi ve testlerle
birlikte belirlenir; temel kural düşük güvenli tek okumadan Telegram alarmı
üretmemektir.

### Aşama 5 - Beden/stok yüklenmesini bekleme

1. Arama sayfası ve ürün detay sayfası için ayrı bekleme politikası kullanılır.
2. Ürün detayında fiyat değil, gerçek beden seçeneği veya stok API cevabı
   beklenir.
3. Ham DOM'da güvenilir beden seçicisi yoksa Playwright response dinleyicisiyle
   ilgili XHR/fetch çağrısı tespit edilir.
4. Kullanım koşullarına uygun ve güvenli ise bu cevap parser'a kaynak yapılır.
5. Bekleme süresi AI Arama'nın 14 saniyelik zenginleştirme sınırıyla uyumlu
   hale getirilir.
6. Bekleme başarısızsa fiyat korunabilir, fakat beden/stok `unknown` kalır.

### Aşama 6 - Durum modelini ayırma

Tek bir `ok` alanı yerine en az şu ayrım yapılır:

- `discovery_status`: URL bulundu mu?
- `detail_status`: ürün sayfası okunabildi mi?
- `price_status`: fiyat doğrulandı mı?
- `stock_status`: beden/stok doğrulandı mı?

Sitemap ile URL bulunması, Adidas canlı ürün sayfasının başarıyla okunduğu
anlamına gelmemelidir.

### Aşama 7 - Test kapsamı

Mevcut pozitif testlere ek olarak şunlar zorunludur:

1. `ProductGroup` kök, liste, `@graph` ve iç içe nesne testleri.
2. `hasVariant` sözlük ve liste testleri.
3. `offers` sözlük, liste ve `AggregateOffer` testleri.
4. Sayfada önce önerilen ürün, sonra ana ürün bulunması.
5. Sayfada eski fiyatın güncel fiyattan önce bulunması.
6. Taksit tutarı ve kampanya fiyatı testleri.
7. Çelişkili DOM fiyatında `None` sonucu.
8. Düşük güvenli fiyatın yüzde 3 alarmı üretmemesi.
9. Beden yüklenmediğinde stok durumunun `unknown` kalması.
10. HTTP 403 ile yerel Playwright hatasının farklı sınıflandırılması.
11. Browser bekleme politikasının arama ve ürün detayında ayrı test edilmesi.
12. Opt-in canlı Adidas testi; varsayılan test takımında ağ erişimi kapalı kalır.

## 6. Kabul Kriterleri

Plan ancak aşağıdaki koşullar birlikte sağlanırsa tamamlanmış sayılır:

- Mevcut backend testlerinin tamamı geçer.
- Yeni olumsuz senaryo testlerinin tamamı geçer.
- Diğer mağaza motorlarının davranışı değişmez.
- Aynı makinede en az bir gerçek Adidas ürününde fiyat doğru okunur veya erişim
  engeli dürüstçe `blocked` olarak raporlanır.
- Yanlış/önerilen ürün fiyatı ana fiyat olarak seçilmez.
- Düşük güvenli tek DOM fiyatı fiyat düşüş alarmı üretmez.
- Beden verisi yoksa stokta/stok dışı uydurulmaz; `unknown` gösterilir.
- Sitemap başarısı ayrıntı başarısı gibi görünmez.
- Telegram'a doğrulanmamış fiyat veya stok bildirimi gönderilmez.
- Gerçek `.env`, token, cookie veya tarayıcı profili kaynak koda/test paketine
  girmez.

## 7. Uygulamada Değişmesi Beklenen Dosyalar

Dar parser düzeltmesi:

- `backend/stores/adidas.py`
- `backend/engines.py`
- `backend/browser_runtime.py`
- `backend/tests/test_adidas_schema_robustness.py`

Güvenli fiyat/alarm ve durum ayrımı için muhtemel ek dosyalar:

- `backend/services.py`
- `backend/server.py`
- `backend/store_health.py`
- `backend/browser_search.py`
- `backend/discovery_service.py`
- `frontend/src/pages/AISearch.jsx`
- `frontend/src/pages/ProductRadar.jsx`
- `frontend/src/pages/ProductDetail.jsx`

Bu liste uygulama sırasında mevcut kod bağımlılıkları yeniden okunarak daraltılır;
gereksiz refaktör yapılmaz.

## 8. Kapsam Dışı ve Yasak Yaklaşımlar

- CAPTCHA çözücü entegrasyonu.
- IP/proxy rotasyonuyla hız sınırı aşma.
- TLS veya tarayıcı fingerprint sahteciliği.
- İzinsiz cookie/oturum aktarımı.
- Robots veya kullanım koşullarını bilerek ihlal etme.
- Yanlış fiyatı yalnız düşük confidence etiketi koyarak üretimde kullanma.

En dayanıklı uzun vadeli çözüm resmi Adidas/affiliate ürün beslemesi veya izinli
API erişimidir. Scraping yolu kullanıldığında hız sınırı, devre kesici, güvenli
URL doğrulaması ve dürüst hata raporlama korunmalıdır.

## 9. Tekrar Çağırma Notu

Gelecekte aşağıdaki ifade bu belgedeki işi anlatır:

> Adidas Güvenli Entegrasyon Planı v1.0'ı uygulamaya geçir.

Bu komut verildiğinde önce bu dosya okunmalı, koruma noktası alınmalı, değişiklikler
aşamalı uygulanmalı ve her aşamadan sonra test edilmelidir. Dosyalar doğrudan
başka platformun önerdiği sürümlerle değiştirilmemelidir.
