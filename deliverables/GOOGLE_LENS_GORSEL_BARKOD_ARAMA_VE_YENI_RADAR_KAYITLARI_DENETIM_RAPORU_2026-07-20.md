# Google Lens Yaklaşımı, Görsel/Barkod Araması ve Yeni Radar Kayıtları Denetim Raporu

**Proje:** ShoeHunter / Ürün Radarı  
**Rapor tarihi:** 20 Temmuz 2026  
**Belge türü:** Teknik denetim, güncel uygulama kanıtı ve bütünleşik ürün/mobil yol haritası  
**Kapsam:** Resimden ve barkoddan ürün bulma, seçilebilir OCR, Google Lens/Shopping Graph uygulanabilirliği, `JR5220` ile `KC1948` Radar vakaları, 27 mağaza güvenilirliği, ürün–varyant–teklif modeli, toplam maliyet, satıcı güveni, mobil/offline/gizlilik, GS1/2D barkod ve uzun vadeli OmniHunter programı  
**Kanıt türleri:** Kaynak kod, otomatik test, MongoDB çalışma kayıtları, standart tarayıcı denemesi ve resmî ürün/API belgeleri  
**Önemli sınır:** Google Lens'in tam sıralama modeli ve Shopping Graph altyapısı kapalı/proprietary sistemlerdir. Bu raporda Lens'in kamuya açıklanan davranışı ile projede uygulanabilir mühendislik karşılığı birbirinden ayrılmıştır.

## 1. Yönetici özeti

`TRAIL RUNNING JR5220` kaydında fotoğraf okuma başarısız olmamıştır. Sistem etiketten:

- ürün kodu `JR5220`,
- EAN/GTIN `4067904494690`,
- sınıf açıklaması `TRAIL RUNNING`,
- ayakkabı kategorisi ve seçilen numarayı

çıkarmış ve kaydetmiştir. İlk sorun, bu doğru kimlik parçalarının geçmişte yalnızca tek bir ham metin aramasına dönüştürülmesi ve 27 mağazadan 25'inin o çalışmada devre kesici nedeniyle hiç aranmamasıdır. Bu yüzden kullanıcı açısından “kod alındı ama tarama yapılmadı” gözlemi haklıdır.

Denetim sırasında arama zinciri kod/barkod öncelikli hale getirildi. Güncel arama planı artık sırasıyla tam ürün kodunu, barkodu, marka+ürün kodunu, zenginleştirilmiş adları ve en son ham OCR metnini dener. Her mağazanın hangi sorguyu denediği ve kaç sonuç verdiği de çalışma kaydına ve Radar arayüzüne taşınmıştır.

Canlı `JR5220` karşılaştırması:

| Ölçüm | İlk sorunlu çalışma | Düzeltme sonrası çalışma |
|---|---:|---:|
| Seçili mağaza | 27 | 27 |
| Başarıyla çalışan mağaza | 2 | 22 |
| Ertelenen mağaza | 25 | 5 |
| Başarısız mağaza | 0 | 0 |
| Gerçek kapsama | %7,4 | %81,5 |
| Çalışma durumu | Yanıltıcı biçimde `completed` | Doğru biçimde `partial` |

Düzeltme sonrası 39 genel “trail running” adayı oluşması ikinci bir sorunu ortaya çıkardı: bunların önemli bölümü `JR5220` değildi. Bunun üzerine eşleştirme sıkılaştırıldı; adayda farklı bir açık model kodu varsa veya marka çelişiyorsa genel başlık benzerliği artık ürünü kabul ettiremiyor. Tam kod/GTIN kanıtı yoksa fiyat ve link otomatik olarak kesin sonuç sayılmıyor.

`KC1948` kaydında da etiket analizi doğru çalışmış; `Adidas`, `KC1948` ve `4068819685753` kaydedilmiştir. Eski çalışma, yanlış proxy ortamı ve tarayıcı başlatma izin hataları yüzünden çok sayıda mağazaya ulaşamamıştır. Güncel tekrar taramasında 18/27 mağaza başarıyla çalışmış; resmî adidas sayfası, Korayspor ve iki n11 ilanı tam `KC1948` kanıtıyla bağlanmıştır. Bu sonuç eski “bulunamadı” kaydının ürün yokluğundan değil tarama ortamından kaynaklandığını doğrulamıştır.

Sonuç olarak Google Lens'in karar yaklaşımının önemli bölümü projeye uygulanabilir:

1. görüntüden barkod, metin, logo/marka, renk ve ürün biçimi çıkarma;
2. bu kanıtları tek ürün kimliğinde birleştirme;
3. GTIN ve model kodunu en güçlü arama anahtarı yapma;
4. aynı ürünü farklı mağaza ilanları altında kümeleme;
5. fiyat, stok ve linki kaynak sayfasında ayrıca doğrulama.

Ancak Lens'in tüm interneti kapsayan görsel indeksi ve Shopping Graph verisi kamuya açık genel bir API olarak sunulmuyor. Bu nedenle birebir Lens kopyası değil; ücretsiz yerel OCR/barkod, kendi mağaza motorlarımız, giderek büyüyen kendi ürün görseli dizinimiz ve isteğe bağlı resmî ücretli web-görsel servislerinden oluşan hibrit bir sistem kurulmalıdır.

## 2. Google Lens gerçekte hangi problemi çözüyor?

Lens'i yalnızca bir OCR veya barkod okuyucu olarak değerlendirmek eksiktir. Kamuya açık ürün açıklamalarından görülen genel yapı üç katmandır:

1. **Algılama:** Görselde ürün bölgesini, yazıyı, logoyu, barkodu, rengi ve biçimi algılar.
2. **Kimlik çözümleme:** Görsel/metin kanıtlarını marka, model, varyant ve GTIN gibi katalog kimliklerine bağlar.
3. **Piyasa eşleme:** Çözülen kimliği Google'ın ürün ve satıcı verileriyle ilişkilendirerek mağaza, fiyat ve bağlantı sonuçları üretir.

Barkoddan iyi fiyat bulmasının nedeni yalnızca çizgileri iyi okuması değildir. Barkod okuma işlemi `4067904494690` sayısını üretir; fiyat bulma ise bu GTIN'i ürün katalogları ve satıcı sayfalarıyla eşleştiren ayrı bir veri problemidir. Lens'in üstünlüğü bu iki adımı büyük bir ürün grafiğiyle birleştirmesidir.

Google'ın tam model ayrıntıları kamuya açık değildir. Bu nedenle “Lens kesin olarak şu puanlama formülünü kullanıyor” denemez. Bize uygulanabilecek olan, gözlenen karar ilkeleridir: önce kesin kimlik, sonra metin/görsel benzerliği, sonra satıcı doğrulaması.

## 3. Bizim mevcut bulma algoritmamız

### 3.1 Fotoğraf ve etiket analizi

`backend/label_scan.py` fotoğrafı şu sırayla işler:

1. JPG, PNG veya WebP dosyasını doğrular ve EXIF yönünü düzeltir.
2. ZXing ile EAN, UPC, Code 128, QR ve desteklenen diğer kodları çözmeye çalışır.
3. RapidOCR + ONNX Runtime ile metni yerel sunucuda okur.
4. Düşük yön güveninde görseli 90° ve 270° döndürerek ek OCR denemesi yapar.
5. Marka, ürün kodu, GTIN, ürün adı, kategori, beden/numara, renk ve fiyat adayları çıkarır.
6. OCR kutularını orijinal fotoğrafa göre normalize eder; kullanıcı ekranda hangi metnin seçildiğini görebilir ve yanlış satırı dışarıda bırakabilir.
7. Kullanıcı onayından sonra Radar kaydı oluşturur.

Bu aşamanın güçlü tarafları:

- ücretli OCR API'si gerektirmemesi;
- fotoğrafın varsayılan olarak kendi sunucumuzda işlenmesi;
- barkod ile OCR tahminini ayrı güven düzeylerinde tutması;
- döndürülmüş etiketlerde de yazı kutularını görsele geri eşleyebilmesi.

Bu aşamanın mevcut sınırı: Fotoğrafın genel görünümünden internet çapında benzer ürün araması yapılmıyor. Yani etiketsiz bir ayakkabı fotoğrafı için şu anda Google Lens kadar geniş bir tersine görsel arama yoktur.

### 3.2 Güncel arama planı

Onaylanan Radar kaydı artık tek sorguya bağlı değildir. `backend/search_query_plan.py` kanıtları şu öncelikle planlar:

```text
1. Tam ürün/stil kodu
2. Tam barkod / GTIN
3. Marka + ürün kodu
4. Zenginleştirilmiş marka + model + kod adları
5. Kullanıcının/OCR'nin ham sorgusu
```

`JR5220` için veritabanında görülen güncel plan:

```text
JR5220                 [product_code, kesin kimlik]
4067904494690          [barcode, kesin kimlik]
TRAIL RUNNING JR5220   [raw_query, geniş geri dönüş]
```

Marka zenginleştirmesi mevcut olduğunda araya `Adidas JR5220` ve `Adidas Terrex Agravic Speed JR5220` gibi sorgular girer. Plan tekrarları temizler ve mağaza başına en fazla sekiz anlamlı sorgu üretir.

### 3.3 Mağaza ve aday değerlendirme akışı

Her seçili mağazada:

1. mağazanın normal arama/katalog yöntemi denenir;
2. erişim engeli veya boş sonuç varsa robots kurallarına uygun katalog/site haritası geri dönüşleri denenir;
3. kesin ürün kodu için desteklenen resmî ürün rotası denenir;
4. bulunan adayın GTIN'i, model kodu, markası, başlığı, URL'si ve kategori sinyalleri çıkarılır;
5. ürün kimliği uyuşmuyorsa aday reddedilir;
6. eşleşme yeterliyse ürün sayfasından fiyat, stok ve varyant kanıtı doğrulanır;
7. doğrulanamayan resmî kod rotası “inceleme gerekli” olarak tutulur, otomatik kesin fiyat sayılmaz.

Güncel karar hiyerarşisi:

| Kanıt | Güç | Karar etkisi |
|---|---|---|
| Aynı geçerli GTIN/EAN | Çok yüksek | Aynı ürün için en güçlü kanıt |
| Aynı açık model/stil kodu | Çok yüksek | Marka/kategori uyumuyla güçlü eşleşme |
| Farklı açık alfanümerik model kodu | Çelişki | Genel başlık benzerliğine rağmen reddet |
| Marka çelişkisi | Çelişki | Kesin kod/GTIN yoksa reddet |
| Marka + model adı + kategori | Orta/yüksek | İnceleme veya doğrulama adayı |
| Yalnız “trail running” gibi genel kelimeler | Düşük | Tek başına ürün eşleşmesi sayılmaz |
| Görsel benzerlik | Henüz yok | Gelecek yerel görsel dizin aşaması |

## 4. `TRAIL RUNNING JR5220` vaka analizi

### 4.1 Etiketten çıkarılan gerçek kayıt

| Alan | Değer |
|---|---|
| Radar kimliği | `4d47888c-fddd-48e1-a62b-1344a0999c5d` |
| Ham metin | `TRAIL RUNNING JR5220` |
| Kaynak | `label_scan` |
| Ürün kodu | `JR5220` |
| Barkod | `4067904494690` |
| Model alanı | `JR5220` |
| Marka | İlk kayıtta boş |
| Kategori | `shoes` |
| Mağaza kapsamı | 27 mağaza |

Bu kayıt “yalnız ürün özel kodunu aldı” şeklinde görünse de barkod veritabanında mevcuttur. Hata barkodu okuyamamak değil, geçmiş taramada barkodu bağımsız arama ve kimlik çözümleme anahtarı olarak yeterince kullanmamaktı.

### 4.2 İlk çalışmanın neden sonuç üretmediği

İlk kayıt dönemindeki en açıklayıcı çalışma 27 mağazanın yalnızca ikisini `ok`, 25'ini `deferred` olarak kaydetmiştir. ASICS ve Columbia çalışan iki mağazadır; bunların adidas ürünü döndürmemesi normaldir. adidas, FLO, pazar yerleri ve ilgili spor mağazaları fiilen aranmamıştır.

Üstelik bu kısmi çalışma eski mantıkta `completed` görünüyordu. Arayüz, “27 mağaza tarandı ve bulunamadı” ile “yalnız 2 mağaza çalıştı” durumlarını ayıramıyordu. Kullanıcının tarama yapılmadığını düşünmesinin ana nedeni budur.

### 4.3 Kök nedenler

| Kök neden | Etki | Düzeltme |
|---|---|---|
| Tek ham metin sorgusu | Güçlü `JR5220` ve GTIN kanıtı kayboluyordu | Kimlik öncelikli çoklu sorgu planı |
| `not_found` gibi doğal boş sonuçların hata sayılması | Mağaza devreleri gereksiz açılıyordu | Yalnız gerçek hata/blok/timeout/parser arızası devreyi yükseltiyor |
| Altı saate kadar açık kalan devre | Yeni ürünler ilgili mağazalara ulaşamıyordu | Hata türüne göre 5–120 dakikalık sınırlı bekleme |
| Ortamdan gelen `127.0.0.1:9` proxy değeri | Normal HTTP istekleri sahte ağ hatası veriyordu | Mağaza istemcilerinde ortam proxy'si varsayılan olarak kapatıldı |
| Kısıtlı süreçte tarayıcı başlatma hatası (`WinError 5`) | Dinamik mağaza motorları çalışmıyordu | Gerçek çalışma servisi uygun izinli süreçte çalıştırıldı; hata sınıfı ayrıştırıldı |
| Kısmi taramanın `completed` görünmesi | Kullanıcı yanlış kapsama güveniyordu | `partial/deferred/failed` ve kapsama yüzdesi eklendi |
| Genel başlık benzerliği | Başka model kodlu trail ürünleri incelemeye düşüyordu | Çelişen model kodu ve marka için kesin ret |
| Sağlık güncellemesinde Mongo `last_error` çakışması | Bazı tanı koşuları `failed` oluyordu | Aynı alanın eşzamanlı set/unset güncellemesi kaldırıldı |

### 4.4 Düzeltme sonrası canlı sonuç

Canlı tanı çalışması `77704e85-cba6-4d16-8bf9-e431810ea5d9` şu sonucu üretmiştir:

- durum: `partial`;
- seçili mağaza: 27;
- başarıyla çalışan: 22;
- ertelenen: 5;
- gerçek hata: 0;
- kapsama: `%81,5`;
- arama planı: `JR5220` → `4067904494690` → `TRAIL RUNNING JR5220`;
- sonuç döndüren kaynaklar: adidas geri dönüş katmanı, Intersport, Barçın, Sneaks Up ve n11;
- ertelenenler: Decathlon, Yalı Spor, Kutupayısı, Hepsiburada ve Amazon.

Bu çalışma erişim kapsamının düzeldiğini kanıtlar; fakat oluşan 39 inceleme adayının tamamı `JR5220` değildir. Çoğu geniş `TRAIL RUNNING` sorgusundan gelmiştir. Bu nedenle sayı başarı ölçütü olarak kullanılmamalıdır. Çelişen açık model kodlarını reddeden yeni kimlik kuralı bu canlı koşudan sonra eklendi ve otomatik testlerle doğrulandı.

Mevcut 40 aday yeni kuralla tekrar sınıflandırıldığında 25'i reddedilmiş, 15'i yalnız kullanıcı incelemesinde bırakılmış ve hiçbiri otomatik kesin eşleşme yapılmamıştır. İncelemede kalanlar genel trail/model adı benzerliği taşısa da `JR5220` kodunu kanıtlamaz; fiyat sonucu olarak kullanılmamalıdır.

### 4.5 Ürünün dış kanıtı

Normal kullanıcı tarayıcısında `https://www.adidas.com.tr/en/JR5220.html` adresi resmî kanonik ürüne yönlenmiştir:

- **adidas Terrex Agravic Speed Trail Running Shoes**;
- ürün kodu `JR5220`;
- denetim anındaki sayfa fiyatı `4.399 TL`;
- önceki fiyat `7.999 TL`.

