# Etiket, Barkod ve Ürün Kodu Okuma — Uygulama ve Test Raporu

**Proje:** ShoeHunter / Ürün Radarı  
**Tarih:** 20 Temmuz 2026  
**Kapsam:** Android telefon/tablet kamerası veya galerideki ürün fotoğrafından ürün bilgisi çıkarma ve kullanıcı onayından sonra Radar takibine hazırlama

## 1. Sonuç özeti

İstenen özellik uygulanmıştır. Kullanıcı artık Ürün Radarı ekranındaki **Etiketi / Barkodu Oku** düğmesiyle:

1. Android telefon veya tablette yeni fotoğraf çekebilir ya da galeriden fotoğraf seçebilir.
2. Barkod, QR, ayakkabı dili/kutu etiketi, ürün kodu, ürün adı, beden ve fiyat yazılarını kendi ShoeHunter sunucusunda okutabilir.
3. Bulunan bilgileri ve okuma güvenini ekranda inceleyebilir.
4. Uygun bulduğu öneriyi mevcut Radar formuna aktarabilir.
5. Mağaza seçimi, aile beden profilleri, hedef fiyat ve diğer kuralları düzenledikten sonra normal **Radar Başlat** işlemini yapabilir.

Fotoğrafın okunması tek başına Radar kaydı oluşturmaz. Bu karar özellikle korunmuştur: OCR hatası veya etiketteki eski/yanlış bilgi, kullanıcı kontrolü olmadan takibe dönüşmez.

## 2. Uygulanan kullanım akışı

```text
Kamera / Galeri
      ↓
JPG, PNG veya WebP doğrulaması
      ↓
Yerel barkod + QR okuma
      ↓
Yerel OCR ve yön düzeltme
      ↓
Marka / kod / beden / fiyat ayrıştırma
      ↓
Güven puanı + uyarılar + ham metin
      ↓
Kullanıcı incelemesi
      ↓
Radar formuna aktarım
      ↓
Kullanıcının son onayıyla Radar kaydı
```

## 3. Arka uç motoru

Yeni `backend/label_scan.py` motoru aşağıdaki görevleri yerine getirir:

- Görsel türü ve boyut güvenliği: JPG, PNG ve WebP; en fazla 12 MB ve 32 megapiksel.
- EXIF yön bilgisini uygular; büyük görseli en fazla 2.600 piksel kenara indirerek bellek ve işlem yükünü sınırlar.
- ZXing tabanlı yerel barkod/QR okuma yapar.
- RapidOCR ve ONNX Runtime ile yerel metin tanıma yapar.
- İlk okumada metin zayıfsa 90° ve 270° yönleri de deneyip daha kaliteli sonucu seçer.
- Marka adlarını, marka biçimine uygun ürün kodlarını, EAN/GTIN adaylarını, QR değerlerini, ayakkabı ve giyim bedenlerini, fiyatları ve açıklayıcı ürün satırlarını ayrıştırır.
- Bir etikette hem kısa hem tam ürün kodu bulunduğunda daha uzun ve ayırt edici kodu önceliklendirir. Örnek: `HL65QUMLN` yerine `HL65QUMLN-W02S`.
- Son görünen fiyatı hedef fiyat önerisi olarak kullanır. Bu, üstü çizili eski fiyat + güncel fiyat etiketlerinde önemlidir.
- Ayakkabı/giyim olmayan ürünlerde `S`, `M`, `L` gibi metinleri yanlış beden saymamak için kategoriye bağlı beden kuralları uygular.
- Marka biçimine uymayan gürültülü kodları eleyerek Radar sorgusunun bozulmasını azaltır.

Eklenen API:

```text
POST /api/radar/scan-label
```

Bu uç nokta mevcut oturum ve CSRF güvenliğine tabidir. Oturumsuz denemede beklendiği gibi `401 Oturum gerekli` dönmüştür.

## 4. Güven ve yanlış eşleşme önlemleri

Motorun çıktısı “kesin ürün” değil, düzenlenebilir Radar önerisidir.

