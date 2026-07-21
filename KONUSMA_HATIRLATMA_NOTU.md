# ShoeHunter / Ürün Radarı — Konuşma ve Devam Notu

**Kayıt tarihi:** 20 Temmuz 2026  
**Proje klasörü:** `C:\Users\ÖGR1\Documents\Ayakkabi`

Bu dosya, yürütülen uzun çalışmanın ana kararlarını, yapılan geliştirmeleri, doğrulanmış sonuçları ve sonraki adımları yeni bir görüşmede hızlıca hatırlatmak için hazırlanmıştır.

## 1. Ürünün amacı

ShoeHunter / Ürün Radarı; farklı mağazalardaki aynı ürünü tek başlık altında toplamak, fiyatı, stok durumunu, beden/numara seçeneklerini ve sepette oluşan kampanyaları izlemek için geliştiriliyor.

Temel değer önerileri:

- Ücretli bir ürün arama API'sine bağımlı olmadan mağazaları taramak.
- Aynı ürünün farklı mağaza bağlantılarını tek ürün altında birleştirmek.
- Kullanıcının ve ailesinin beden/numaralarına göre anlamlı bildirim üretmek.
- Stoğa yeni giren, son bedeni kalan veya düşük fiyattan geri gelen ürünleri erkenden yakalamak.
- Radar ile bulunan ürünleri, elle bağlantı veya yapay zekâ yardımıyla eklenen ürünlerden ayırabilmek.

## 2. Bildirim ve radar gereksinimleri

Takip edilmesi istenen bildirim sınıfları:

1. **Son numara fırsatı**
2. **Numaran yeniden stokta**
3. **İndirimli fiyattan yeniden stokta**
4. **Tek renk / tek numara geri geldi**
5. **Fiyat düştü ve numaran mevcut**
6. **Sepette fiyat devam ediyor**
7. **Stok kritik seviyede**
8. **En az yüzde 3 fiyat düşüşü**
9. **Yeni kampanya veya kural yakalandı**
10. **Radarda yeni ürün bulundu**

Radarın olağan kontrol aralığı altı saat olarak ele alındı. Mesajlarda yalnızca ürün adı ve fiyat değil, ilgili beden/numara da açıkça yer almalı. Bu kontrol; radar ile bulunan ürünlerin yanında bağlantı ile veya yapay zekâ yardımıyla eklenen ürünlere de uygulanmalı.

## 3. Aile ve beden profili yaklaşımı

Tek bir kullanıcı için birden fazla numara gerekebilir; örneğin ayakkabı modeline göre normal numara ve bir büyük numara birlikte izlenebilir. Sistem gelecekte yalnızca ayakkabı değil, farklı ürün sınıflarını da kapsamalıdır.

Önerilen veri modeli:

- Aile üyesi / profil adı
- Ürün sınıfı: ayakkabı, tişört, pantolon, mont vb.
- Ana beden veya numara
- Alternatif kabul edilen bedenler / numaralar
- Marka ya da kategoriye özel beden tercihi
- Renk tercihi
- Bildirim önceliği
- İndirim eşiği ve azami fiyat

Ürün ekranında ürünün kaynağı görünür olmalı. Özellikle radarın getirdiği ürünlerde belirgin bir **Radar ürünü** işareti bulunmalı; çünkü tek ürün başlığının altında çok sayıda mağaza bağlantısı yer alabilir.

## 4. Güvenli erişim sınırı

Mağazaların robots kurallarını, CAPTCHA veya erişim korumalarını aşmak için stealth, kimlik sahteciliği, proxy rotasyonu ya da benzeri kaçınma yöntemleri uygulanmadı ve uygulanmamalı.

Kabul edilen yaklaşım:

- Önce normal HTTP ve sayfadaki yapılandırılmış veriler kullanılır.
- Gerekli olduğunda yalnızca standart Playwright tarayıcı erişimi denenir.
- `401`, `403`, `429`, CAPTCHA veya erişim doğrulama sayfası görülürse mağaza **erişim engelli** olarak sınıflandırılır.
- İndirilen ve kullanıcı tarafından sağlanan HTML dosyaları, ayrıştırıcı geliştirme ve test için kullanılabilir.

Bu sınır; sistemi sürdürülebilir, denetlenebilir ve mağazaların erişim korumalarını ihlal etmeyen bir yapıda tutmak içindir.

## 5. Mağaza motorlarında yapılan önemli çalışmalar

### N11

- Önce statik sayfa ayrıştırma yaklaşımı güçlendirildi.
- Gerektiğinde tek bir standart tarayıcı yedeği kullanılacak biçimde ele alındı.