[Resmî adidas Türkiye ürün sayfası](https://www.adidas.com.tr/en/terrex-agravic-speed-trail-running-shoes/JR5220.html)

Standart otomasyon isteği adidas aramasında HTTP 403 alırken normal kullanıcı tarayıcısı bu kesin ürün rotasını açabilmiştir. Sistem bu durumda korumayı atlatmamalı; resmî kod rotasını “sayfa doğrulaması gerekli” işaretiyle kullanıcı incelemesine sunmalıdır. Fiyat, beden ve stok otomatik doğrulanmadan kesin fırsat bildirimi üretilmemelidir.

## 5. İkinci yeni kayıt `KC1948` vaka analizi

| Alan | Değer |
|---|---|
| Radar kimliği | `2d855960-b164-44f8-9273-c993f63ed625` |
| Ham metin | `Adidas JZ.N.E.FZ TRACK TOPS KC1948` |
| Kaynak | `label_scan` |
| Marka | `Adidas` |
| Ürün kodu | `KC1948` |
| Barkod | `4068819685753` |
| Kategori | `outerwear` |

Bu kayıt JR5220'den daha zengin okunmuştur: marka, ürün kodu ve barkod birlikte mevcuttur. Güncel sorgu planı da doğru üretilmektedir:

```text
KC1948
4068819685753
Adidas KC1948
Adidas JZ.N.E.FZ TRACK TOPS KC1948
```

Veritabanındaki düzeltme öncesi özet:

- seçili mağaza: 27;
- aranmış sayılan mağaza: 16;
- başarılı mağaza: 2;
- ertelenen mağaza: 11;
- hata veren mağaza: 14;
- kapsama: `%59,3`;
- otomatik/inceleme sonucu: 0.

Hataların çoğu `All connection attempts failed` ve `WinError 5` sınıfındadır. Bunlar ürünün yokluğunu değil, o çalışmadaki ortam ve tarayıcı süreç sorununu gösterir.

Güncel motorla yapılan canlı tanı çalışması `e5a5b114-e411-476c-98dc-c575ada665a5` şu sonucu üretmiştir:

- durum: `partial`;
- seçili mağaza: 27;
- başarıyla çalışan: 18;
- ertelenen: 9;
- gerçek hata: 0;
- kapsama: `%66,7`;
- otomatik bağlanan kesin eşleşme: 4;
- inceleme adayı: 1;
- reddedilen yanlış/genel aday: 64;
- yeni bağlı ilan: 4.

Tam ürün koduyla bağlanan kaynaklar:

| Kaynak | Sonuç | Kanıt |
|---|---|---|
| adidas Türkiye | Kanonik ürün sayfası otomatik bağlandı | `exact_identifier:KC1948` |
| Korayspor | 1 ilan otomatik bağlandı | Başlık ve URL'de `KC1948` |
| n11 | 2 ilan otomatik bağlandı | Başlık ve URL'de `KC1948` |
| adidas kısa resmî rota | İncelemeye bırakıldı | Kod doğru; otomatik sayfa doğrulaması gerekli |

Fiyat alanları bu tanı çalışmasında doğrulanmadığı için bağlanan dört ilan “kesin fiyat bulundu” anlamına gelmez. Sistem ürün kimliğini bağlamış, fiyat/stok doğrulamasını ayrı aşamaya bırakmıştır. Bu ayrım Lens benzeri güvenilirlik için doğrudur.

Ürün kodunun resmî adidas ve perakende sayfalarında bulunması da sonucu destekler:

- [Resmî adidas Türkiye KC1948 sayfası](https://www.adidas.com.tr/en/adidas-z.n.e.-full-zip-hooded-track-jacket/KC1948.html)
- [FLO KC1948 ürün sayfası](https://www.flo.com.tr/urun/adidas-cocuk-mavi-ceket-j-znefz-kc1948-201762585)

Bu vaka için doğru yorum şudur: etiket tanıma ve sorgu planı başarılıdır; eski piyasa taraması güvenilir kapsama ulaşamamıştır; güncel tarama ise kod öncelikli yaklaşımın ürünü bulduğunu ve genel adayların büyük çoğunluğunu reddettiğini kanıtlamıştır.

## 6. Lens yaklaşımını bize nasıl uygularız?

### 6.1 Önerilen hedef mimari

```text
Kamera / galeri / barkod
        ↓
Yerel barkod + OCR + seçilebilir metin kutuları
        ↓
Ürün kimlik grafiği
GTIN ─ ürün kodu ─ marka ─ model ─ kategori ─ renk/varyant
        ↓
Kimlik öncelikli sorgu planı
        ↓
Mağaza motorları + resmî ürün rotaları + katalog/site haritası
        ↓
Kesin kimlik filtresi
        ↓
Ürün sayfası fiyat/stok/beden doğrulaması
        ↓
Aynı ürün altında satıcı, fiyat, link ve kanıt zamanı
```

### 6.2 Kimlik varken izlenecek yol

Barkod veya ürün kodu bulunduğunda pahalı görsel arama ilk adım olmamalıdır:

1. GTIN biçim ve kontrol hanesi doğrulanır.
2. Ürün kodu marka kalıbına göre normalize edilir.
3. Tam kod ve GTIN bütün mağazalarda ayrı sorgulanır.
4. Resmî marka sayfası kimliği zenginleştirmek için kullanılır.
5. Bulunan ilanlarda aynı kod/GTIN kanıtı aranır.
6. Aynı ürün farklı renk/varyant ise ayrı varyant olarak tutulur.

Bu yaklaşım Lens'in barkod aramalarındaki en değerli davranışını düşük maliyetle taklit eder.

### 6.3 Kimlik yoksa görsel arama

Etiketsiz veya okunamayan görseller için ikinci hat kurulmalıdır:

1. Kullanıcı fotoğrafta ürünü kırpar veya otomatik ürün bölgesi seçilir.
2. Logo/marka ve kategori tahmini yapılır.
3. OpenCLIP benzeri modelle görsel embedding çıkarılır.
4. Kendi mağaza taramalarımızdan toplanan ürün görselleri Qdrant, FAISS veya PostgreSQL/pgvector dizininde aranır.
5. En yakın görsel adaylarının başlık ve ürün kodları yeniden metin/kimlik filtresinden geçirilir.
6. Yalnız görsel benzerliğe dayanan sonuç “benzer ürün” olarak gösterilir; “aynı ürün” denmesi için kod, GTIN veya güçlü katalog kanıtı gerekir.

Bu yöntem ücretsiz ve kontrol edilebilir bir çekirdek sağlar. Başlangıçta yalnız kendi katalog kapsamımız kadar güçlü olur; zaman içinde mağaza görselleri biriktikçe iyileşir.

### 6.4 İsteğe bağlı dış kaynaklar

| Seçenek | Ne sağlar? | Ne sağlamaz? | Karar |
|---|---|---|---|
| Google ML Kit Barcode Scanning | Cihazda hızlı barkod okuma | Fiyat/satıcı verisi | Mobil çekirdekte kullanıldı |
| Google ML Kit Text Recognition | Cihazda OCR | İnternet çapında ürün eşleme | Tam yerel mobil OCR için uygun |
| Cloud Vision Web Detection | Webde eşleşen/benzer görsel ve sayfa ipuçları | Doğrulanmış canlı fiyat/stok garantisi | İsteğe bağlı ücretli geri dönüş |
| Vision Product Search | Yüklediğimiz kendi katalogda görsel arama | Tüm interneti/Lens'i aramaz | Kendi katalog büyürse değerlendirilebilir |
| Merchant API | Yetkili olduğumuz Merchant Center ürünlerini yönetir | Rakip mağazaların genel fiyat API'si değildir | Piyasa araması için uygun değil |
| GS1 Digital Link / Verified by GS1 | GTIN kimlik güveni ve çözümleme standardı | Mağaza fiyat karşılaştırması | Kimlik doğrulamada yararlı |

### 6.5 Google Shopping Graph API gerçeği

İncelenen resmî belgelerde “bir GTIN gönder, internetteki bütün satıcı ve fiyatları döndür” biçiminde genel kullanıma açık bir Shopping Graph/Lens API'si bulunmamaktadır. Merchant API, kullanıcının yetkili olduğu Merchant Center kaynaklarını yönetir; genel piyasa araması değildir.

Ayrıca yeni bir çekirdeği eski Google Content API for Shopping veya Custom Search JSON API üzerine kurmak doğru değildir:

- Content API for Shopping için kapanış tarihi 18 Ağustos 2026'dır; yeni geliştirme Merchant API'ye yönlendirilmiştir.
- Custom Search JSON API yeni müşterilere kapalıdır ve mevcut müşteriler için geçiş takvimi duyurulmuştur.

Bu nedenle projenin temel araması kendi mağaza motorları ve kendi görsel/ürün dizini üzerinde kalmalıdır.

## 7. Mobil uygulamada uygulanmış bölüm

Test APK'sında Android'in resmî Google Code Scanner arayüzü eklendi. Kullanıcı uygulama araç çubuğundaki barkod düğmesiyle EAN/UPC/Code 128/QR/Data Matrix okuyabilir. Sonuç Radar ekranındaki kesin kimlik alanına aktarılır.

Web tabanlı fotoğraf akışında:

- fotoğraf çekme veya galeriden seçme;
- sunucuda yerel OCR/barkod çözme;
- OCR kutularını fotoğraf üzerinde gösterme;
- seçilen metin satırlarıyla arama oluşturma;
- numara/beden profilini koruma

mevcuttur.

Tam Lens benzeri mobil deneyim için sonraki adım, ML Kit Text Recognition'ı da doğrudan Android tarafına ekleyip OCR kutularını canlı kamera ön izlemesi üzerinde seçilebilir hale getirmektir. Bu yapılana kadar fotoğraf OCR'si sunucuda, doğrudan barkod okuma cihazda çalışır.

Test APK'sı:

`mobile/dist/ShoeHunter-Radar-0.1.0-test.apk`

- boyut: `1.494.791` bayt;
- SHA-256: `C82197227B271D4529743CD546B86EACB6B1286B4A1492F4C97309F29968768C`.

## 8. Kullanıcı ekranında gösterilmesi gereken kanıtlar

Radar sonucu yalnız “bulundu/bulunamadı” dememelidir. Her çalışma için şu bilgiler görünmelidir:

- seçili, gerçekten aranan, başarılı, ertelenen ve hata veren mağaza sayısı;
- kapsama yüzdesi;
- mağaza bazında denenen sorgular;
- sonucu getiren sorgu türü: barkod, ürün kodu, marka+kod, zengin ad veya ham metin;
- eşleşme kanıtı: aynı GTIN, aynı ürün kodu, başlık benzerliği veya yalnız görsel benzerlik;
- fiyat/stok doğrulamasının zamanı;
- “resmî link bulundu fakat sayfa otomatik doğrulanamadı” uyarısı;
- “aynı ürün” ile “benzer ürün” ayrımı.

Bu alanların önemli bölümü güncel Radar ekranına eklenmiştir: sorgu planı, mağaza kapsamı, ertelenen/hatalı mağazalar, sorgu denemeleri, OCR kutu seçimi ve doğrulama gerekli rozeti.

## 9. Güvenilir sonuç için kabul kuralları

### Aynı ürün olarak otomatik kabul

Aşağıdakilerden en az biri ve marka/kategori uyumu bulunmalıdır:

- doğrulanmış aynı GTIN;
- aynı açık üretici model/stil kodu;
- resmî marka sayfasından kanonik yönlendirme + aynı kod.

### Kullanıcı incelemesine gönder

- marka ve model adı güçlü fakat kod görünmüyor;
- resmî kod rotası var fakat fiyat/stok sayfası otomatik okunamadı;
- kod OCR'den geliyor fakat barkod çözümüyle doğrulanmadı;
- çok güçlü görsel benzerlik var fakat katalog kimliği eksik.

### Reddet

- farklı açık alfanümerik model kodu;
- kesin kimlik yokken marka çelişkisi;
- yalnız genel kategori kelimeleri eşleşiyor;
- ürün yerine kategori/kampanya/listeme sayfası bulunmuş;
- fiyat ve link aynı ürüne ait olduğunu kanıtlamıyor.

## 10. Test ve doğrulama özeti

| Kontrol | Sonuç |
|---|---|
| Arka uç otomatik testleri | `184 passed, 1 skipped` |
| Ön yüz otomatik testleri | `20 passed` |
| Ön yüz üretim derlemesi | Başarılı |
| Android APK derlemesi | Başarılı |
| Yerel arka uç sağlık kontrolü | HTTP 200, veritabanı bağlı, sürüm 0.6.0 |
| Yerel ön yüz | HTTP 200 |
| adidas kesin `JR5220` rotası | Normal tarayıcıda kanonik ürün sayfasına yönlendi |
| adidas standart otomasyon araması | HTTP 403; koruma atlatılmadı |
| `JR5220` canlı mağaza kapsamı | 22/27, `%81,5`, doğru `partial` durumu |
| `KC1948` canlı mağaza kapsamı | 18/27, `%66,7`, 4 kesin eşleşme, 64 yanlış aday reddi |

Atlanan tek arka uç testi ortam koşuluna bağlıdır. Uyarılar FastAPI/Starlette bağımlılıklarının gelecekte kaldırılacak API'leri ve pytest önbellek izin durumuyla ilgilidir; test başarısızlığı değildir.

## 11. Öncelikli yol haritası

### P0 — Doğru kimlik ve güvenilir sonuç

- Ürün kodu/GTIN öncelikli sorgu planını bütün Radar girişlerinde kullan.
- Kayıt oluşturulurken marka boşsa ürün kodundan kontrollü marka zenginleştirmesi yap.
- Çelişen model kodunu kesin ret olarak uygula.
- Kısmi çalışma ve mağaza kapsamını kullanıcıya göster.
- Fiyat/stok doğrulanmadıysa kesin fırsat bildirimi üretme.

### P1 — Lens benzeri kendi görsel dizinimiz

- Mağaza ilanı görselleri için içerik özeti ve tekrar temizliği.
- OpenCLIP embedding üretimi.
- Qdrant/pgvector/FAISS yakın komşu araması.
- “aynı ürün” ve “benzer ürün” için ayrı eşik ve ekran sınıfı.
- Ürün görseli, kutu etiketi, ayakkabı dili ve fiyat etiketi fotoğraflarını farklı rollerle birleştirme.

### P2 — Mobil tam kamera deneyimi

- Android'de doğrudan ML Kit Text Recognition.
- Canlı OCR kutu seçimi ve yeniden çekim yönlendirmesi.
- Bir ürün için çoklu fotoğraf oturumu.
- Çevrimdışı barkod/OCR sonucunu bağlantı gelince Radar'a gönderme.

### P3 — İsteğe bağlı haricî web-görsel geri dönüşü

- Yalnız yerel kimlik ve katalog araması sonuçsuz kaldığında Cloud Vision Web Detection benzeri resmî servis.
- Haricî sonuçları kesin fiyat saymadan önce mağaza motoruyla doğrulama.
- Maliyet limiti, gizlilik onayı ve kaynak kanıtı.

## 12. Başarı ölçütleri

Sistemin Lens benzeri yönde gerçekten geliştiğini aşağıdaki ölçüler gösterecektir:

- geçerli barkodlu girişlerde ürün kimliği bulma oranı;
- tam ürün kodlu girişlerde resmî sayfa bulma oranı;
- 27 mağazalık çalışmada gerçek kapsama yüzdesi;
- yanlış “aynı ürün” oranı;
- fiyatı ve stoğu son 6 saat içinde doğrulanmış sonuç oranı;
- kullanıcı incelemesinden otomatik kabul/ret kurallarına taşınan sonuç oranı;
- etiketsiz fotoğraflarda ilk 5 görsel aday içinde doğru ürün oranı;
- arama sonucunun hangi kanıtla bulunduğunun ekranda açıklanma oranı.

Önerilen ilk kalite hedefi yanlış eşleşmeyi azaltmaktır. Çok sayıda genel aday göstermek, doğru ürünü kod/GTIN ile bulmaktan daha değerli değildir.

## 13. Nihai değerlendirme

`JR5220` ve `KC1948` vakalarında temel problem fotoğrafın okunmaması değildir. Etiketlerden güçlü ürün kimlikleri çıkarılmıştır. Sorun, bu kimliklerin geçmişte mağaza aramasına doğru sırada taşınmaması, mağaza devrelerinin gerçek olmayan ortam hatalarıyla açık kalması ve kısmi çalışmanın kullanıcıya açıklanmamasıdır.

Güncel yapı barkod ve ürün kodunu artık arama zincirinin merkezine alır; mağaza bazında sorgu denemelerini kaydeder; kısmi kapsamı doğru gösterir ve farklı model kodlu genel ürünleri reddeder. Bu, Lens'in barkod/ürün kodundan piyasa bulma davranışının projeye uygulanabilen en önemli kısmıdır.

Henüz eksik kalan bölüm, etiketsiz bir ürün fotoğrafını bütün internet çapında arayan küresel görsel indekstir. Bunu Google'ın kapalı Lens/Shopping Graph altyapısını kopyalayarak değil; kendi mağaza verimizden oluşan OpenCLIP tabanlı görsel dizin, resmî mağaza doğrulaması ve yalnız gerektiğinde haricî resmî görsel-web servisi kullanarak çözmek en sürdürülebilir yoldur.

## 14. Kaynaklar

### Google ve Android resmî belgeleri

- [Google Lens ile görsel alışveriş yaklaşımı](https://blog.google/products-and-platforms/products/shopping/visual-search-lens-shopping/)
- [ML Kit Barcode Scanning for Android](https://developers.google.com/ml-kit/vision/barcode-scanning/android)
- [Google Code Scanner](https://developers.google.com/ml-kit/vision/barcode-scanning/code-scanner)
- [ML Kit Text Recognition v2](https://developers.google.com/ml-kit/vision/text-recognition/v2/android)
- [Cloud Vision Web Detection](https://cloud.google.com/vision/docs/detecting-web)
- [Vision Product Search](https://cloud.google.com/vision/product-search/docs)
- [Merchant API ürün yönetimi](https://developers.google.com/merchant/api/guides/products/add-manage)
- [Content API for Shopping geçiş bilgisi](https://developers.google.com/shopping-content/guides/quickstart)
- [Custom Search JSON API genel bakış](https://developers.google.com/custom-search/v1/overview)

### Kimlik standartları

- [GS1 Digital Link standardı](https://www.gs1.org/standards/gs1-digital-link)
- [GS1 Resolver standardı](https://www.gs1.org/standards/resolver)

### Açık kaynak teknik seçenekler

- [ZXing barkod kütüphanesi](https://github.com/zxing/zxing)
- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)
- [OpenCLIP](https://github.com/mlfoundations/open_clip)
- [clip-retrieval](https://github.com/rom1504/clip-retrieval)
- [FAISS](https://github.com/facebookresearch/faiss)
- [Qdrant](https://github.com/qdrant/qdrant)
- [pgvector](https://github.com/pgvector/pgvector)
- [GS1 digital-link.js](https://github.com/gs1/digital-link.js/)

### İncelenen ürün kanıtları

- [adidas Türkiye — JR5220](https://www.adidas.com.tr/en/terrex-agravic-speed-trail-running-shoes/JR5220.html)
- [adidas Türkiye — KC1948](https://www.adidas.com.tr/en/adidas-z.n.e.-full-zip-hooded-track-jacket/KC1948.html)
- [FLO — KC1948](https://www.flo.com.tr/urun/adidas-cocuk-mavi-ceket-j-znefz-kc1948-201762585)

## 15. Önceki OmniHunter raporuyla birleştirilmiş karar

Bu bölüm, 13 Temmuz 2026 tarihli `OMNIHUNTER_BUTUNLESIK_VIZYON_HEDEFLER_VE_UYGULAMA_PLANI.md` belgesindeki geniş ürün hedeflerini bu denetimin canlı kanıtlarıyla günceller. Önceki belgenin doğru ana fikri korunmuştur: ürün yalnız “bir mağazada görülen başlık” değil, kimlikleri, varyantları, teklifleri, kanıtları ve zaman içindeki fiyat/stok hareketleri olan kalıcı bir varlıktır. Eski belgedeki “mobil/OCR henüz yok” gibi tarihsel durum ifadeleri ise artık geçerli değildir; web OCR seçimi ve Android barkod APK'sı bugün çalışır durumdadır.

### 15.1 Ürünün hedef tanımı

Sistem aşağıdaki soruları aynı kayıtta yanıtlamalıdır:

1. Fotoğraftaki veya barkoddaki ürün tam olarak hangisidir?
2. Bu ürünün hangi renk, beden, kapasite veya başka varyantı aranıyor?
3. Aynı ürün hangi mağaza ve satıcılarda bulunuyor?
4. Etiket, sepet, üyelik ve kupon fiyatlarından hangisi gerçekten kullanılabilir?
5. Kargo ve bilinen ücretler eklendiğinde ödenecek toplam nedir?
6. Kullanıcının veya aile üyesinin bedeni/numarası stokta mıdır?
7. Satıcı ve teklif kanıtı ne kadar güvenilirdir?
8. Sonuç ne zaman ve hangi kaynakla doğrulanmıştır?
9. Ürün daha sonra alınmadıysa hangi koşul oluştuğunda bildirim gönderilmelidir?

Bu nedenle hedef ürün tanımı “çok mağazalı ürün takipçisi”nden daha geniştir: fiziksel ve çevrim içi ürünü tek kimlik grafiğinde birleştiren, kullanıcı adına doğrulanabilir satın alma kararı hazırlayan kişisel alışveriş zekâsıdır.

### 15.2 Bugünkü uygulama durumu

| Yetenek | Güncel durum | Kanıt / kalan iş |
|---|---|---|
| Android barkod/QR | Çalışıyor | Google Code Scanner kullanan test APK'sı üretildi |
| Fotoğraf yükleme ve yerel OCR | Çalışıyor | RapidOCR/ONNX; görüntü kalıcı olarak saklanmıyor |
| Fotoğrafta OCR kutusuna dokunarak seçim | Çalışıyor | Normalize çokgenler, seçili satır sorgusu, toplu/önerilen seçim |
| GTIN ve model kodu ayrıştırma | Çalışıyor | Check digit ve ürün kodu kalıpları; sorgu planına ayrı kanıt olarak giriyor |
| Kod/barkod öncelikli çoklu mağaza sorgusu | Çalışıyor | Kod → GTIN → marka+kod → zengin ad → ham metin |
| CanonicalProduct/ProductVariant/ProductIdentifier görünümü | Temel katman eklendi | Mevcut ürün/listing verisinden açık rol ayrımı üretiliyor; ayrı koleksiyon migrasyonu sonraki faz |
| Toplam maliyet | Temel katman eklendi | Koşulsuz sepet fiyatı + açık kargo; bilinmeyen kargo/kupon koşulu açıkça eksik işaretleniyor |
| Satıcı güven göstergesi | Temel katman eklendi | Resmî satıcı, marketplace, satıcı adı/puanı ve veri güncelliği açıklamalı puanlanıyor; garanti olarak sunulmuyor |
| GS1 Digital Link | Temel ayrıştırıcı eklendi | HTTP(S) bağlantısı açılmadan GTIN/lot/son kullanma/seri/varyant AI alanları ayrıştırılıyor |
| Kendi katalog görsel araması | Planlandı | OpenCLIP + pgvector öneriliyor; henüz üretim dizini yok |
| İnternet çapında görsel web araması | İsteğe bağlı gelecek katman | Vision Web Detection aday sayfa bulabilir; fiyat/stock kanıtı değildir |
| Fiziksel raf fiyatı/fiş kanıtı | Planlandı | OCR temeli var; kanıt, konum/mağaza ve kullanıcı onay modeli henüz tamamlanmadı |
| Canlı mobil OCR kamera katmanı | Planlandı | Web fotoğraf seçimi çalışıyor; CameraX + ML Kit Text Recognition sonraki mobil aşama |
| AR mağaza deneyimi | Uzun vadeli | Kimlik ve saha doğruluk kapıları geçilmeden başlanmamalı |

## 16. Bütünleşik ürün ve kanıt veri modeli

Mevcut veritabanında `products`, `listings`, `watch_queries`, `candidate_listings`, `price_history` ve `alerts` çekirdeği vardır. Hedef semantik model aşağıdaki rolleri açık hale getirmelidir:

| Varlık | Sorumluluğu | Zorunlu kanıt / ilişki |
|---|---|---|
| `CanonicalProduct` | Marka ve model düzeyinde kalıcı ürün | marka, model ailesi, kategori, canonical key |
| `ProductVariant` | Renk, beden, kapasite, cinsiyet, yaş grubu gibi varyant | canonical product bağlantısı, ayrıştırılmış varyant özellikleri |
| `ProductIdentifier` | GTIN/EAN/UPC, MPN/stil kodu, mağaza SKU'su, GS1 Digital Link | değer, tür, kaynak, doğrulanma durumu |
| `Offer` | Bir mağaza/satıcının belirli varyanta teklifi | ürün/varyant, satıcı, URL, fiyat türü, para birimi, stok |
| `OfferEvidence` | Teklif bilgisinin neden doğru sayıldığı | kaynak türü, seçici/JSON-LD alanı, zaman, güven, ham kanıt özeti |
| `Seller` | Marketplace satıcısı veya doğrudan mağaza | ad, mağaza, resmî satıcı işareti, puan, ölçüm zamanı |
| `PriceObservation` | Teklifin zaman içindeki fiyat gözlemi | etiket/sepet/üye/kupon ayrımı, toplam maliyet, zaman |
| `WatchQuery` | Kullanıcı niyeti ve filtreleri | kim için, bedenler, renk, hedef fiyat, mağaza kapsamı, sıklık |
| `ScanEvidence` | Kamera/barkod/OCR sonucu | ham değer, polygon/bbox, dönüş, güven, görsel özeti, kullanıcı seçimi |
| `UserReportedPrice` | Kullanıcının fiziksel mağazada gördüğü fiyat | mağaza, zaman, ürün kimliği, kullanıcı onayı, kanıt fotoğrafı politikası |
| `ReceiptEvidence` | Satın alma sonrası fiyat ve ürün kanıtı | fiş satırı, toplam, mağaza, tarih, kişisel verisi ayıklanmış görüntü |
| `Device` | Mobil istemci ve çevrimdışı iş kuyruğu | cihaz kimliği yerine rastgele kurulum ID'si, son senkronizasyon |
| `NotificationPreference` | Bildirim kanalı ve sessizlik/öncelik ayarı | kullanıcı/aile üyesi, olay türü, kanal, sıklık, gece politikası |

### 16.1 Kimlik çözümleme önceliği

Kimlik kararı aşağıdaki sırayla verilmelidir:

```text
doğrulanmış GTIN
  > marka + açık MPN/stil kodu
  > mağaza SKU'su + kanıtlanmış varyant
  > marka + ayırt edici model adı + kategori
  > görsel/OCR benzerliği
  > kullanıcı onayı
```

Bir alt basamak daha üst basamaktaki açık çelişkiyi geçersiz kılamaz. Örneğin `JR5220` aranırken aday sayfasında `JR5219` görünüyorsa “trail running” benzerliği otomatik kabul oluşturamaz. Görsel benzerlik aday üretir; tek başına kesin SKU kanıtı değildir.

### 16.2 Ürün ve varyant ayrımı

Schema.org'un [`ProductGroup`](https://schema.org/ProductGroup), `hasVariant`, `isVariantOf` ve `variesBy` ilişkileri referans alınmalıdır. Ayakkabıda renk ve numara; giyimde renk ve beden; televizyonda ekran boyutu/model suffix'i; bisiklette kadro/jant gibi alanlar aynı canonical product altında ayrı varyant olabilir. Farklı açık üretici kodu varsa varsayılan karar ayrı varyant/üründür; kullanıcıya “aynı aile” ilişkisi ayrıca gösterilebilir.

## 17. Lens benzeri seçilebilir OCR kullanıcı deneyimi

### 17.1 Güncel web davranışı

Fotoğraf OCR sonucu artık yalnız düz metin değildir. Her OCR satırı kaynak fotoğraf koordinatlarına normalize edilmiş bir çokgen taşır. Radar ekranı:

- fotoğraftaki her metin alanını tıklanabilir çerçeve olarak gösterir;
- seçili alanı farklı renkle işaretler;
- satır listesinden aynı seçimi erişilebilir checkbox'larla yapar;
- tümünü seç, önerilenleri seç ve seçimi temizle işlemlerini sunar;
- yalnız seçilen metni düzenlenebilir Radar sorgusuna aktarır;
- decoder ile gerçekten çözülen barkodu, kullanıcı yalnız OCR satırı seçse bile ayrı güçlü kimlik kanıtı olarak korur;
- seçilmeyen OCR model kodunu sessizce kesin kanıt olarak taşımamaya dikkat eder;
- fotoğrafı sola/sağa döndürüp OCR'ı yeniden çalıştırabilir.

Bu yapı Lens'teki “hangi yazıyı arayacağını kullanıcı belirlesin” davranışının web tabanlı karşılığıdır. Lasso/serbest şekil seçimi yerine satır/alan seçimi kullanılmıştır; ürün etiketleri için daha deterministik ve yanlış birleşmeye daha dirençlidir.

### 17.2 Mobil hedef davranış

Tam mobil deneyimde CameraX karesi üzerinde ML Kit Barcode Scanning ve Text Recognition paralel çalışmalıdır. Text Recognition v2 blok, satır, kelime ve sembol koordinatlarını verdiği için şu etkileşim yapılabilir:

1. Kullanıcı ürün/etiket alanına dokunur veya kırpar.
2. Barkodlar ve OCR kutuları canlı görüntü üzerinde çizilir.
3. Kullanıcı satırları dokunma, sürükleme veya çoklu seçimle işaretler.
4. Seçili metin düzenlenebilir sorguya dönüşür.
5. GTIN uzunluk ve kontrol hanesi doğrulanır.
6. “Marka”, “ürün adı”, “model kodu”, “beden/renk”, “fiyat/tarih/gereksiz metin” rolleri ayrılır.
7. Kullanıcı onayıyla Radar işi cihazda kuyruğa alınır; internet gelince sunucuya gönderilir.

ML Kit OCR belgeleri küçük/bulanık karakterlerde giriş kalitesinin kritik olduğunu belirtir. Etiket çekiminde otomatik odak, perspektif düzeltme, parlamayı azaltma ve karakter başına yeterli piksel sağlama, model değişiminden daha yüksek değer üretebilir. Kaynak: [ML Kit Text Recognition v2](https://developers.google.com/ml-kit/vision/text-recognition/v2/android).

## 18. Barkoddan piyasa fiyatı bulmanın gerçek algoritması

Barkodun içinde ürünün piyasa fiyatı yoktur. Barkod, çoğunlukla ürünü tanımlayan GTIN'i verir. İyi sonuç zinciri şudur:

```text
EAN/UPC/GS1 kod çözümü
        ↓
GTIN biçim + check digit doğrulaması
        ↓
GTIN → CanonicalProduct/ProductVariant eşlemesi
        ↓
tam GTIN + marka/model kodu mağaza sorguları
        ↓
aday sayfada ürün kimliği doğrulaması
        ↓
Offer/stock/size/seller/shipping kanıtı
        ↓
toplam maliyet + zaman damgası + güven açıklaması
```

### 18.1 Fiyat kaynağı önceliği

1. Yetkili resmî mağaza API/feed'i.
2. Ürün sayfasındaki `Product`/`Offer` JSON-LD veya sunucudan gelen yapılandırılmış durum.
3. Görünür ürün detay sayfasının mağazaya özel ayrıştırıcısı.
4. Kullanıcı destekli, açıkça etiketlenmiş tarayıcı/mağaza kanıtı.
5. Fiziksel raf etiketi/fiş OCR'si ve kullanıcı onayı.

Arama motoru özeti, görsel eşleşme sayfası veya kategori kartı tek başına canlı fiyat/stok kanıtı sayılmamalıdır.

### 18.2 Toplam maliyet hesabı

Kullanıcıya “en ucuz” denmesi için karşılaştırma değeri şu olmalıdır:

```text
kullanılabilir ürün fiyatı
+ açık kargo bedeli
+ bilinen zorunlu ücretler
- kullanıcının gerçekten kullanabildiği koşulsuz indirim
= doğrulanmış toplam maliyet
```

Yeni temel hesaplayıcı, koşulsuz doğrulanmış sepet fiyatını kullanır ve açık kargo tutarını ekler. Üyelik, banka, kupon, minimum sepet veya kişiye özel kampanyayı otomatik olarak düşmez. Kargo bilinmiyorsa ürün fiyatını gösterebilir fakat `complete=false` ve `shipping_cost missing` kanıtı verir. Böylece “etikette ucuz, kasada pahalı” hatası azaltılır.

### 18.3 Satıcı güveni

Satıcı puanı bir güvenlik garantisi değildir. Ekrandaki açıklamalı gösterge şu sinyalleri ayrı tutar:

- doğrudan mağaza alan adı mı, marketplace satıcısı mı;
- resmî satıcı/marka mağazası işareti var mı;
- satıcı adı ve sayfadaki puanı okunabildi mi;
- ürün sayfası son kontrolde başarılı mı;
- teklif güncel olarak fiyat/stok kanıtı verdi mi.

Marketplace ilanında satıcı adı veya puanı okunamadıysa düşük kanıt uyarısı çıkar. Resmî satıcı işareti puanı yükseltir, fakat sonuç yine “mevcut sayfa kanıtlarının özeti; satıcı garantisi değildir” açıklamasını taşır.

## 19. Google servisleri: kullanılabilir olanlar ve olmayanlar

| Servis/yetenek | Bize açık mı? | Doğru kullanım | Kritik sınır |
|---|---:|---|---|
| Google Lens tüketici deneyimi | Hayır | Davranış ve UX referansı | Programatik genel Lens arama API'si yok |
| Shopping Graph sorgu katmanı | Hayır | Mimari çıkarım | GTIN/görsel → tüm satıcı/fiyat/link API'si yayımlanmamış |
| Merchant API v1 | Koşullu | Yetkili kendi Merchant Center ürün/envanter/raporları | Genel rakip/piyasa araması değildir; OAuth/hesap yetkisi ister |
| Merchant benchmark raporları | Uygun hesapta koşullu | Kendi offerId'leri için fiyat rekabeti sinyali | Ham rakip satıcı/link listesi vermez; uygunluk şartları var |
| ML Kit Barcode Scanning | Evet | Cihaz üstü EAN/UPC/QR/Data Matrix vb. | Ürün fiyatı vermez |
| ML Kit Text Recognition | Evet | Cihaz üstü OCR ve seçilebilir kutular | Ürünü internette eşlemez |
| Vision Product Search | Ücretli | Bizim yüklediğimiz kendi katalog içinde görsel arama | Shopping Graph/Lens indeksi değildir; indeks güncelliği sınırlı olabilir |
| Vision Web Detection | Ücretli | Benzer/eşleşen görsel ve web sayfası adayları | Canlı fiyat, stok veya doğru varyant garantisi vermez |
| Custom Search JSON API | Stratejik olarak hayır | Eski müşteriler için geçiş dönemi | Yeni müşterilere kapalı; 1 Ocak 2027 geçiş takvimi |

Google'ın resmî Lens açıklaması Shopping Graph'un 45 milyardan fazla ürün kaydı kullandığını belirtir; bu ölçek tüketici deneyiminin neden güçlü olduğunu açıklar, fakat veri katmanının geliştiriciye açıldığı anlamına gelmez. Kaynak: [Google Lens ile görsel alışveriş](https://blog.google/products-and-platforms/products/shopping/visual-search-lens-shopping/).

Merchant API için doğru karar: İleride ShoeHunter'ın kendisine ait veya yetkili olduğu bir Merchant Center hesabı varsa ürün yönetimi/benchmark amacıyla ayrı bir entegrasyon yapılabilir. Piyasa arama çekirdeği buna bağlanmamalıdır. Merchant API v1 kullanılmalı; eski Content API for Shopping 18 Ağustos 2026'da kapanacağı için yeni geliştirme ona kurulamaz. Kaynaklar: [Merchant API overview](https://developers.google.com/merchant/api/overview), [ürün yönetimi](https://developers.google.com/merchant/api/guides/products/add-manage), [pazar raporları](https://developers.google.com/merchant/api/guides/reports/understand-the-market), [Content API kapanışı](https://support.google.com/merchants/answer/16493611?hl=en-GB).

## 20. GS1, 2D barkod ve çok kategorili gelecek

GS1 Digital Link bir GTIN/GLN/SSCC gibi kimliği marka sahibinin çevrim içi kaynaklarına bağlayabilir; piyasa fiyatı veri tabanı değildir. Yeni ayrıştırıcı, bağlantıyı otomatik açmadan yaygın Application Identifier alanlarını çıkarır:

- `(01)` GTIN;
- `(10)` parti/lot;
- `(17)` son kullanma tarihi;
- `(21)` seri numarası;
- `(22)` tüketici ürünü varyantı.

Güvenlik kuralı: QR/GS1 bağlantısı kameradan okununca otomatik açılmaz. Önce şema ve alan adı gösterilir, kimlik ayrıştırılır, uzak erişim ancak kullanıcı onayı ve sunucu URL güvenlik kontrolüyle yapılır.

GS1 Digital Link URI syntax'ın güncel sürümü 1.6.0, Resolver standardının güncel sürümü 1.2.0'dır. [`gs1/digital-link.js`](https://github.com/gs1/digital-link.js) Apache-2.0 lisanslı yararlı bir referanstır; üretimde güncel standardın conformance testleri ayrıca uygulanmalıdır. [GS1 Digital Link](https://www.gs1.org/standards/gs1-digital-link), [GS1 Resolver](https://www.gs1.org/standards/resolver).

Çok kategorili destek için ortak kimlik/teklif çekirdeği korunmalı, kategori eklentileri kullanılmalıdır:

| Kategori | Varyant/izleme alanları | Özel risk |
|---|---|---|
| Ayakkabı | EU/US/UK/CM numara, cinsiyet, genişlik, renk | marka bazlı kalıp ve aynı kodun cinsiyet varyantı |
| Üst giyim | XS–4XL, yaş/boy, fit, renk | ülke beden eşlemesi |
| Pantolon | bel/boy, beden sistemi, kalıp | W/L ile EU bedeninin karışması |
| Dış giyim | beden, su geçirmezlik sınıfı, renk | aynı modelin sezon/suffix farkı |
| Elektronik | GTIN, üretici model suffix'i, kapasite/ekran | aynı seri içinde teknik varyant |
| Bisiklet/spor ekipmanı | kadro, jant, yaş, renk | yerel model/seri adı tutarsızlığı |
| Gıda/kozmetik | GTIN, hacim/ağırlık, lot/SKT | fiyat kadar son kullanma ve paket miktarı |

## 21. Mobil mimari kararı, offline ve gizlilik

### 21.1 Çerçeve karşılaştırması

| Seçenek | Güçlü yanı | Zayıf yanı | Bu proje için karar |
|---|---|---|---|
| Mevcut Android WebView kabuğu | En hızlı APK, mevcut React arayüzünü yeniden kullanır | Canlı kamera/OCR, offline ve push yaşam döngüsü sınırlı | Geçiş sürümü olarak korunur |
| React Native | Web/React ekibine yakın, ortak ürün mantığı | Kamera overlay ve düşük seviye taramada native köprü gerekir | UI büyürse değerlendirilebilir |
| Flutter | Tutarlı çapraz platform UI | Mevcut React kodunu yeniden kullanmaz; yeni ekip/katman | Bugün öncelik değil |
| Native Kotlin + CameraX + ML Kit | En güçlü kamera, OCR kutuları, offline iş ve Android entegrasyonu | Android/iOS için ayrı istemci maliyeti | Tarama dikey dilimi için önerilen yöntem |

En iyi yakın dönem yol, bütün uygulamayı bir anda yeniden yazmak değildir. Mevcut WebView kabuğu hesap/Radar ekranlarını taşırken yeni native `ScanActivity` veya Compose/CameraX dikey dilimi barkod, OCR ve seçim işini yapabilir. Sonuç güvenli bir yerel köprüyle web formuna veya mobil API'ye aktarılır. Kullanım kanıtlanırsa diğer ekranlar kademeli nativeleşir.

### 21.2 Offline davranış

- Bundled ML Kit barkod/OCR modeli ilk kullanımda internetsiz çalışabilmelidir.
- Tarama sonucu, seçilen metin ve GTIN cihazda şifreli küçük bir outbox kaydına yazılabilir.
- İnternet yokken “güncel fiyat bulundu” denmez; yalnız kimlik/arama niyeti kaydedilir.
- Bağlantı gelince idempotency key ile tek Radar işi oluşturulur.
- Son bilinen fiyat gösterilirse zamanı ve “çevrimdışı/eski” durumu belirgin olmalıdır.

### 21.3 Kamera ve kişisel veri politikası

1. Barkod ve mümkünse OCR cihaz üzerinde işlenir.
2. Kamera karesi varsayılan olarak sunucuya gönderilmez.
3. Fotoğraf yükleme ayrı, açık kullanıcı işlemi olmalıdır.
4. Sunucu OCR'si görüntüyü bellekte işler; kalıcı saklama kapalı varsayılandır.
5. Kanıt fotoğrafı saklanacaksa amaç, süre ve silme seçeneği gösterilir.
6. Fiş OCR'sinde ad, kart son hanesi, telefon ve sadakat numarası gibi alanlar cihazda maskelenmelidir.
7. Konum zorunlu değildir; fiziksel mağaza kullanıcı tarafından seçilebilir. Konum izni verilirse yalnız mağaza eşlemeye yetecek hassasiyet tutulur.
8. QR bağlantısı otomatik açılmaz.
9. AI sağlayıcısına profil/fotoğraf gönderimi ayrı onay ve veri minimizasyonu ister.

## 22. 27 mağaza güvenilirliği ve kök çözüm programı

### 22.1 “25 engel” nasıl yorumlanmalı?

Bir çalışmada 25 mağazanın `deferred` olması “25 mağaza kesin bot engeli koydu” demek değildir. O kayıtta mağaza motorlarının çoğu devre kesici yüzünden hiç çağrılmamıştır. Devreyi açan nedenler arasında sahte/bozuk yerel proxy, tarayıcı kapasite zaman aşımı ve başka bir işlem türündeki eski hata bulunuyordu. Kullanıcı açısından sonuç yine başarısızdır; fakat doğru kök çözüm her mağazaya daha saldırgan istek göndermek değil, erişim ve operasyon durumlarını doğru ayırmaktır.

### 22.2 Kök mimari

```text
watch run
  ├─ mağaza başına bağımsız görev ve hata kapsülleme
  ├─ discovery/search/product_detail için ayrı devre hattı
  ├─ kısa, sınırlı ve jitter'lı geçici hata yeniden denemesi
  ├─ mağazaya özel zaman bütçesi
  ├─ normal HTTP → yapılandırılmış veri → normal Playwright → izinli katalog/sitemap fallback
  ├─ sonuç başına kimlik doğrulama
  └─ selected / searched / success / deferred / failed / coverage kanıtı
```

Bir ürün detay sayfasında 403 alınması, aynı mağazanın normal katalog veya keşif hattını otomatik kapatmamalıdır. Benzer biçimde tarayıcı havuzu doluluğu mağaza bot engeli sayılmamalıdır. Yeni operasyon-izole devre politikası `discovery`, `search` ve `product_detail` durumlarını ayrı tutar; eski global devreleri migrasyonda emekliye ayırır. Mağaza hatası diğer mağazaları iptal etmez; sınırlı yeniden deneme ve güvenli fallback kendi süre bütçesi içinde kalır.

### 22.3 Erişim katmanları ve kesin sınır

Önerilen erişim sırası:

1. resmî API/feed;
2. robots ve kullanım şartlarıyla uyumlu katalog/site haritası;
3. normal, tanımlı HTTP istemcisi;
4. normal Playwright tarayıcı otomasyonu;
5. açık kullanıcı onaylı insan destekli sayfa aktarımı;
6. kontrollü `deferred/blocked` sonucu ve yeniden deneme zamanı.

CAPTCHA atlatma, stealth/tespitten kaçma, kimlik sahteciliği, çalıntı çerez, proxy rotasyonuyla engel aşma veya hız sınırı saldırısı kullanılmamalıdır. Bunlar veriyi daha güvenilir yapmaz; hesap/alan adı engeli, hukuki ve güvenlik riski oluşturur. “Tüm mağazalarda çalışan” hedefi, korumayı delmek değil, izinli veri kanalları + mağazaya özel adaptör + insan destekli kanıt + dürüst kapsama ile gerçekleştirilmelidir.

### 22.4 Hizmet seviyesi hedefi

- Bir mağaza hatası diğer 26 mağazanın işini durdurmamalı.
- `deferred` ve kapasite beklemesi devre başarısızlığı sayılmamalı.
- Arama sonucu `completed` yalnız tüm seçili mağazalar terminal duruma geldiyse kullanılmalı; aksi durumda `partial`.
- Tier-1 mağazalarda arama çalıştırma başarısı ≥ %95, ürün detay kanıtı ≥ %98 hedeflenmeli.
- Koruma nedeniyle otomatik erişilemeyen mağaza için kullanıcı destekli link/kanıt yolu ve açık durum gösterilmeli.
- Her mağaza için son başarı, son hata sınıfı, operasyon hattı, retry zamanı ve son 24 saat başarı oranı izlenmeli.

## 23. Dünya örnekleri ve açık kaynak fırsatları

| Proje/servis | Öğrenilecek parça | Lisans / risk | Öneri |
|---|---|---|---|
| [Google ML Kit örnekleri](https://github.com/googlesamples/mlkit) | CameraX ile canlı/statik barkod, OCR, nesne algılama | Apache-2.0 | Native tarama ekranı için birincil referans |
| [OpenCLIP](https://github.com/mlfoundations/open_clip) | Görsel ve metni ortak embedding uzayına taşıma | Kod MIT; checkpoint/ağırlık lisansı ayrıca denetlenmeli | Kendi katalog görsel aramasının modeli |
| [pgvector](https://github.com/pgvector/pgvector) | Metadata ile aynı DB'de exact/HNSW/IVFFlat vektör arama | PostgreSQL lisansı; approximate recall ölçülmeli | MVP için önerilen vektör katmanı |
| [Qdrant](https://github.com/qdrant/qdrant) | Filtreli HNSW ve hybrid search | Apache-2.0; ayrı servis işletme maliyeti | Ölçek artınca ikinci aşama |
| [FAISS](https://github.com/facebookresearch/faiss) | CPU/GPU exact/approx KNN | MIT; kalıcı metadata/transaction DB'si değil | Offline benchmark ve prototip |
| [clip-retrieval](https://github.com/rom1504/clip-retrieval) | Embedding + FAISS + servis/UI uçtan uca örneği | MIT; ürün kimliği/fiyat doğrulaması değildir | Mimari referans |
| [AWS CLIP Search örneği](https://github.com/aws-samples/amazon-sagemaker-clip-search) | Offline katalog embedding + online sorgu embedding | Bulut maliyeti ve bağımlılık lisansları | Büyük katalog mimari referansı |
| [ZXing-C++](https://github.com/zxing-cpp/zxing-cpp) | Non-GMS/server çok formatlı barkod fallback'i | Apache-2.0, aktif proje | Google servisleri olmayan cihazlar için değerlendirilir |
| [ZXing Java](https://github.com/zxing/zxing) | Barkod çekirdeği ve format referansı | Apache-2.0; Android Scanner uygulaması bakım modunda | Eski Scanner uygulaması kopyalanmamalı |
| [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) | Karmaşık fiş/etiket ve çok dil server fallback'i | Apache-2.0 kod; modeller ayrıca incelenmeli | Ağır OCR gerektiğinde ikincil yol |
| [Open Food Facts](https://github.com/openfoodfacts/openfoodfacts-server) | Barkod merkezli crowdsource ürün kimliği | AGPL-3.0; genel ürün/ayakkabı kapsamı zayıf | API/kavramsal referans, çekirdeğe kopyalama yok |
| [Open Prices](https://github.com/openfoodfacts/open-prices) | Fiyat + mağaza + zaman + etiket/fiş kanıtı | AGPL-3.0 ve kategori kapsamı | Fiziksel fiyat kanıt modeline güçlü örnek |
| [GS1 digital-link.js](https://github.com/gs1/digital-link.js) | GS1 URI üretme/ayrıştırma/check digit | Apache-2.0; güncel standarda conformance testi gerekli | GS1 katmanı için referans |

Ticari ürün için [Apple MobileCLIP](https://github.com/apple/ml-mobileclip) model ağırlıkları uygun varsayılmamalıdır: kod MIT olsa da yayımlanan model ağırlıkları araştırma/non-commercial koşullar taşır. Açık kaynak seçimi yalnız GitHub repo lisansına değil model kartı, checkpoint ve eğitim verisi koşullarına göre yapılmalıdır.

## 24. Fiziksel mağaza fiyatı, raf etiketi ve fiş kanıtı

Fotoğraflardaki “ALDIN ALDIN”, televizyon/bisiklet model metni ve fiyatlar, ürün Radarını ayakkabı dışına genişletmek için gerçekçi saha örnekleridir. Önerilen işlem:

1. Fotoğrafta ürün adı/model/barcode alanı ile fiyat alanı kullanıcı tarafından ayrı seçilir.
2. Fiyat OCR'si tek başına ürüne bağlanmaz; aynı görüntü/oturumda ürün kimliği şarttır.
3. Mağaza kullanıcı seçimi, QR/konum veya mağaza katalog eşlemesiyle belirlenir.
4. `UserReportedPrice` kaydı zaman, mağaza, ürün/varyant, fiyat, güven ve kanıt rolünü tutar.
5. Başka bir kullanıcıya gösterilmeden önce makul aralık, tarih, aynı mağaza/ürün tekrarları ve gerekirse ikinci kanıt kontrol edilir.
6. Raf fiyatı ile kasa/fiş fiyatı farklıysa ikisi ayrı gözlem türü olarak tutulur.
7. Fiş fotoğrafı kalıcı tutulacaksa kişisel veriler cihazda maskelenir; varsayılan tercih ayrıştırılmış alanları tutup ham görüntüyü silmektir.

Open Prices'ın ürün + yer + zaman + fiyat + kanıt yaklaşımı bu tasarım için değerlidir; ancak kapsam ve AGPL lisansı nedeniyle kodu doğrudan kapalı çekirdeğe almak yerine veri/kanıt modelinden öğrenmek daha güvenlidir. Kaynak: [Open Prices belgeleri](https://openfoodfacts.github.io/open-prices/).

## 25. Bildirim, aile profili ve müşteri değeri

Lens benzeri bulma tek seferlik aramayı çözer; Ürün Radarının daha kalıcı değeri doğru ürün/beden koşulunu zaman içinde izlemesidir. Aile profili bir kişi için birden fazla ayakkabı numarası ve kategori başına farklı beden profili tutmalıdır. Watch kaydı profile bağımlı kalmamalı; o anda çözülen bedenlerin snapshot'ını da saklamalıdır. Profil değişince kullanıcı isterse mevcut takipler yeniden hesaplanır.

Öncelikli bildirim sınıfları:

- son numara/beden fırsatı;
- numaran yeniden stokta;
- indirimli fiyattan yeniden stokta;
- tek renk/tek numara geri geldi;
- fiyat düştü ve numaran mevcut;
- sepet fiyatı devam ediyor;
- stok kritik seviyede;
- son 30/90 günün en düşük fiyatı;
- yeni mağaza veya yeni varyant bulundu;
- fiyat doğrulanamadı / ürün yayından kalktı.

Her bildirim ürün adı, mağaza, ürün kodu/GTIN kanıtı, uygun numara/beden, fiyat türü, toplam maliyetin tam olup olmadığı, satıcı, zaman ve doğrudan link içermelidir. Bir ayakkabı için “42 veya 42,5”, bir üst giyim için “L veya XL” gibi alternatifler ayrı hedefler değil aynı kullanıcının kabul ettiği beden kümesidir.

## 26. Fazlı uygulama planı ve geçiş kapıları

### F0 — Güvenilir çekirdek ve ölçüm

- Operasyon-izole mağaza devreleri, per-store hata kapsülleme ve gerçek kapsama metriği.
- Kimlik çelişkisi, fiyat türü ve kanıt tazeliği kuralları.
- Tier-1 mağaza kontrat testleri ve canlı sağlık paneli.

**Geçiş kapısı:** Tek mağaza hatası bütün koşuyu durdurmuyor; yanlış kesin ürün eşleşmesi kontrollü veri setinde <%1; kapsam kullanıcıya eksiksiz açıklanıyor.

### M1 — Android barkod ve Radar dikey dilimi

- Mevcut Code Scanner APK, güvenli sunucu adresi ayarı ve Radar formu aktarımı.
- EAN/UPC/QR/Data Matrix saha testi.
- Offline outbox ve idempotent senkronizasyon.

**Geçiş kapısı:** Desteklenen, kaliteli barkod örneklerinde >%95 decode; p95 ilk sonuç <1 saniye hedefi; çevrimdışı kayıt kaybı yok.

### M2 — Seçilebilir OCR ve kimlik grafiği

- CameraX + ML Kit Text Recognition.
- Canlı metin kutuları, seçim/düzeltme, GTIN check digit.
- CanonicalProduct/ProductVariant/ProductIdentifier migrasyonu.
- Toplam maliyet ve satıcı güvenini tüm teklif kartlarına taşıma.

**Geçiş kapısı:** Ürün kodlu etiketlerde ilk üç sorgu adayında doğru ürün ≥%95; otomatik exact match precision ≥%99; koşullu fiyat kesin toplam diye gösterilmiyor.

### M3 — Kendi görsel ürün dizini

- Katalog görsellerini hash ile tekrar temizleme.
- Lisansı onaylı OpenCLIP modeliyle embedding.
- Başlangıçta pgvector, ölçek ihtiyacında Qdrant.
- Aynı ürün ve benzer ürün için farklı eşik/etiket.

**Geçiş kapısı:** Etiketsiz saha setinde top-5 doğru aday hedefi tanımlanıp karşılanmalı; varyant karışıklığı ayrı ölçülmeli; yalnız embedding ile exact SKU kabul edilmemeli.

### M4 — Fiziksel fiyat ve fiş kanıtı

- Raf etiketi/fiş OCR rol ayrımı.
- Mağaza, zaman, kanıt ve moderasyon modeli.
- Kişisel veri maskeleme ve ham görüntü TTL/silme.

**Geçiş kapısı:** Kullanıcıya yayımlanan fiziksel fiyatlarda ürün-varyant doğruluğu ≥%95; kişisel veri sızıntısı test setinde sıfır; kanıtsız fiyat “doğrulandı” sayılmıyor.

### M5 — GS1 Digital Link ve yaşam döngüsü

- Digital Link/Resolver uyum testleri.
- Seri/lot/SKT ve satın alma sonrası takip.
- İade süresi, garanti, sarf/yenileme hatırlatmaları.

### M6 — AR ve ileri mağaza deneyimi

- Kamera üzerinde takipteki ürün/beden/fiyat rozeti.
- Mağaza içi karşılaştırma ve yönlendirme yalnız açık izinle.

**Ön koşul:** Kamera kimlik doğruluğu, pil/performans ve gizlilik saha ölçümleri hedefi geçmeden AR geliştirilmez.

## 27. KPI sistemi

Ana müşteri metriği: **doğrulanmış faydalı karar sayısı**. “Bulunan link sayısı” tek başına başarı değildir.

| KPI | Tanım | İlk hedef |
|---|---|---:|
| Doğru fırsat kararı | Doğru ürün/varyant + kullanılabilir fiyat + güncel stok | ≥ %95 |
| Otomatik exact match precision | Otomatik bağlanan ilanların gerçekten aynı ürün olması | ≥ %99 |
| Yanlış stok bildirimi | Bildirimde mevcut denip kullanıcı açtığında yok olan uygun beden | < %1 hedefi |
| Tier-1 detay başarısı | Fiyat/stok/beden sözleşmesini karşılayan canlı kontroller | ≥ %98 |
| Radar mağaza kapsamı | Başarıyla aranan / seçili mağaza | Koşu ve mağaza bazında görünür; Tier-1 ≥ %95 |
| Barkod çözme | Kaliteli desteklenen barkodlarda başarılı decode | > %95 |
| Barkod p95 gecikme | Kamera algılamadan kimlik sonucuna | < 1 sn hedefi |
| Görsel top-5 recall | Etiketsiz fotoğrafta doğru adayın ilk beşte olması | Saha veri setiyle faz kapısı |
| Toplam maliyet tamlığı | Kargo/koşul bilgisiyle karşılaştırılabilir teklifler | Kaynak bazında izlenir |
| Kanıt tazeliği | Son 6 saat içinde doğrulanmış aktif teklif | Bildirim öncesi zorunlu |
| Açıklanabilirlik | Sonucun kimlik/fiyat/stock kanıtını gösterebilmesi | %100 otomatik sonuç |

## 28. Gelir modeli ve güven sırası

Gelir özelliği ürün güveninden sonra gelmelidir:

1. Kullanıcı yararı bozulmadan açıkça işaretlenmiş affiliate bağlantı;
2. daha sık Radar, çok aile üyesi, gelişmiş fiyat geçmişi ve özel bildirim için premium;
3. kullanıcı onaylı topluluk fiyat kanıtı ağı;
4. en son, anonim ve toplulaştırılmış B2B içgörü.

Kullanıcı profili, fiş görüntüsü, kamera fotoğrafı veya bireysel satın alma geçmişi satılmamalıdır. Affiliate komisyonu sıralamayı gizlice değiştirmemeli; en ucuz/doğru teklif ile sponsorlu teklif ayrı gösterilmelidir.

## 29. Sınırlamalar, belirsizlik ve sağlamlık kontrolleri

- Lens/Shopping Graph'un kapalı sıralama ayrıntıları bilinmediği için önerilen algoritma Google'ın kamuya açık özellikleri ve genel bilgi erişim ilkelerinden çıkarımdır.
- Canlı mağaza sonuçları tarihe, ürüne, bölgeye, oturuma ve mağaza korumasına göre değişebilir. `22/27` ve `18/27` sonuçları belirli koşuların kanıtıdır, kalıcı SLA değildir.
- Bir mağazanın sorguya boş yanıt vermesi ürünün piyasada olmadığı anlamına gelmez.
- Görsel benzerlik, özellikle aynı modelin renk/nesil varyantlarında yanlış SKU üretebilir.
- OCR güven puanı doğru alan rolünü garanti etmez; model kodu, fiyat ve beden kullanıcı tarafından düzenlenebilir tutulmalıdır.
- Marketplace satıcı puanlarının ölçeği ve anlamı mağazalar arasında aynı değildir; puan karşılaştırması normalize edilse bile açıklama gösterilmelidir.
- Kargo, kupon ve üyelik koşulları okunamıyorsa toplam maliyet eksik sayılmalıdır.
- Google Cloud fiyatları ve API politikaları değişebilir; ücretli pilot öncesi güncel resmî sayfa yeniden kontrol edilmelidir.
- Bu raporda ayrı bir grafik kullanılmamıştır; vaka ve mimari ilişkileri tam sayı içeren tablolar ve akışlarla daha açık aktarılmıştır.

## 30. Teknik sonuç ve önerilen kesin sıra

Bugün için en doğru sistem sırası şudur:

1. `JR5220`/`KC1948` vakalarında kanıtlanan kod+GTIN öncelikli sorgu ve sıkı kimlik filtresini koru.
2. Operasyon-izole devre ve per-store hata kapsüllemeyi bütün 27 mağazada kullan; kısmi kapsamı asla “bulunamadı” diye özetleme.
3. Web'de çalışan seçilebilir OCR'ı native CameraX + ML Kit ekranına taşı.
4. Mevcut ürün/listing çekirdeğini CanonicalProduct/ProductVariant/ProductIdentifier/OfferEvidence rollerine kademeli migrate et.
5. Toplam maliyet ve satıcı kanıtını fiyat sıralamasının parçası yap.
6. Kendi mağaza görsellerinden OpenCLIP + pgvector katalog araması kur; yalnız aday üretme amacıyla kullan.
7. Yalnız yerel/katalog araması sonuçsuzsa, açık kullanıcı onayı ve bütçeyle Vision Web Detection gibi resmî dış fallback değerlendir.
8. Fiziksel fiyat/fiş kanıtını gizlilik ve moderasyon kapılarıyla ekle.
9. GS1/2D ve satın alma sonrası yaşam döngüsünü kimlik grafiği olgunlaşınca genişlet.
10. AR ve gelir modellerini ancak doğruluk, gizlilik ve müşteri değeri KPI'ları geçilince başlat.

Bu plan Google Lens'i kopyalamaya çalışmaz; Lens'in güçlü ilkesini — görsel/barkod kanıtını büyük ve iyi doğrulanmış ürün/teklif ilişkilerine bağlamayı — ShoeHunter'ın kontrol edebildiği veri, mağaza adaptörleri ve kullanıcı güveni sınırında uygular.

### Cevabı henüz saha verisi isteyen sorular

- 27 mağazanın her biri için 30 günlük başarı/blocked/latency dağılımı nedir?
- Etiketsiz ürün fotoğraflarında hangi açık lisanslı embedding modeli Türk perakende kataloğunda en iyi top-5 sonucu verir?
- Kullanıcıların yüzde kaçı fotoğrafta OCR satırı seçmek yerine otomatik öneriyi kabul eder?
- Marketplace sonuçlarında toplam maliyetin tam hesaplanabildiği teklif oranı nedir?
- Hangi kategori barkoddan en yüksek kimlik kapsamasını, hangisi OCR/görsel fallback ihtiyacını gösterir?
- Fiziksel fiyat katkısında ikinci kanıt/moderasyon eşiği ne olmalıdır?

## 31. 21 Temmuz 2026 — yeni modelle yeniden denetim ve uygulama durumu

Bu ek bölüm, önceki çalışmanın yeni modelle yeniden okunması ve çalışan kod/test kanıtıyla karşılaştırılmasıdır. Önceki kazanımlar korunmuş, fakat sonuç üretimini doğrudan etkileyen dört ek hata bulunup düzeltilmiştir.

### 31.1 Yeni modelin bulduğu ek sorunlar

| Sorun | Kullanıcı etkisi | Yapılan düzeltme |
|---|---|---|
| Google Lens motoru var olmayan `stores.base_store` modülünü içe aktarıyordu | Endpoint çağrıldığında motor yüklenemiyordu | Ortak `StoreEngine` ve `parse_price_text` doğrudan `engines` modülünden bağlandı |
| Google Shopping ayrıştırıcısı `JR5220` gibi harf-rakam ürün kodunu fiyat sanabiliyordu | Gerçek başlık kayboluyor, sonuç eleniyor veya yanlış fiyat oluşabiliyordu | Fiyat adayı için `TL`, `₺` veya desteklenen para işareti kanıtı zorunlu yapıldı |
| Shopping backend'i `url/image`, React kartı `link/image_url` bekliyordu | Sonuç gelse bile bağlantı ve görsel boş kalabiliyordu | Canonical alanlarla birlikte iki arayüz uyumluluk alanı da döndürülüyor; React iki biçimi de okuyabiliyor |
| `success:false` yanıtı HTTP 200 ile geldiğinde arayüz hata göstermiyordu | Erişim/ayrıştırma hatası “0 sonuç” gibi görünüyordu | Lens ve Shopping istemcisi `success` değerini denetleyip gerçek hata mesajını gösteriyor |
| OCR satırı elle seçilirken seçilmeyen marka/model ilk taramadan taşınıyordu | Kullanıcının reddettiği yanlış kimlik Radar sorgusuna girebiliyordu | OCR kaynaklı marka, model, GTIN ve stil kodu yalnız seçilen metinde kanıtlanıyorsa taşınıyor; kamera tarafından çözülen barkod/QR kanıtı korunuyor |

Lens yükleme endpoint'ine ayrıca boş dosya ve görüntü olmayan MIME türü denetimi eklendi. Google Lens sonucu, resmî ve kararlı bir tüketici API'si değildir; kamuya açık sonuç sayfasının değişebilen HTML'inden en iyi çabayla aday üretir. CAPTCHA veya erişim koruması görülürse otomatik aşma denenmez, açık hata döndürülür. Bu yol çekirdek Radar motorlarının yerine değil, kullanıcı tarafından başlatılan isteğe bağlı aday üretme katmanı olarak değerlendirilmelidir.

### 31.2 Mobil uygulama kararı ve APK kapsamı

Depoda iki Android yapı vardır:

1. `frontend/android`: Capacitor tarafından üretilen web kabuğu;
2. `mobile/android`: sunucu adresi ayarı, WebView, Google Code Scanner, CameraX, cihazda ML Kit OCR, dondurulmuş kare üzerinde metin kutusu seçimi ve Radar'a aktarım içeren özellikli test uygulaması.

Bir haftalık deneme için ikinci yapı esas alınmıştır. Bu seçim, kamera/OCR özelliklerini kaybetmeden mevcut React Radar ekranlarını kullanır. Üretilen APK `mobile/dist/ShoeHunter-Radar-0.1.0-test.apk` dosyasıdır; varsayılan test sunucusu `http://192.168.1.131:3000` olarak derlenmiştir ve uygulama içindeki Sunucu Ayarları ekranından değiştirilebilir.

APK kanıtı:

| Alan | Değer |
|---|---|
| Derleme | `assembleDebug` başarılı |
| Dosya boyutu | 48.398.521 bayt |
| SHA-256 | `48361604503F0731C1E4381FBB6BFA8F27C020F3732EEE1B97A0B475511C70BF` |
| Barkod | EAN-13, EAN-8, UPC-A/E, Code 128, QR, Data Matrix |
| OCR | CameraX + APK içinde ML Kit Latin modeli; metin okuma cihazda çalışır |
| Sunucu ihtiyacı | Ürün arama, fiyat ve Radar kaydı için telefon/tablet ile bilgisayar aynı ağa bağlı olmalıdır |

### 31.3 Doğrulama kanıtı

| Katman | Sonuç |
|---|---|
| Tüm backend testleri | 239/239 geçti; 1 isteğe bağlı test atlandı |
| Tüm frontend testleri | 24/24 geçti |
| React production build | Başarılı |
| Native OCR seçim/geometri JUnit testleri | 7/7 geçti |
| Android debug APK derlemesi | Başarılı |

Android Gradle'ın `testDebugUnitTest` worker süreci bu Windows ortamında `GradleWorkerMain` sınıf yolunu yükleyemedi. Aynı test kaynakları aynı JDK, JUnit 4.13.2 ve Hamcrest ile doğrudan derlenip çalıştırılmış ve 7/7 geçmiştir. Uygulamanın `assembleDebug` derlemesi de başarıyla tamamlanmıştır; dolayısıyla bu kayıt kod testi başarısızlığı değil, Gradle test-worker ortam uyumsuzluğudur.

### 31.4 Bugün tamamlanan ile kalan hedeflerin kesin ayrımı

**Tamamlanan:** barkod ve OCR kimlik çıkarımı, seçilebilir OCR, ürün kodu/GTIN öncelikli Radar sorgusu, sıkı kimlik filtresi, Google Shopping metin araması için isteğe bağlı adaptör, Google Lens görsel sonucu için isteğe bağlı en-iyi-çaba adaptörü, native Android barkod/OCR köprüsü, çevrimdışı kuyruk, yerel bildirim beslemesi, GS1 çözümleme/üretme, güvenli görsel aday kataloğu, fiziksel fiyat kanıtı ve kurulabilir test APK'sı.

**Dış veri/model gerektiren ve bu nedenle tamamlandı denmeyen:** lisansı ve SHA-256 değeri onaylı gerçek OpenCLIP checkpoint'inin kurulması, büyük katalog popülasyonu, etiketli saha setinde ölçülmüş görsel top-5 recall, pgvector/Qdrant ölçek geçişi, internet dışından anlık FCM teslimi ve tam 3B/ARCore nesne takibi.

Mevcut kamera deneyimi canlı aday bilgisi bindirmesini içerir; exact SKU veya 3B konum takibi iddia etmez. Görsel katalog varsayılan olarak deterministik yerel parmak iziyle güvenli aday üretir. OpenCLIP hattı yalnız kullanıcı tarafından sağlanan, hash'i doğrulanan yerel checkpoint ile etkinleşir; otomatik model indirme yapılmaz.

## 32. 21 Temmuz 2026 — bütün önerilerin uygulama turu

Bu bölüm “rapordaki öneriler gerçekten koda uygulandı mı?” sorusunun kesin durum kaydıdır. Aşağıdaki maddeler bu son turda çalışan koda bağlanmış ve test edilmiştir.

### 32.1 Görsel katalog ve vektör hazırlığı

- MongoDB üzerinde kalıcı `visual_candidate_index` koleksiyonu ve indeksleri eklendi.
- Görsel indeksleme yalnız yüklenen görüntü baytlarını kabul eder; sunucunun keyfî URL veya dosya yolu okumasına izin verilmez. Bu tasarım SSRF ve yerel dosya sızıntısı riskini kapatır.
- Kayıtlar canonical ürün, varyant, kaynak, GTIN, ürün kodu ve lisans/kanıt alanlarıyla doğrulanır.
- Arama yalnız aday üretir; görsel benzerlik exact SKU kanıtı sayılmaz.
- Varsayılan sağlayıcı deterministik yerel görsel parmak izidir. OpenCLIP desteği hazırdır fakat yalnız `OPENCLIP_MODEL_NAME`, yerel `OPENCLIP_CHECKPOINT_PATH`, beklenen `OPENCLIP_WEIGHTS_SHA256` ve `OPENCLIP_LICENSE_ID` birlikte verilirse açılır. Ağdan otomatik ağırlık indirilmez.
- Ürün ayrıntı ekranına fotoğrafla benzer aday arama, güven skoru, canonical ürüne geçiş ve doğrulanmış mevcut ürün görselini kataloğa ekleme akışı getirildi.

### 32.2 GS1, barkod ve QR

- GS1 Digital Link URI ayrıştırma, doğrulanmış GTIN-14 üretme ve GS1 insan-okunur element string ayrıştırma uçları eklendi.
- Desteklenen temel uygulama tanımlayıcıları: GTIN `(01)`, lot `(10)`, üretim `(11)`, best-before `(15)`, sell-by `(16)`, son kullanma `(17)`, seri `(21)` ve tüketici varyantı `(22)`.
- Native QR içeriği GS1 Digital Link ise Radar sorgusu GTIN öncelikli hazırlanır; lot, seri ve tarih kanıtları kaybolmaz.
- Düz metin ürün kodu ve isim, QR, EAN/UPC ve OCR hâlâ aynı kimlik kanıt modelinde ayrı roller olarak tutulur.

### 32.3 Fiziksel mağaza fiyat kanıtı

- Ürün ayrıntı ekranına mağaza, şube, fiyat, kanıt türü, GTIN, ürün kodu ve fotoğraf içeren fiziksel fiyat formu eklendi.
- Raf etiketi, fiş ve kullanıcı beyanı aynı fiyat türü gibi birleştirilmez.
- Ham fotoğraf güvenli yükleme yolundan işlenir; kanıt hash'i, zaman, kaynak ve ürün kimliği birlikte saklanır.
- Doğrulanmış fiyat için ikinci bağımsız kanıt/moderasyon akışı ve onay/red işlemi bulunur.
- Fiziksel fiyat, çevrimiçi sepet/kargo/toplam maliyet hesabından ayrı gösterilir; böylece kanıt rolleri karışmaz.

### 32.4 Aile profili, beden ve bildirim kuralları

- Birden fazla aile üyesi, kişi başına birden fazla ayakkabı numarası ve kategoriye özel beden kümeleri mevcut profil sisteminde korunmuştur.
- Takip kaydı profilin o andaki beden hedeflerinin snapshot'ını tutar; sonraki profil değişikliği geçmiş takibi sessizce değiştirmez.
- Aktif kurallar: son numara/beden fırsatı, numaran yeniden stokta, indirimli fiyattan yeniden stokta, tek renk/tek numara geri geldi, fiyat düştü ve numaran mevcut, sepette fiyat devam ediyor, stok kritik, dönem dibi, yeni ilan ve yeni varyant.
- Genel fiyat düşüşü eşiği yüzde 3 ve Radar periyodu 6 saat olarak desteklenir. Linkten, barkoddan, OCR'dan, görselden veya AI destekli girişten oluşan kayıt aynı Radar ve bildirim hattına girer.
- Bildirim içeriğinde ürün, mağaza, uygun numara/beden, fiyat, zaman ve bağlantı alanları taşınır.

### 32.5 Android çevrimdışı kullanım ve bildirim

- Barkod/OCR sonucu ağ yokken cihazdaki kalıcı outbox'a yazılır; bağlantı geldiğinde Radar ekranına aktarılır.
- Kuyruk topluca silinmez. Web tarafı olayı teslim aldığında yalnız ilgili `outbox_id` native katmana onaylanır ve sadece o kayıt silinir. Bu, kısmi aktarımda veri kaybını önler.
- Cihaz, oturumdan türetilmiş geri alınabilir ve sunucuda hash'li saklanan cihaz token'ı ile bildirim beslemesine kaydolur.
- WorkManager ağ bağlantısı olduğunda arka planda `/api/mobile/alerts` beslemesini denetler; yeni olayları Android yerel bildirimi olarak ürün/mağaza/beden/fiyat bilgisiyle gösterir.
- Bu yöntem kendi sunucusu üzerinden bir haftalık test için dış ücretli push API'si gerektirmez. Uygulama tamamen kapalıyken internet üzerinden gerçek zamanlı FCM push ayrıca kurulmamıştır; mevcut çözüm periyodik ve ağ-koşullu senkronizasyondur.

### 32.6 Kamera bilgi bindirmesi

- CameraX OCR görüntüsünün üzerinde canlı marka, ürün kodu, GTIN ve görünür fiyat adayını gösteren bilgi bindirmesi eklendi.
- Bindirme “aday” olarak etiketlenir; kullanıcı seçimi ve kimlik kanıtı olmadan exact ürün iddiası üretmez.
- Bu, saha kullanımına yararlı AR-benzeri kamera katmanıdır. ARCore ile 3B nesne sabitleme veya mağaza içi mekânsal yönlendirme yapılmış sayılmaz.

### 32.7 Son doğrulama ve teslim

| Kontrol | Sonuç |
|---|---|
| Backend test paketi | 239 geçti, 1 isteğe bağlı test atlandı |
| Frontend test paketi | 24 geçti |
| React üretim derlemesi | Başarılı |
| Native saf JUnit | 7 geçti |
| Android `assembleDebug` | Başarılı |
| Güncel APK | `mobile/dist/ShoeHunter-Radar-0.1.0-test.apk` |
| APK boyutu | 48.398.521 bayt |
| APK SHA-256 | `48361604503F0731C1E4381FBB6BFA8F27C020F3732EEE1B97A0B475511C70BF` |

### 32.8 Kesin kalan hedefler

Kod altyapısı tamamlanmış olsa da aşağıdaki sonuçlar dosya yazarak dürüstçe üretilemez; dış varlık veya saha ölçümü gerektirir:

1. Lisansı onaylanmış OpenCLIP checkpoint'i sağlanmalı, hash sabitlenmeli ve gerçek katalog görselleri indekslenmelidir.
2. Etiketli gerçek kullanıcı fotoğraflarıyla top-5 recall, varyant karışıklığı ve yanlış exact eşleşme oranı ölçülmelidir.
3. Katalog hacmi Mongo tabanlı tarama sınırını aşarsa pgvector veya Qdrant'a aynı metadata/kanıt sözleşmesiyle geçilmelidir.
4. Telefon farklı ağdayken anlık bildirim istenirse sunucu HTTPS üzerinden erişilebilir yapılmalı ve FCM/APNs yaşam döngüsü eklenmelidir.
5. 3B ARCore ancak kamera aday doğruluğu, pil tüketimi ve gizlilik saha hedefleri geçildikten sonra geliştirilmelidir.

Bu sınırlar özelliklerin unutulması değildir. Yanlış doğruluk veya tamamlanmışlık iddiası üretmemek için ölçülebilir geçiş kapılarıdır.

## 33. 22 Temmuz 2026 — rapor sırasıyla devam uygulaması

### 33.1 Doğrulanmış gerçek embedding modeli

Python 3.14 çalışma ortamında güncel OpenCLIP/PyTorch dağıtımının ağır ve uyumsuz bağımlılık riski nedeniyle aynı CLIP ViT-B/32 görsel kulesinin Qdrant tarafından yayımlanan ONNX portu seçildi. Model kartı kullanım amacını görüntü benzerliği olarak tanımlar ve MIT lisansı bildirir. Model hiçbir istek sırasında indirilmez; yalnız yerel dosyadan yüklenir.

| Alan | Doğrulanan değer |
|---|---|
| Model | `Qdrant/clip-ViT-B-32-vision` |
| Çalıştırıcı | ONNX Runtime CPU |
| Boyut | 351.686.194 bayt |
| Embedding | 512 boyut |
| Lisans kaydı | MIT |
| SHA-256 | `c68d3d9a200ddd2a8c8a5510b576d4c94d1ae383bf8b36dd8c084f94e1fb4d63` |
| Kaynak | [Qdrant model kartı](https://huggingface.co/Qdrant/clip-ViT-B-32-vision) |

Uygulama başlangıcında yerel dosyanın SHA-256 değeri doğrulanır; girişin `pixel_values`, çıkışın `image_embeds[512]` olduğu kontrol edilir. Dosya veya sözleşme farklıysa embedding özelliği kapalı kalır. Eski, üçüncü taraf URL'den otomatik ONNX indiren kod yolu kaldırılmıştır. Yeni kurulumlarda `scripts/setup-visual-model.ps1` sabitlenmiş model revizyonunu indirir, `.part` dosyasını hash ile doğrular ve yalnız doğrulama geçerse etkin dosya adına taşır.

### 33.2 Gerçek katalog popülasyonu

Veritabanındaki 245 görselli listing için mağaza bazında açık CDN izin listesi uygulandı. HTTPS, standart port, kullanıcı/parola içermeyen URL, genel IP DNS çözümü, her yönlendirmede yeniden alan adı doğrulama, en fazla 12 MB yanıt ve JPEG/PNG/WebP tür kontrolü zorunlu tutuldu.

Sonuç:

- 245 aday kaydın 243'ü başarıyla embedding kataloğuna alındı;
- 243 kaydın tamamında doğrulanmış model descriptor'ı ve embedding bulunuyor;
- 17 mağaza kaynağı ve `shoes`, `tops`, `bottoms`, `outerwear`, `products` kategorileri oluştu;
- iki eski Trendyol görseli üç kontrollü denemede de CDN tarafından HTTP 503 döndürdü;
- başarısız iki görsel ürünün piyasada olmadığı şeklinde yorumlanmadı;
- indeksleme idempotenttir: tekrar koşuda var olan kayıtlar indirilip yeniden hesaplanmaz.

Katalog komutu: `scripts/index-visual-catalog.py`. Komut yalnız veritabanındaki listing görsellerini ve mağaza-CDN eşleşmesini kullanır; rastgele URL almaz.

### 33.3 Etiketli saha benchmark'ı ve bulunan varyant sorunu

Kullanıcının gönderdiği dört gerçek etiket fotoğrafı, katalogda karşılığı bulunan `JH6206`, `JF2443`, `KC1948` ve `JF2847` kodlarıyla etiketlendi. Aynı 243 kayıt üzerinde iki yöntem karşılaştırıldı:

| Yöntem | Top-1 | Top-5 | Top-5 recall | MRR |
|---|---:|---:|---:|---:|
| Yalnız görsel embedding | 0/4 | 2/4 | %50 | 0,1217 |
| Görsel + OCR/ürün kodu + marka kanıtı | 4/4 | 4/4 | %100 | 1,0000 |

Yalnız görsel yönteminde `JH6206` adayı 50. sırada kaldı; ilk sıraları görsel olarak benzer fakat farklı kodlu Adizero EVO SL varyantları aldı. `KC1948` 15. sırada kaldı. Bu doğrudan varyant karışıklığı kanıtıdır ve “görsel benzerlik exact SKU değildir” kuralını doğrular.

Bunun üzerine aday sıralamasına isteğe bağlı `model_code_hint` ve `brand_hint` kanıt füzyonu eklendi. İpucu native OCR, barkod/QR veya kullanıcının doğruladığı ürün kodundan gelir. Kod eşleşmesi adayı yükseltir fakat sonuç alanı hâlâ `candidate_only=true`, `exact_sku_decision=false` kalır. Ürün ayrıntı ekranı mevcut ürün kodu ve markayı otomatik olarak bu aramaya taşır; kategori bilinmiyorsa yanlış `other` filtresi uygulamak yerine açık çapraz kategori araması yapar.

Benchmark yeniden çalıştırılabilir: `scripts/benchmark_visual_catalog.py`. Dört örnek küçük bir doğrulama setidir; %100 hibrit sonuç genel saha başarısı iddiası değildir. Yeni marka, açı, ışık, ambalaj ve benzer varyantlardan daha büyük kör test seti eklenmelidir.

### 33.4 Vektör veritabanı geçiş kararı

Mevcut hacim 243 kayıttır; raporda tanımlanan 100.000 kayıt geçiş eşiğinin çok altındadır. Bu nedenle bu aşamada pgvector/Qdrant servis bağımlılığı eklemek gereksiz operasyon yükü oluşturur. İstatistik endpoint'i artık kullanılan depolamayı, 100.000 kayıt eşiğini, kalan kapasiteyi ve geçiş önerisi durumunu açıkça döndürür. Eşik aşılırsa aynı metadata/model-descriptor sözleşmesi korunarak ayrı vektör veritabanına geçilecektir.

### 33.5 Sıradaki koşullu hedefler

Rapor sırasındaki sonraki iki hedef koşulludur:

1. Telefon sunucuyla farklı ağda ve anlık bildirim gerektiriyorsa Firebase projesi, Android `google-services.json`, FCM API etkinliği, HTTPS sunucu adresi ve sunucu ADC/service-account yetkisi gerekir. Mevcut WorkManager + cihaz token'lı kendi-sunucu bildirimi aynı ağ/test kullanımı için çalışmaya devam eder. FCM kimlik bilgileri olmadan sahte bir “push tamamlandı” kaydı oluşturulmayacaktır.
2. Tam 3B ARCore, daha geniş kör saha setinde kamera kimlik doğruluğu, varyant karışıklığı, pil ve gizlilik hedefleri geçildikten sonra başlatılacaktır. Mevcut canlı kamera bindirmesi 3B AR olarak adlandırılmaz.

Dolayısıyla rapor sırasındaki ilk dört maddeden model kurulumu, katalog popülasyonu ve ölçüm tamamlandı; vektör veritabanı geçişinin koşulu oluşmadığı ölçümle kanıtlandı. Son iki madde dış Firebase projesi/kimlik bilgisi ve daha geniş saha ölçümü beklemektedir.

### 33.6 Bu turun son doğrulaması

| Kontrol | Sonuç |
|---|---|
| Backend test paketi | 241 geçti, 1 isteğe bağlı test atlandı |
| Frontend test paketi | 24/24 geçti |
| React üretim derlemesi | Başarılı (`main.0dcda0f1.js`) |
| FastAPI yükleme kontrolü | 88 rota başarıyla yüklendi |
| Doğrulanmış ONNX model smoke testi | 512 boyutlu sonlu ve normalize embedding üretildi |
| Katalog | 243/245 görsel indeksli; iki CDN 503 kaydı açıkça raporlu |
| Benchmark | Görsel %50 top-5; OCR/kod füzyonu %100 top-5, küçük `n=4` set uyarısıyla |
| Exact SKU güvenlik kuralı | Tüm görsel/hibrit sonuçlarda `exact_sku_decision=false` |

## 34. 22 Temmuz 2026 — ShopHunter-Radar FCM HTTP v1 uygulaması

### 34.1 Firebase kimliği ve güvenli anahtar kullanımı

Firebase projesi ve Android test uygulaması aşağıdaki bilgilerle doğrulandı:

| Alan | Değer |
|---|---|
| Firebase görünen adı | `ShopHunter-Radar` |
| Firebase Project ID | `shophunter-radar` |
| Firebase Project Number | `526501879181` |
| Android debug package | `com.shoehunter.radar.debug` |
| Android yapılandırması | `mobile/android/app/google-services.json` |
| Sunucu yetkilendirmesi | ADC + ayrı servis hesabı JSON dosyası |
| Gönderim protokolü | FCM HTTP v1 |

`google-services.json` doğru debug package ile eşleşmektedir ve Git dışında tutulması için `.gitignore` kapsamına alınmıştır. Sunucu servis hesabı dosyası proje klasörüne kopyalanmamış, içeriği rapora/loglara yazılmamış ve `scripts/start-lan.ps1` tarafından yalnız çalışma zamanında `GOOGLE_APPLICATION_CREDENTIALS` üzerinden ADC'ye tanıtılmıştır. Legacy Cloud Messaging API kullanılmamıştır; kapalı kalması beklenen ve doğru durumdur. Gerekli en dar IAM rolü `roles/firebasecloudmessaging.admin` rolüdür.

### 34.2 Android anlık bildirim hattı

- Google Services Gradle eklentisi `4.5.0`, Firebase BoM `34.16.0` ve sürümsüz `firebase-messaging` bağımlılığı bağlandı.
- Güncel Firebase Installation ID (FID) kaydı manifest bayrağıyla etkinleştirilir; eski registration-token akışı kullanılmaz.
- FCM kaydı oluştuğunda veya FID değiştiğinde `FirebaseMessagingService.onRegistered` güncel FID'yi sunucuya taşır.
- FCM mesajı ürün, mağaza, numara/beden, fiyat, alarm sınıfı ve HTTPS ürün bağlantısını veri alanlarıyla taşır.
- Bildirime dokunulduğunda doğrulanmış HTTPS ürün bağlantısı açılır.
- FCM ve WorkManager aynı alarmı getirirse `alert_id` tabanlı, son 100 kayıtla sınırlı cihaz-içi tekrar engelleme uygulanır.
- Mevcut 15 dakikalık WorkManager alarm beslemesi kaldırılmamıştır. FCM/Google Play servisleri veya internet anlık teslimi bozarsa güvenli yedek olarak çalışmaya devam eder.

### 34.3 Sunucu FCM gönderimi

- Python Firebase Admin SDK `7.5.0` kuruldu ve bağımlılıklara sabitlendi.
- `shophunter-radar` projesi servis hesabı ile ADC başlatma smoke testi geçti.
- Mobil cihaz ve FCM FID kaydı için ayrı uçlar oluşturuldu. FID güncelleme ucu tarayıcı çerezine güvenmez; geri alınabilir cihaz bearer token'ını doğrular.
- Cihaz auth token'ı yalnız SHA-256 hash olarak saklanır. FID hash'i benzersiz indeks için ayrıca tutulur; gönderim için gereken FID veritabanında erişim kontrollü kayıt olarak kalır ve hiçbir yanıta/loga eklenmez.
- Aynı FID başka cihaz kaydına taşınırsa eski bağlantı temizlenir. Firebase `UnregisteredError` veya sender uyuşmazlığı döndürürse geçersiz FID otomatik kaldırılır.
- Geliştiriciye özel parser/listing hata alarmları müşteriye push edilmez. Diğer aktif radar sınıfları aynı FCM hattından geçer.
- Telegram sonucu ile FCM sonucu ayrı alanlarda saklanır; kanallardan biri başarılıysa alarm genel gönderim durumu başarılı kabul edilir.

### 34.4 Doğrulama ve APK teslimi

| Kontrol | Sonuç |
|---|---|
| Firebase Admin SDK | `7.5.0` kurulu |
| ADC başlatma | Başarılı, Project ID `shophunter-radar` |
| HTTP v1 IAM yetki testi | Yetkili istek FCM'e ulaştı; rastgele FID için beklenen `UnregisteredError`, `PermissionDenied=false` |
| Google Services Gradle adımı | `processDebugGoogleServices` başarılı |
| Android `assembleDebug` | Başarılı |
| Backend test paketi | 244 geçti, 1 isteğe bağlı test atlandı |
| Mobil FCM FID güvenlik testi | Kayıt, bearer doğrulama, FID yenileme ve hash kontrolü geçti |
| APK package | `com.shoehunter.radar.debug` |
| FCM service/intent/channel | Birleştirilmiş manifestte doğrulandı |
| Android sürümü | `versionCode=2`, `versionName=0.1.1-test` |
| APK | `mobile/dist/ShopHunter-Radar-0.1.1-test.apk` |
| APK boyutu | 49.473.470 bayt |
| APK SHA-256 | `B52F4A09CD872B17F72838832516F9E94442300EC2094D6C47A630DC83815573` |

### 34.5 Kalan tek saha doğrulaması

Canlı uçtan uca teslim henüz tamamlanmış sayılmaz; yeni APK telefona/tablete kurulup uygulamada oturum açılmadan gerçek cihaz FID'si oluşmaz ve sunucuda gönderilecek hedef kurulum bulunmaz. APK kurulduktan sonra bildirim izni verilmeli, ShopHunter sunucusuna bir kez giriş yapılmalı ve cihaz kaydının oluşması beklenmelidir. Sonraki gerçek radar alarmı veya kontrollü test alarmı ile ekran kapalı/uygulama kapalı teslim süresi ölçülecektir. Bu saha adımı kod, Firebase projesi veya servis hesabı eksiği değil; gerçek hedef kurulum FID'sine bağlı son teslim doğrulamasıdır.

## 35. 22 Temmuz 2026 — Android kamera açılışı ve gerçek cihaz kaydı

### 35.1 Bulunan kamera sorunu ve düzeltme

Radar ekranındaki `Etiketi / Barkodu Oku` alanı HTML tarafında `capture="environment"` ile arka kamerayı istiyordu. Android WebView dosya-seçici katmanı bu isteği kontrol etmediği için kullanıcıya doğrudan kamera yerine dosya/galeri seçimi gösteriliyordu. `WebChromeClient.onShowFileChooser` artık `FileChooserParams.isCaptureEnabled()` değerini denetler; arka kamera isteği ve kullanılabilir kamera uygulaması varsa `ACTION_IMAGE_CAPTURE` doğrudan açılır. Kamera bulunamazsa dosya seçici güvenli yedek olarak kalır. Çekilen görüntünün mevcut OCR, barkod, ürün kodu ve Radar'a kontrollü aktarma hattı değiştirilmemiştir.

### 35.2 Gerçek cihaz ve yeni APK durumu

Telefonun `POST /api/mobile/device/register` isteği canlı sunucu kaydında HTTP 200 olarak, ardından FCM FID güncellemesi `POST /api/mobile/device/push-registration` HTTP 200 olarak görüldü. Bu, oturum açan gerçek cihazın sunucuya ve FCM hedef kaydına ulaştığını kanıtlar; ekran kapalı anında bildirim teslimi ayrı saha testi olarak kalır.

| Kontrol | Sonuç |
|---|---|
| Android `assembleDebug` | Başarılı |
| Frontend regresyon testleri | 24/24 geçti |
| Gerçek cihaz kaydı | HTTP 200 |
| Gerçek cihaz FCM FID kaydı | HTTP 200 |
| Android sürümü | `versionCode=2`, `versionName=0.1.1-test` |
| APK | `mobile/dist/ShopHunter-Radar-0.1.1-test.apk` |
| APK boyutu | 49.473.470 bayt |
| APK SHA-256 | `B52F4A09CD872B17F72838832516F9E94442300EC2094D6C47A630DC83815573` |

Kamera davranışı yerel Android kodunda düzeltildiği için telefondaki önceki APK'nın yeni APK ile güncellenmesi gerekir. Kurulumdan sonraki ilk saha kontrolünde Radar ekranındaki `Etiketi / Barkodu Oku` düğmesine dokunulduğunda arka kameranın dosya seçici gösterilmeden açılması beklenir.

## 36. 22 Temmuz 2026 — WebView kamera çökmesi düzeltmesi

0.1.1 saha denemesinde `Etiketi / Barkodu Oku` düğmesine basıldığında `org.chromium.base.JniAndroid$UncaughtExceptionException` ile uygulamanın kapandığı bildirildi. Paylaşılan kesit Java `Caused by` satırını içermediğinden tek OEM istisna sınıfı kesinleştirilemedi; ancak hata, doğrudan kamera değişikliğinde Android kamera izni kontrol edilmeden `ACTION_IMAGE_CAPTURE` başlatılması ve bu yoldaki yalnız `ActivityNotFoundException` türünün yakalanmasıyla aynı noktada oluştu. Bir Android `SecurityException`, MediaStore veya OEM kamera `RuntimeException` hatası WebView geri çağrısından JNI katmanına kaçabiliyordu.

0.1.2-test sürümünde:

- doğrudan kamera açılmadan önce Android `CAMERA` izni kontrol edilir;
- izin yoksa kullanıcıdan sistem izin ekranıyla istenir;
- izin verilirse kamera açılır;
- izin reddedilirse uygulama kapanmaz ve resim galerisi açılır;
- MediaStore, kamera uygulaması, dosya seçici ve eski WebView callback hataları `RuntimeException` sınırında yakalanır;
- başarısız/geçersiz kamera URI ve WebView dosya callback durumları temizlenir;
- eski APK'nın üstüne güvenilir güncelleme kurulabilmesi için sürüm kodu 3'e yükseltildi.

| Kontrol | Sonuç |
|---|---|
| Android `assembleDebug` | Başarılı |
| Paket | `com.shoehunter.radar.debug` |
| Sürüm | `versionCode=3`, `versionName=0.1.2-test` |
| APK | `mobile/dist/ShopHunter-Radar-0.1.2-test.apk` |
| APK boyutu | 49.474.390 bayt |
| APK SHA-256 | `6B4330FB44B252C160BE8BB3648B7EB320146420D5D6B37AAFB57EDA495C12C9` |

Kaynak derlemesi ve paket metadata kontrolü geçti. Gerçek cihazın USB/ADB bağlantısı bulunmadığı için OEM kamera davranışı bilgisayardan otomatik doğrulanamadı; son kabul adımı 0.1.2 APK telefona kurulduktan sonra kamera izni verilerek yapılacaktır.

## 37. 22 Temmuz 2026 — gerçek cihaz FCM bildirim testi

Kamera saha kontrolünden sonraki plan adımı olan gerçek cihaz Firebase testi uygulandı. `scripts/send-fcm-device-test.py` yalnız etkin ve FCM kurulum kimliği bulunan cihazları hedefler; cihaz kimliğini, FID'yi veya cihaz yetkilendirme belirtecini ekrana/loga yazmaz.

| Kontrol | Sonuç |
|---|---|
| Etkin ve FCM kayıtlı cihaz | 1 |
| FCM tarafından kabul edilen gönderim | 1 |
| Gönderim hatası | 0 |
| Sunucu sonucu | `sent=true` |
| Test zamanı | `2026-07-22 09:32:47 +03:00` |
| Test alarm kimliği | `fcm-device-test-439ac329-7df4-4dc5-8273-fb9e1a40c39d` |

Bu sonuç sunucu → Firebase HTTP v1 → kayıtlı cihaz hedefi hattının FCM tarafından kabul edildiğini kanıtlar. Kullanıcı, `ShopHunter Radar bildirim testi` başlıklı bildirimin telefonun bildirim paneline ulaştığını teyit etti. Böylece sunucu → FCM → Android servis → bildirim paneli zincirinin gerçek cihaz uçtan uca saha kabulü tamamlandı.

| Son saha kabulü | Durum |
|---|---|
| Telefon bildirim panelinde görünme | **Teyit edildi** |
| Uçtan uca FCM hattı | **Tamamlandı** |

Bu teyitten sonraki plan adımı, telefon farklı ağdayken uygulamanın kişisel sunucuya erişebilmesi için Tailscale özel ağ kurulumudur.

## 38. 22 Temmuz 2026 — Tailscale özel HTTPS hazırlığı ve 0.1.3 APK

### 38.1 Hedef ve güvenlik sınırı

Amaç, ShopHunter-Radar sunucusunu genel internete açmadan telefondan ve tabletten farklı mobil/Wi-Fi ağları üzerinden erişilebilir kılmaktır. Bunun için Tailscale Serve hedeflenmiştir. Serve yalnız aynı Tailscale özel ağına (`tailnet`) giriş yapmış cihazlara HTTPS erişimi sağlar. Genel internete açık Tailscale Funnel özellikle etkinleştirilmemiştir.

Resmî Windows MSI paketi `1.98.9` indirildi. İndirilen dosyanın SHA-256 değeri yayımlanan sağlama değeriyle karşılaştırıldı ve Windows Authenticode imzası `Tailscale Inc.` adına `Valid` olarak doğrulandı.

| Paket kontrolü | Sonuç |
|---|---|
| Dosya | `tailscale-setup-1.98.9-amd64.msi` |
| SHA-256 | `07BCB57D3BD34A0299D98133F1A0091DB2CE66831AA7C100F456E2269A41E665` |
| Authenticode | Geçerli — `Tailscale Inc.` |
| Funnel/genel yayın | Etkinleştirilmedi |

### 38.2 Tek HTTPS kök adresi için uygulama değişiklikleri

- FastAPI artık `frontend/build` üretim çıktısını `/` ve istemci rotalarından sunar; `/api/*` istekleri SPA geri dönüşüne düşmez.
- HTTP yerel ağ kullanımında mevcut `http://sunucu:8000` davranışı korunur.
- HTTPS/Tailscale Serve kullanımında arayüz API kökü olarak aynı HTTPS origin'i kullanır. Böylece ayrı bir açık API portu veya karma içerik izni gerekmez.
- Android cihaz/FCM kaydı, HTTPS sayfada kayıtlı özel bir adres yoksa `location.origin` üzerinden yapılır.
- Ters vekilin `X-Forwarded-Proto: https` başlığıyla gelen kurulum ve giriş yanıtlarında oturum ve CSRF çerezleri `Secure` olarak üretilir.
- `scripts/configure-tailscale-serve.ps1`, yerel sağlık kontrolünden sonra yalnız `http://127.0.0.1:8000` hedefini kalıcı Tailscale Serve HTTPS servisine bağlamak üzere eklendi.

### 38.3 Çalışan sunucu doğrulaması

Eski 8000 portu süreci kapatılıp güncel FastAPI süreci temiz biçimde başlatıldı. Aynı portta hem üretim arayüzü hem API doğrulandı:

| İstek | Sonuç |
|---|---|
| `GET http://127.0.0.1:8000/` | HTTP 200, HTML |
| `GET http://127.0.0.1:8000/radar` | HTTP 200, HTML |
| `GET http://127.0.0.1:8000/api/health` | HTTP 200, JSON |

### 38.4 Regresyon testleri ve yeni APK

| Kontrol | Sonuç |
|---|---|
| Backend test paketi | **245 geçti, 1 isteğe bağlı test atlandı** |
| Frontend test paketi | **25/25 geçti** |
| React üretim derlemesi | Başarılı (`main.7e5b7487.js`) |
| Tailscale PowerShell betiği | Sözdizimi doğrulaması geçti |
| Android derleme | Başarılı |
| Paket | `com.shoehunter.radar.debug` |
| Sürüm | `versionCode=4`, `versionName=0.1.3-test` |
| APK | `mobile/dist/ShopHunter-Radar-0.1.3-test.apk` |
| APK boyutu | 49.474.394 bayt (47,18 MiB) |
| APK SHA-256 | `D5004122A5CEB9FD1A4D139678E00D79FD934B930E18FDB7D50B28806B96EEAB` |

### 38.5 Kalan dış sistem adımı

MSI sessiz kurulum denemesi Windows Installer günlüğünde `This package requires elevated privileges to install` ve hata `1603` ile durdu. Bu bir paket, kod veya servis bağımlılığı hatası değildir; mevcut otomasyon oturumunun Windows UAC yönetici belirtecini MSI'a aktaramamasıdır. Kurulumun tamamlanması için bilgisayarda kullanıcı tarafından yalnız bir kez aşağıdaki işlem gerekir:

1. `%TEMP%\tailscale-setup-1.98.9-amd64.msi` dosyasını açın.
2. `Install` ve ardından Windows UAC ekranında `Evet` seçin.
3. Tailscale'de kullanıcı hesabıyla giriş yapın.
4. Telefona/tablete resmî Tailscale uygulamasını kurup aynı hesaba/tailnet'e giriş yapın ve Android VPN iznini verin.
5. Ardından `scripts/configure-tailscale-serve.ps1` çalıştırılarak özel HTTPS adresi üretilecek ve telefon Wi-Fi kapalıyken mobil veri üzerinden son saha testi yapılacaktır.

Bu son kullanıcı/UAC adımı tamamlanmadan Tailscale'in kurulduğu, özel HTTPS adresinin üretildiği veya hücresel ağ testinin geçtiği iddia edilmemiştir. Sunucu, uygulama kodu, doğrulama betiği ve 0.1.3 APK bu son bağlantı kabulü için hazırdır.

### 38.6 Kurulum ve tailnet giriş kabulü

Kullanıcı Windows MSI/UAC kurulumunu tamamladı. Kurulum sonrası aşağıdaki durumlar gerçek makinede doğrulandı:

| Kontrol | Sonuç |
|---|---|
| Tailscale sürümü | `1.98.9` |
| Windows `Tailscale` servisi | `Running`, başlangıç türü `Automatic` |
| Tailscale özel ağ bağlantısı | Başarılı |
| Tailscale IPv4 | `100.93.18.127` |
| MagicDNS son eki | `tail135515.ts.net` |
| Beklenen bilgisayar adı | `pc1.tail135515.ts.net` |
| Yerel ShopHunter sunucusu | `http://127.0.0.1:8000`, sağlık kontrolü başarılı |
| Tailscale HTTPS Serve | **Başarılı** |
| Özel uygulama adresi | `https://pc1.tail135515.ts.net` |
| HTTPS `/` | HTTP 200, HTML |
| HTTPS `/radar` | HTTP 200, HTML |
| HTTPS `/api/health` | HTTP 200, `{"status":"ok","database":true,"version":"0.6.0"}` |
| TLS sertifika doğrulaması | Başarılı; doğrulama kapatılmadan HTTP 200 alındı |

Windows kurulumu, tailnet hesabına giriş ve Tailscale Serve özel HTTPS yayını tamamlanmıştır. `scripts/configure-tailscale-serve.ps1` betiği `http://127.0.0.1:8000` hedefini kalıcı arka plan Serve yapılandırmasına bağladı ve gizli anahtar içermeyen `mobile/tailscale-connection.json` sonuç kaydını üretti; bu makineye özel dosya Git dışında tutulur. Bilgisayar tarafındaki son kabul tamamlandı. Kalan tek dış cihaz kabulü, Android Tailscale uygulamasında aynı tailnet'e giriş yaptıktan sonra telefon Wi-Fi kapalı ve mobil veri açıkken `https://pc1.tail135515.ts.net` adresine erişildiğinin doğrulanmasıdır.

## 39. 22 Temmuz 2026 — Tailscale üzerinden veri yüklenememesi düzeltmesi ve 0.1.4 APK

### 39.1 Bildirilen belirti ve canlı kanıt

Android uygulamada ilk şifreyle giriş başarılı olmuş ve menüler açılmış; buna karşılık Ürünler ve Ürün Radarı ekranları yüklenemedi uyarısı vermiştir. Canlı sunucu erişim kayıtlarında telefonun Tailscale IP adresi `100.103.16.93` üzerinden bağlandığı ve aşağıdaki isteklerin HTTP 200 aldığı doğrulanmıştır:

| Canlı istek | Sonuç |
|---|---|
| `GET /urunler` ve statik uygulama paketi | HTTP 200 |
| `POST /api/auth/login` | HTTP 200 |
| `GET /api/auth/status` | HTTP 200 |
| `GET /api/` | HTTP 200 |
| `GET /api/products` | HTTP 200 |

Bu kanıt veritabanının ve ürün verilerinin kaybolmadığını, telefon–sunucu bağlantısının ve kimlik doğrulamanın çalıştığını gösterir. Sorun, istemcinin bazı alt isteklerde daha önce kaydedilmiş yerel ağ HTTP adresini kullanabilmesi ve ekran yükleyicilerinin yardımcı bir istek hatasında tüm ekranı başarısız saymasıydı.

### 39.2 Uygulanan düzeltmeler

- HTTPS altında açılan arayüz, daha önce kaydedilmiş `http://192.168...` sunucu adresini artık kullanmaz; API kökü zorunlu olarak güvenli sayfanın kendi origin'ine döner. Bu, Android WebView karma içerik engelini ortadan kaldırır.
- Android yerel FCM/cihaz kaydı da HTTPS oturumunda kayıtlı eski LAN adresi yerine `location.origin` kullanır.
- Ürün Radarında ana `/watches` verisi zorunlu tutulurken `/stores` ve `/profile` yardımcı istekleri ayrı ele alınır. Yardımcı bir servisin geçici hatası artık bütün radar listesini kapatmaz.
- Ürünler ekranında yanıt tipi doğrulaması, kontrollü hata mesajı ve her durumda tamamlanan yüklenme durumu eklendi.
- HTTPS davranışını korumak için otomatik frontend testi eklendi.

### 39.3 Doğrulama ve yeni Android paketi

| Kontrol | Sonuç |
|---|---|
| Frontend test paketi | **26/26 geçti** |
| React üretim derlemesi | Başarılı (`main.78b7782e.js`) |
| Canlı Tailscale HTTPS ana sayfası | HTTP 200 ve yeni paket doğrulandı |
| Canlı `/api/health` | HTTP 200, `status=ok` |
| Android Gradle/Firebase kaynak işleme | Başarılı |
| Android APK derleme | **Başarılı** |
| Paket | `com.shoehunter.radar.debug` |
| Varsayılan sunucu | `https://pc1.tail135515.ts.net` |
| Başlangıç ekranı | `/urunler` |
| Sürüm | `versionCode=5`, `versionName=0.1.4-test` |
| APK | `mobile/dist/ShopHunter-Radar-0.1.4-test.apk` |
| APK boyutu | 49.474.394 bayt (47,18 MiB) |
| APK SHA-256 | `D477272B4F6176212D543783340C1465B0AD6FEB50F3329E2B8BEFFFC656D7A6` |

### 39.4 Saha kabul adımı

Mevcut `0.1.3-test` uygulamasının üzerine `0.1.4-test` APK kurulmalı, Tailscale bağlı tutulmalı ve uygulama tamamen kapatılıp yeniden açılmalıdır. Girişten sonra önce **Ürünler**, ardından **Ürün Radarı** açılarak gerçek cihaz kabulü tamamlanacaktır. Bu rapor kod, otomatik test, canlı HTTPS ve APK derleme doğrulamalarını kaydeder; son iki ekranın telefonda görüntülendiği henüz kullanıcı tarafından teyit edilmemiştir.

## 40. 22 Temmuz 2026 — Arka plan Radar, 6 saatlik keşif ve gerçek FCM kabulü

### 40.1 Android veri ekranı saha kabulü

Kullanıcı `0.1.4-test` kurulumundan sonra uygulamanın, Ürünler ekranının ve Ürün Radarının çalıştığını teyit etti. Böylece 39.4'te bekleyen gerçek cihaz kabulü tamamlandı.

### 40.2 `WinError 5` kök nedeni ve işçi mimarisi düzeltmesi

Canlı kurulumda hem FastAPI içindeki gömülü işçi hem de ayrı `browser` worker aynı kalıcı browser kuyruğundan iş alabiliyordu. Playwright işi kısıtlı sunucu sürecine denk geldiğinde Windows alt süreç başlatma işlemi `WinError 5 / Access denied` ile durabiliyordu; aynı iş ayrı browser worker'a denk geldiğinde tarayıcı açılıyordu.

`scripts/start-lan.ps1` kalıcı scheduler ile `default` ve `browser` kuyruklarına ayrı işçiler başlattığı için bu modda `EMBEDDED_SCHEDULER=false` ayarlanacak şekilde düzeltildi. Böylece browser kuyruğunun tek sahibi Playwright açabilen ayrı işçi oldu. Servisler bu yapıyla yeniden başlatıldı.

| Kontrol | Sonuç |
|---|---|
| Bağımsız Playwright / Decathlon | Sayfa render edildi, 646.414 HTML baytı |
| Adidas standart arama | HTTP 403; erişim koruması aşılmadı |
| Adidas `JR5220` resmî kesin kod rotası | Aday URL bulundu |
| Yerel `/api/health` | HTTP 200, veritabanı bağlı |
| Tailscale HTTPS `/api/health` | HTTP 200 |
| Güncel servis hata kayıtları | `WinError 5`, `Access denied`, traceback ve ERROR yok |
| Hedefli backend regresyon testleri | **22/22 geçti** |
| PowerShell başlatma betiği sözdizimi | Geçti |

### 40.3 Gerçek üründe manuel Radar taraması

Mevcut `nike Vomero 18` Radar kaydı değiştirilmeden normal `browser` kuyruğuna manuel keşif işi bırakıldı. İş `PC1-17800-browser` ayrı işçisi tarafından tek denemede tamamlandı.

| Manuel tarama kanıtı | Sonuç |
|---|---|
| Job kimliği | `5b1f605f3a57749dbb5069cc37c4ce4e` |
| Discovery run kimliği | `9a4281dc-9c0f-43ce-8def-4873048f1dc7` |
| Mağaza kapsamı | 28/28 denendi |
| Kullanılabilir mağaza sonucu | 24, kapsama `%85,7` |
| Erişim koruması nedeniyle bloklanan | 4 |
| Runtime hatası | 0 |
| Otomatik eşleşme | 14 |
| İnceleme adayı | 4 |
| Yeni ilan | 1 |
| İş denemesi | 1, tamamlandı |

Yeni ilan Nike TR'de gerçek `nike Vomero 18` ilanıdır ve taranan fiyat `8.799 TL` olarak kaydedilmiştir.

### 40.4 Zamanlanmış kontrol ve 6 saatlik Radar yolu

Canlı ayarlarda scheduler etkindir; fiyat/stok kontrol aralığı 30 dakika, Radar keşif temel aralığı 6 saattir. Yeniden başlatılan gerçek scheduler `14:30 UTC` kovasında otomatik `batch_check` üretti. Ayrı browser worker 43 vadesi gelen ilanın tamamını başarıyla kontrol etti.

| Otomatik fiyat/stok turu | Sonuç |
|---|---|
| Job kimliği | `b4b26239869acd3124b8c710c60885fd` |
| Check run kimliği | `03f516af-f474-4476-8dcf-edd95a678f7a` |
| Kontrol edilen / başarılı | **43/43** |
| Hatalı / ertelenen / fiyatsız | `0 / 0 / 0` |
| Henüz vadesi gelmediği için atlanan | 254 |
| Değişmeyen | 38 |
| Oluşan alarm | 0 |

6 saatlik Radar kabulü için aynı `nike Vomero 18` kaydı kontrollü olarak vadesi gelmiş yapıldı ve scheduler'ın kullandığı `discover_due` iş tipi normal `browser` kuyruğunda çalıştırıldı. Kabul işinin sadece tek vadesi gelen kaydı tarayabilmesi için dahili `limit` değeri 1–20 aralığında sınırlanarak desteklendi ve iki otomatik test eklendi.

| 6 saatlik yol kabulü | Sonuç |
|---|---|
| Job kimliği | `431811e7c074407597175dd99798f08d` |
| Job tipi / kuyruk | `discover_due` / `browser` |
| İşçi | `PC1-8680-browser` |
| Vadesi gelen Radar işlendi | 1 |
| Discovery run kimliği | `3a127976-079a-42df-afd0-520528788d43` |
| Mağaza kapsamı | 28 |
| Kullanılabilir mağaza sonucu | 24, kapsama `%85,7` |
| Runtime hatası | 0 |
| İş denemesi | 1, tamamlandı |

Her Radar kaydının `discovery_frequency_hours=6` temel aralığı korunur. Bir mağaza geçici olarak bloklu/ertelenmişse sistem altı saatlik normal turu beklemeden daha erken güvenli tekrar tarihi belirleyebilir. Bu nedenle kabul kaydında sonraki çalışma, bloklu mağazalar için `16:24 UTC` tekrarına çekilmiştir; bu 6 saatlik temel taramanın kaldırıldığı anlamına gelmez.

### 40.5 Gerçek Radar olayından FCM

Manuel taramada eklenen gerçek Nike ilanı `new_listing` alarmı oluşturdu. Bildirim için yapay fiyat veya stok değişikliği üretilmedi.

| FCM kabul kanıtı | Sonuç |
|---|---|
| Alarm kimliği | `4bcb81ef62be16d5250d12563def3170` |
| Alarm türü | `new_listing` |
| Başlık | `Yeni magazada urun bulundu` |
| Ürün / mağaza / fiyat | `nike Vomero 18` / Nike TR / `8.799 TL` |
| Etkin FCM cihazı | 1 |
| FCM sonucu | `fcm_sent=true`, `fcm_sent_count=1`, hata yok |
| Genel bildirim durumu | `sent` |

Bu sonuç gerçek Radar keşfi → yeni ilan → alarm kaydı → FCM HTTP v1 kabulü zincirini doğrular. Bildirimin Android bildirim panelinde görülmesi kullanıcı tarafından ayrıca teyit edilebilir; sunucu ve Firebase gönderim kabulü tamamlanmıştır.