- Her sonuçta 0–1 arası güven puanı üretilir ve arayüzde yüzde olarak gösterilir.
- Ürün kodu veya barkod bulunamazsa kullanıcıya açık uyarı verilir.
- Düşük güvenli metin otomatik kaydedilmez.
- OCR ile sayı parçalarından bir GTIN adayı kurulabilir; fakat barkod çizgileri ZXing tarafından gerçekten çözümlenmediyse bu değer kalıcı “güvenilir barkod” kimliği olarak Radar kaydına yazılmaz.
- QR ile barkod ayrı tutulur. Örneğin Nike etiketindeki `qr.nike.com` adresi EAN gibi değerlendirilmez.
- Kaynak kimlikleri en fazla 8 alan, anahtar başına 40 ve değer başına 300 karakter olacak şekilde temizlenir.
- Ham OCR metni yalnızca inceleme için döndürülür; Radar sorgusuna gürültülü bütün metin eklenmez.
- Fotoğraftan gelen Radar kayıtları `input_origin=label_scan` ile işaretlenir ve kartta **Etiketten** rozeti görünür.

## 5. Ön yüz ve kullanıcı deneyimi

Ürün Radarı ekranına şunlar eklenmiştir:

- **Etiketi / Barkodu Oku** düğmesi.
- Mobil cihazlarda arka kamerayı önceliklendiren dosya alanı.
- Seçilen fotoğrafın ön izlemesi.
- Okuma sürerken durum göstergesi.
- Önerilen Radar başlığı, marka, ürün kodları, barkod/QR, bedenler, fiyatlar ve güven yüzdesi.
- Düşük güven veya eksik kimlik uyarıları.
- **Bilgileri Radar Formuna Aktar** ve **Başka Fotoğraf Seç** işlemleri.
- İstenirse bütün OCR metnini açıp karşılaştırma imkânı.
- Etiketten oluşturulan takip kartlarında **Etiketten** rozeti.

Form aktarımı mevcut seçimleri bozmaz. Özellikle mağaza kapsamı ve aile beden profili seçimleri fotoğraf sonucu uygulanırken korunur.

## 6. Android uygulama değişiklikleri

Android WebView dosya seçicisi kamera ve galeriyi birlikte sunacak şekilde geliştirilmiştir.

- **Fotoğraf çek veya galeriden seç** menüsü açılır.
- Android 10 ve üzerindeki cihazlarda kamera çıktısı MediaStore üzerinden oluşturulur.
- Çekim iptal edilirse boş kamera kaydı temizlenir.
- Sistem kamera uygulaması kullanıldığı için WebView içine geniş bir sürekli kamera izni verilmez.
- Uygulama manifestine kamera özelliği “isteğe bağlı” olarak eklenmiştir; kamerasız tabletlerde uygulama kurulabilir.
- Etiket tarama düğmesi mobil WebView içinde çalışacak şekilde dosya seçici sonucu tekrar web formuna aktarılır.

Yeni APK:

| Alan | Değer |
|---|---|
| Dosya | `mobile/dist/ShoeHunter-Radar-0.1.0-test.apk` |
| Paket | `com.shoehunter.radar.debug` |
| Sürüm | `0.1.0-test` |
| Minimum Android | Android 8.0 / API 26 |
| Hedef SDK | API 35 |
| Boyut | 26.109 bayt |
| SHA-256 | `015D7087C77E89E4BCEF6B28B3CDB3FDD0D1876272E3403826026061C66529E8` |
| İmza | Android debug, APK Signature Scheme v2 doğrulandı |

## 7. Gönderilen 12 fotoğrafın nihai değerlendirmesi

Tüm görseller motor tarafından hata vermeden işlendi. Aşağıdaki tablo otomatik sonucun pratik değerini ve kullanıcı kontrolü gereken noktaları gösterir.