### Amazon

- ASIN tabanlı bağlantı normalleştirme geliştirildi.
- Önce statik veri, ardından gerekirse standart tarayıcı yedeği yaklaşımı benimsendi.

### Trendyol

- Ürün başlığını farklı sayfa kaynaklarından kurtarma/yedekleme davranışı iyileştirildi.

### Decathlon

İncelenen ürün:

`https://www.decathlon.com.tr/p/erkek-yelkenli-yagmurlugu-lacivert-sailing-500/_/R-p-340673?mc=8758966&c=MAV%C4%B0`

Kullanıcının sağladığı kayıtlı sayfa:

`C:\Users\ÖGR1\Downloads\Erkek Yelkenli Yağmurluğu - Lacivert - Sailing 500 - Decathlon.html`

Doğrulanan sonuçlar:

- Decathlon statik HTTP isteğini zaman zaman `403` ile engelliyor.
- Standart Playwright bazı denemelerde sayfayı açabiliyor; erişim kararlı değil.
- Kayıtlı HTML içindeki `__DKT` verisini okuyan ayrıştırıcı geliştirildi.
- Ayrıştırıcı, bağlantıdaki kesin `mc=8758966` ürün varyantını seçiyor.
- Doğrulanan fiyat: **2.890 TL**.
- Doğrulanan beden durumu: **S ve M stokta**, **2XL stokta değil**.
- İlgisiz varyant ve bedenlerin ürüne karışması engellendi.
- Doğru uzak ürün görseli seçildi.
- Decathlon motoru standart tarayıcı havuzunu kullanıyor; erişim doğrulama sayfası görülürse işlem engelli olarak işaretleniyor.

Bu aşamadaki test sonucu: **153 test başarılı, 1 test atlandı**.

İlgili dosyalar:

- `backend/stores/decathlon.py`
- `backend/browser_access_diagnostic.py`
- `PLAYWRIGHT_ERISIM_TEST_RAPORU.md`

## 6. Android test uygulaması

Özel test dönemi için, mevcut web arayüzünü kullanıcının kendi yerel sunucusundan açan yerel Android WebView uygulaması hazırlandı.

### Teslim bilgileri

- Android proje klasörü: `mobile/android`
- APK: `mobile/dist/ShoeHunter-Radar-0.1.0-test.apk`
- Paket adı: `com.shoehunter.radar.debug`
- Sürüm: `0.1.0-test`
- Asgari Android API: 26
- Hedef API: 35
- APK boyutu: 26.109 bayt
- SHA-256: `015D7087C77E89E4BCEF6B28B3CDB3FDD0D1876272E3403826026061C66529E8`

Doğrulamalar:

- APK v2 imzası doğrulandı.
- Android manifesti paketleme aracıyla doğrulandı.
- Telefon görünümü `390×844`, tablet görünümü `800×1280` boyutlarında kontrol edildi.
- Yatay taşma görülmedi.
- Android Lint sonucu: hata yok; yerel ağdaki test sunucusu için bilinçli olarak açık bırakılan şifresiz HTTP konusunda bir uyarı var.
- Fiziksel cihaz bağlı olmadığı için APK otomatik kurulmadı.

### Yerel test adresleri

- Web arayüzü: `http://192.168.1.131:3000`
- Arka uç API: `http://192.168.1.131:8000`

Son kontrolde iki adres de `200` yanıtı verdi. Web sunucusu `0.0.0.0:3000`, API `0.0.0.0:8000` üzerinden yerel ağa açıldı ve API tarafında yerel ağ kaynağı için CORS izni düzenlendi.

Son gözlenen süreçler:

- Web sunucusu PID: `14296`
- API sunucusu PID: `21816`

Bu süreç numaraları bilgisayar veya sunucu yeniden başlatıldığında değişebilir; kalıcı bilgi olarak değerlendirilmemelidir.

### Android yardımcı dosyaları

- `mobile/setup-android-toolchain.ps1`
- `mobile/build-android-apk.ps1`
- `mobile/install-android-apk.ps1`
- `mobile/start-mobile-test-server.ps1`

Yerel Android araç zinciri `mobile/.toolchain` altında JDK 17, Gradle 8.9 ve Android SDK 35 ile hazırlandı.

İlgili raporlar:

- `ANDROID_BASLANGIC_RAPORU.md`
- `MOBILE_APK_TESLIM_RAPORU.md`

## 7. Mobil uygulama mimarisi kararı

