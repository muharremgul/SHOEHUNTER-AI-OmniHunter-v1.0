# ShoeHunter — Ek Net Durum, Kalınan Yer ve Hedefler

**Tarih:** 20 Temmuz 2026  
**Bağlı ana rapor:** `GOOGLE_LENS_GORSEL_BARKOD_ARAMA_VE_YENI_RADAR_KAYITLARI_DENETIM_RAPORU_2026-07-20.md`  
**Amaç:** Bir haftalık Android saha denemesi öncesinde gerçekten tamamlanan işleri, son canlı kanıtı, bilerek ertelenen işleri ve devam sırasını tartışmasız biçimde kaydetmek.

## 1. Net sonuç

Çalışan çekirdek tamamlandı: barkod veya fotoğraftan kimlik çıkarma, seçilebilir OCR, kod/GTIN öncelikli arama planı, 27 mağazanın adil ve hata yalıtımlı taranması, yanlış ürünleri otomatik bağlamayan sıkı kimlik filtresi, toplam maliyet açıklaması ve satıcı güven kanıtı uygulandı. Web sitesi ve yerel API çalışır durumdadır. Test Android APK'sı telefon ve tablet için hazırdır.

Google Lens'in kapalı internet ölçeğindeki Shopping Graph altyapısı kopyalanmış değildir. OpenCLIP tabanlı kendi görsel vektör kataloğu, native CameraX canlı OCR ve AR kamera katmanı bu APK'nın içinde yoktur. Bunlar sonraki geliştirme fazlarıdır.

## 2. Son canlı JR5220 kanıtı

Son koşu kimliği: `62b2fd3d-87f0-4670-8ba3-fa75451a4f28`  
Sorgu: `TRAIL RUNNING JR5220`  
Arama sırası: `JR5220` → `4067904494690` → `TRAIL RUNNING JR5220`

| Ölçüm | Sonuç |
|---|---:|
| Seçili mağaza | 27 |
| Gerçekten denenen mağaza | 27 (`%100`) |
| Kullanılabilir sonucu olan mağaza | 25 (`%92,6`) |
| Kapasite nedeniyle ertelenen mağaza | 0 |
| Erişim engeli | 2 — Kutupayısı ve Hepsiburada |
| Otomatik kesin eşleşme | 0 |
| Kullanıcı incelemesine ayrılan aday | 15 |
| Zayıf/çelişkili kanıtla reddedilen aday | 18 |
| Yeni yanlış ilan bağlantısı | 0 |

Önceki koşuda 14 mağaza tarayıcı sırası gelmeden `capacity_timeout` olmuştu. Son düzeltmede tarayıcı gerektiren mağazalar üç işçili adil FIFO kuyruğuna alındı; normal HTML mağazaları paralel bırakıldı. Son koşuda kapasite ertelemesi sıfıra düştü ve kapsama `%40,7` seviyesinden `%92,6` seviyesine çıktı.

Adidas doğrudan isteğe HTTP 403 verdi; sistem korumayı atlatmadı. Güvenli açık kaynak geri dönüşü `JR5220` kodlu bir aday buldu, fakat kesin sayılmadı. Decathlon, Intersport, Barçın, Sneaks Up ve n11 geniş sorguda aday üretti. Kod/GTIN kanıtı taşımayan sonuçlar kullanıcı incelemesine bırakıldı veya reddedildi.

## 3. Koda uygulanan ana kazanımlar

### Görsel, OCR ve barkod

- Fotoğraftaki OCR kutuları görüntü üzerinde seçilebilir.
- Kullanıcı bütün alanları, önerilen alanları veya kendi seçtiği alanları Radar sorgusuna aktarabilir.
- Fotoğraf sola/sağa döndürülüp yeniden okunabilir.
- Sunucu OCR'ı 0°, 90°, 180° ve 270° yönlerini değerlendirir.
- Barkod/QR sonucu seçim sırasında kaybolmaz; kesin kimlik olarak korunur.
- Google Code Scanner ile EAN, UPC, Code 128, QR ve Data Matrix Android'de okunabilir.

### Ürün kimliği ve arama

- Ürün kodu ve GTIN, genel ürün adından önce aranır.
- `JR5220` gibi açık ürün kodu artık yalnız model alanında tutulup unutulmaz; mağaza sorgusuna gider.
- Farklı açık model kodu taşıyan aday otomatik eşleşemez.
- Marka çelişkisi ve yalnız genel kategori benzerliği kesin eşleşme sayılmaz.
- Geniş sorgu aday üretmek için kullanılır; fiyat sonucu diye otomatik sunulmaz.

### 27 mağaza güvenilirliği

- Bir mağazanın hatası diğer 26 mağazayı iptal etmez.
- Keşif, ürün detayı ve izleme hataları ayrı devrelerde tutulur.
- Yerel kapasite/ağ/çalışma ortamı hataları gerçek mağaza engeli diye kalıcı devre açmaz.
- Tarayıcı mağazaları adil kuyrukta çalışır; mağaza süresi kuyrukta beklerken tükenmez.
- Kapsama “denendi” ve “kullanılabilir sonuçlandı” olarak ayrı raporlanır.
- Erişim koruması görülürse stealth, CAPTCHA çözme, kimlik sahteciliği veya proxy rotasyonu uygulanmaz.

### Fiyat ve teklif kalitesi

- Ürün, varyant, kimlik ve mağaza teklifi için kanonik projeksiyon eklendi.
- Koşulsuz sepet fiyatı varsa toplam maliyete alınır.
- Üyelik, kupon, adet veya beden koşullu fiyat kesin toplam diye gösterilmez.
- Açık kargo bedeli toplam maliyete eklenir; bilinmeyen kargo uydurulmaz.
- Satıcı güveni açıklanabilir kanıt/risk puanı olarak gösterilir; garanti olarak sunulmaz.