| Dosya | Görsel türü | Bulunan ana kimlik | Beden / fiyat | Değerlendirme |
|---|---|---|---|---|
| `...1281.jpg` | Nordmende TV fiyat etiketi | `Q65NM1105` | Eski 27.499 TL, hedef 24.999 TL | İndirimli son fiyat doğru sırada önerildi. |
| `...1281 (1).jpg` | Aynı Nordmende etiketinin ikinci kopyası | `Q65NM1105` | Eski 27.499 TL, hedef 24.999 TL | Yinelenen görsel de aynı ürün mantığıyla işlendi. |
| `...1282.jpg` | 65 inç TV etiketi | `HL65QUMLN-W02S` | Hedef 28.999 TL | Satıra bölünmüş model kodu yeniden birleştirildi; kısa kod yerine tam kod seçildi. |
| `...1283.jpg` | Mağaza içi bisiklet fiyat etiketi | `BİSİKLET 26 JANT` | Hedef 5.599 TL | Ürün kodu/barkod olmadığı için genel sorgu; marka/model kullanıcı tarafından tamamlanmalı. |
| `...1284.jpg` | Adidas giyim etiketi | `JF2847` | XL / 176 | Ürün kodu ve beden bilgisi Radar için kullanılabilir. |
| `...1285.jpg` | Adidas giyim etiketi | `JF2847` | XL / 176 | Aynı ürünün ikinci fotoğrafında da aynı ana kod bulundu. |
| `...1286.jpg` | Adidas çocuk/üst giyim etiketi | `KC1948` | XL / 176 | Ürün kodu, sınıf ve beden ayrıştırıldı. |
| `...1287.jpg` | Adidas giyim etiketi | `KE4680` | XL | Ürün kodu ve giyim bedeni ayrıştırıldı. |
| `...1288.jpg` | Adidas giyim etiketi | `JF2443` | L | Ürün kodu ve beden ayrıştırıldı. |
| `...1289.jpg` | Nike ayakkabı dili | `HV8113-200`; Nike QR | EU 42.5 | “Nike ACG Zegama Trail” sorgusu ve tam renkli ürün kodu üretildi. |
| `...1290.jpg` | Under Armour ayakkabı dili | `3027000-107` | EU 43 | Nihai tekrar testinde güven 0,976; gürültüsüz sorgu üretildi. |
| `...1291.jpg` | Adidas Adizero EVO SL kutusu | `JH6206` | Görselde EU 44 | Kod doğru bulundu. OCR yalnız “4” gördüğü için sistem 44 tahmini yapmadı; beden kullanıcı tarafından onaylanmalı. Barkod fotoğrafta görünür olsa da makine tarafından güvenilir biçimde çözümlenmedi. |

### Testlerden çıkarılan önemli sonuçlar

- Etiket çok net olmasa bile ürün kodu, Radar aramasında ürünü yalnız isimle aramaktan daha ayırt edici bir anahtar sağlar.
- Ayakkabı dili, kutu etiketi, giyim etiketi ve mağaza fiyat etiketi aynı girişten işlenebilir.
- Fiyat etiketi, çevrim içi stok kanıtı değildir. Yalnızca Radar sorgusu ve hedef fiyat için başlangıç verisi sağlar.
- Görselde okunabilen ama OCR'nin tam seçemediği bedenin otomatik tahmin edilmemesi bilinçli ve güvenli davranıştır.
- Barkod/QR okunamadığında ürün kodu ve metin OCR'si yine işe yarar; ancak kullanıcı incelemesi vazgeçilmezdir.

## 8. Doğrulama sonuçları

| Kontrol | Sonuç |
|---|---|
| Arka uç tam test takımı | `163 passed, 1 skipped` |
| Yeni etiket ayrıştırıcı testleri | `8 passed` |
| Yetkili yükleme + Radar kaynak kaydı entegrasyon testleri | Geçti |
| Ürün Radarı ön yüz testleri | `5 passed` |
| Ön yüz üretim derlemesi | Başarılı |
| Python kod kalite kontrolü | Başarılı |
| Android APK derlemesi | Başarılı |
| APK v2 imza kontrolü | Başarılı |
| Android Lint | 0 hata; yalnız yerel HTTP test yapılandırması uyarısı |
| Canlı web sunucusu | `http://192.168.1.131:3000`, HTTP 200 |
| Canlı API | `http://192.168.1.131:8000`, yeni `/api/radar/scan-label` yolu mevcut |
| Canlı güvenlik kapısı | Oturumsuz erişim reddedildi; yönetici girişi korunuyor |

Atlanan tek test, mevcut test takımındaki koşullu/ortama bağlı kontroldür; yeni etiket özelliğinin başarısız testi değildir.

## 9. Sunucu başlatma altyapısındaki düzeltmeler

Telefon/tablet kullanımını etkileyen iki başlatma sorunu da giderilmiştir:

- Sunucu artık sistemdeki rastgele Python yerine projenin `.venv` ortamını kullanır; yerel OCR bağımlılıkları kesin olarak bulunur.
- Kullanıcı adındaki Türkçe karakter nedeniyle bozulabilen sabit Node yolu kaldırıldı.
- Yönetici izni isteyen ağ sorgusu yerine standart DNS tabanlı yerel IP tespiti kullanıldı.
- Windows ortamında hem `PATH` hem `Path` bulunmasından kaynaklanan süreç başlatma hatası temizlendi.
- Arka uç ve ön yüz logları `mobile/logs` altında tutulur.
- `mobile/start-mobile-test-server.ps1`, aynı güvenilir ortak başlatıcıyı kullanır.