Mevcut WebView APK, tek kullanıcıyla hızlı ve düşük maliyetli özel test için uygun görüldü. Ancak herkese yayımlanacak uzun vadeli uygulama için tek başına en iyi çözüm değildir.

Sonraki aşama için önerilen yapı:

1. Capacitor içinde paketlenmiş mevcut React arayüzü
2. Ayrı ve kararlı ShoeHunter API'si
3. FCM ile gerçek arka plan bildirimleri
4. Güvenli oturum bilgisi saklama
5. Son veriyi çevrimdışı gösterebilme
6. Ürün ve bildirimlere doğrudan giden derin bağlantılar
7. Üretim imzası, HTTPS ve Google Play için AAB

Değerlendirilen diğer seçenekler:

- PWA: en hızlı dağıtım, ancak Android bildirim ve mağaza entegrasyonları daha sınırlı.
- TWA: PWA'yı mağaza uygulaması gibi sunabilir; yine web bağımlıdır.
- React Native / Flutter: daha yerel deneyim, fakat mevcut web arayüzünün daha büyük bölümünü yeniden geliştirmek gerekir.
- Kotlin + Jetpack Compose: en güçlü yerel Android yaklaşımı; geliştirme maliyeti en yüksektir.

## 8. Sonraki görüşmede yapılacaklar

Önerilen sıra:

1. `mobile/dist/ShoeHunter-Radar-0.1.0-test.apk` dosyasını telefon ve tablete kur.
2. Cihazlarla bilgisayarı aynı Wi-Fi ağına bağla.
3. Giriş, sayfa dolaşımı, ürün bağlantıları, dosya yükleme/indirme ve geri tuşu davranışını test et.
4. Karşılaşılan sorunları cihaz modeli ve ekran görüntüsüyle kaydet.
5. Özel test başarılı olursa Capacitor tabanlı ikinci aşamaya ve FCM bildirimlerine geç.
6. Yayın öncesinde HTTPS, üretim imzası, güvenli kimlik doğrulama ve AAB hazırlığını tamamla.
7. Radar bildirim sınıfları, aile beden profilleri ve ürün kaynağı işaretlerini uçtan uca test et.

## 9. Gizlilik notu

Projedeki `.env` ve benzeri yapılandırma dosyalarında bulunabilecek API anahtarları, sohbet kimlikleri veya diğer gizli bilgiler bu özet dosyasına alınmamıştır. Bu bilgiler kaynak kontrolüne veya paylaşılacak raporlara eklenmemelidir.

---

Yeni bir Codex görüşmesinde devam etmek için şu kısa yönerge yeterlidir:

> `KONUSMA_HATIRLATMA_NOTU.md` dosyasını tamamen oku, mevcut proje durumunu doğrula ve 8. bölümdeki sıradan devam et. Mevcut kazanımları bozma; stealth, CAPTCHA atlatma, kimlik sahteciliği veya proxy rotasyonu kullanma.

## 10. Etiket / barkod / ürün kodu ile Radar ekleme

20 Temmuz 2026 tarihinde telefon kamerası veya galeriden gelen ürün fotoğrafını yerel olarak okuyup Radar formuna hazırlayan özellik tamamlandı.

- Ayakkabı dili, kutu etiketi, giyim etiketi, barkod, QR ve mağaza fiyat etiketi desteklenir.
- RapidOCR + ONNX Runtime ve ZXing kendi ShoeHunter sunucusunda çalışır; ücretli OCR API'si kullanılmaz.
- Marka, ürün kodu, barkod/QR, beden, fiyat, kategori ve Radar sorgusu önerilir.
- Sonuç kullanıcı incelemesi olmadan Radar'a kaydedilmez.
- Fotoğraftan gelen takipler kartta `Etiketten` rozetiyle görünür.
- Android APK kamera veya galeri seçimini destekleyecek şekilde yeniden üretildi.
- Yeni APK boyutu 26.109 bayt, SHA-256 değeri `015D7087C77E89E4BCEF6B28B3CDB3FDD0D1876272E3403826026061C66529E8`.
- 12 örnek fotoğraf işlendi; `HL65QUMLN-W02S / 28.999 TL`, `Under Armour 3027000-107 / EU 43`, `Nike HV8113-200 / EU 42.5` gibi zor örnekler doğrulandı.
- Tam arka uç testi: `163 passed, 1 skipped`; Radar ön yüz testi: `5 passed`.
- Ayrıntılı rapor: `deliverables/ETIKET_BARKOD_URUN_RADARI_UYGULAMA_VE_TEST_RAPORU_2026-07-20.md`.