## 4. Doğrulama durumu

| Kontrol | Sonuç |
|---|---|
| Arka uç testleri | `200 passed, 1 skipped` |
| Ön yüz testleri | `22 passed` |
| Ön yüz üretim derlemesi | Başarılı |
| Değiştirilen Python dosyalarında kod kalite kontrolü | Başarılı |
| Yerel API | HTTP 200, veritabanı bağlı, sürüm 0.6.0 |
| JR5220 canlı tarama | 27/27 denendi, 25/27 kullanılabilir sonuç |
| Android APK | Başarılı |

Atlanan tek test ortam koşuluna bağlıdır. FastAPI/Starlette gelecek sürüm uyarıları ve pytest önbellek izin uyarısı ürün testi başarısızlığı değildir. Tüm depo üzerinde eski biçimlendirme borcu vardır; yalnız bu çalışmada değişen dosyalar temiz doğrulanmıştır.

## 5. Bir haftalık test APK'sı

- Dosya: `mobile/dist/ShoeHunter-Radar-0.1.0-test.apk`
- Varsayılan sunucu: `http://192.168.1.131:3000`
- Boyut: `1.494.791` bayt
- SHA-256: `C82197227B271D4529743CD546B86EACB6B1286B4A1492F4C97309F29968768C`

Telefon/tablet ile sunucu bilgisayar aynı yerel ağda olmalıdır. Bilgisayarın IP adresi değişirse uygulamadaki sunucu ayarı kullanılmalı veya APK yeni adresle yeniden derlenmelidir. Windows güvenlik duvarında 3000 numaralı porta yalnız güvenilen özel ağdan izin verilmelidir. Bu test imzalı APK'dır; mağaza yayını değildir.

Bir haftalık denemede özellikle şunlar kaydedilmelidir:

1. Barkodun ilk denemede okunup okunmadığı.
2. OCR'ın doğru ürün adı/kodu/GTIN alanını önerip önermediği.
3. Kullanıcının hangi OCR kutularını elle seçmek zorunda kaldığı.
4. Radarın 27 mağazadan kaçını tamamladığı ve hangi mağazaların engel verdiği.
5. İnceleme adaylarından gerçekten aynı ürün olanların sayısı.
6. Fiyat, kargo, sepet koşulu, beden ve stok bilgisinin doğru olup olmadığı.
7. Telefon ve tablette geri tuşu, kamera izni, fotoğraf seçimi ve ağ kopması davranışı.

## 6. Kalınan yer

Kalan iş bir hata düzeltme değil, ürünün ikinci teknik fazıdır. Mevcut APK barkod ve fotoğraf OCR'ıyla çalışır; görüntünün kendisini büyük bir ürün kataloğunda benzerlik aramasına sokmaz. Native kamera üzerinde canlı OCR kutuları göstermez. AR katmanı yoktur. Fiziksel raf etiketi ve fiş kanıtlarını topluluk verisine dönüştürmez.

## 7. Sonraki hedefler ve doğru sıra

### Hedef 1 — Bir haftalık saha verisini ölç

Önce bu APK ile gerçek kullanım kayıtları toplanmalı. Yanlış eşleşme ve OCR düzeltme oranı görülmeden daha karmaşık görsel model eklenmemelidir.

### Hedef 2 — Native CameraX + ML Kit

WebView kabuğunun yanına canlı kamera ekranı, cihaz üzerinde metin tanıma, seçilebilir kutular, offline outbox ve idempotent senkronizasyon eklenmelidir. Hedef: kaliteli ürün kodlu etiketlerde doğru ürünün ilk üç sorgu adayında en az `%95`, otomatik exact match precision en az `%99`.

### Hedef 3 — Kendi görsel vektör kataloğu

Yasal olarak kullanılabilir mağaza katalog görselleri hash ile temizlenmeli; lisansı doğrulanmış OpenCLIP modeliyle embedding üretilmeli; ilk sürümde pgvector, ölçek gerekirse Qdrant kullanılmalıdır. Görsel arama yalnız aday üretmelidir; exact SKU kararı kod/GTIN veya güçlü sayfa kanıtı gerektirmelidir.

### Hedef 4 — Fiziksel fiyat/fiş kanıt ağı

Raf etiketi ve fiş OCR rolleri ayrılmalı; mağaza, zaman, konum hassasiyeti, kanıt görseli, kişisel veri maskeleme, saklama süresi ve moderasyon eklenmelidir. Kanıtsız veya eski fiyat doğrulanmış diye yayınlanmamalıdır.

### Hedef 5 — GS1 Digital Link ve yaşam döngüsü

GTIN yanında lot, seri, son kullanma tarihi ve varyant kimliği GS1 kurallarına göre saklanmalıdır. Resolver kimlik çözümlemek için kullanılabilir; piyasa fiyatı kaynağı değildir.

### Hedef 6 — AR

Kamera üzerinde takipteki ürün, beden ve fiyat rozeti ancak ürün kimliği doğruluğu, kamera performansı, pil tüketimi ve gizlilik hedefleri saha testinde geçildikten sonra yapılmalıdır.

## 8. Tamamlanma tanımı

Mevcut bir haftalık test teslimi tamamdır. Lens/vector/AR programı ise ancak şu üç çıktı üretildiğinde tamamlanmış sayılabilir:

- ölçülmüş ve lisansı doğrulanmış görsel katalog araması;
- native mobil kamera/OCR deneyimi ve offline senkronizasyon;
- kimlik doğruluğu ve gizlilik kapılarından geçen AR saha sürümü.

Bu ek belge, bugün çalışan kod ile gelecek hedefleri birbirinden ayırır; hiçbir yol haritası maddesini yapılmış gibi göstermez.