Güncel yerel ağ adresi test sırasında otomatik olarak `192.168.1.131` bulundu.

## 10. Gizlilik ve güvenlik sınırları

- OCR ve barkod motoru kendi bilgisayarınızdaki ShoeHunter sunucusunda çalışır; ücretli OCR/AI API'sine fotoğraf gönderilmez.
- Sunucu fotoğrafı diske kaydetmez; bellekte işler ve yalnız çıkarılan sonucu döndürür.
- Android kamera ile çekilen asıl fotoğraf cihazın `Pictures/ShoeHunter` alanında kalabilir; kullanıcı isterse cihazdan silebilir.
- Mevcut kişisel test kurulumu yerel ağda HTTP kullanır. Fotoğraf internet bulutuna gönderilmese de Wi‑Fi üzerindeki aktarım şifreli değildir. Güvenilmeyen/ortak ağda kullanılmamalı; dış yayın veya çok kullanıcılı kullanım öncesinde HTTPS zorunlu olmalıdır.
- Etiket sonucu mağaza sitelerinde Radar araması başlatıldığında yalnız ürün sorgusu/kodu mevcut keşif motorlarına gider; kaynak fotoğraf mağazalara gönderilmez.
- Yönetici oturumu, CSRF kontrolü, dosya türü ve boyut sınırları kaldırılmamıştır.

## 11. Bilinen sınırlar ve sonraki iyileştirmeler

1. OCR sonucu ışık, bulanıklık, kıvrımlı dil etiketi ve düşük kontrasttan etkilenebilir.
2. Tek fotoğrafta hem barkod hem beden net görünmüyorsa iki ayrı fotoğraf seçme/birleştirme akışı sonraki sürümde eklenebilir.
3. Aynı ürünün ön yüz fotoğrafı + etiket fotoğrafını tek Radar adayında birleştiren çoklu görsel akışı yararlı olacaktır.
4. Mağaza fiyat etiketindeki QR içeriği ürün sayfasına gidiyorsa kullanıcı onayından sonra doğrudan mağaza linki olarak eklenebilir; güvenlik nedeniyle otomatik açılmamalıdır.
5. Barkod katalog eşleştirmesi için ileride GS1 veya mağazaların resmî ürün API'leri tercih edilebilir. Ücretli ya da üçüncü taraf servis kullanılacaksa ayrıca gizlilik kararı alınmalıdır.
6. Yayın sürümünde HTTPS, kalıcı release imzası, Android ağ güvenlik yapılandırmasının sıkılaştırılması ve cihaz üstü bildirim kanalı eklenmelidir.

## 12. İlgili dosyalar

- `backend/label_scan.py`
- `backend/scan_label_diagnostic.py`
- `backend/server.py`
- `backend/discovery_service.py`
- `backend/tests/test_label_scan.py`
- `backend/tests/test_shoehunter.py`
- `frontend/src/pages/ProductRadar.jsx`
- `frontend/src/pages/ProductRadar.test.js`
- `mobile/android/app/src/main/java/com/shoehunter/radar/MainActivity.java`
- `mobile/android/app/src/main/AndroidManifest.xml`
- `mobile/android/app/src/main/res/values/strings.xml`
- `scripts/start-lan.ps1`
- `mobile/start-mobile-test-server.ps1`
- `mobile/dist/ShoeHunter-Radar-0.1.0-test.apk`

## 13. Kullanım

1. Bilgisayarda `scripts/start-lan.ps1` başlatılır.
2. Telefon/tablet aynı özel Wi‑Fi ağına bağlanır.
3. Test APK'sında `http://192.168.1.131:3000` adresi seçilir.
4. Yönetici hesabıyla giriş yapılır.
5. **Ürün Radarı → Etiketi / Barkodu Oku** açılır.
6. Fotoğraf çekilir veya galeriden seçilir.
7. Kod, beden, fiyat ve ürün adı kontrol edilir.
8. **Bilgileri Radar Formuna Aktar** seçilir.
9. Aile profili/bedenler, mağazalar, hedef fiyat ve renk kuralları gözden geçirilir.
10. **Radar Başlat** ile takip oluşturulur.

## 14. Teknik kaynaklar

- [RapidOCR kullanım belgeleri](https://rapidai.github.io/RapidOCRDocs/main/install_usage/rapidocr/usage/)
- [ZXing C++ Python paketi](https://pypi.org/project/zxing-cpp/)

