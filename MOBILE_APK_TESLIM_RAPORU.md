# ShoeHunter Android APK Teslim Raporu

**Tarih:** 20 Temmuz 2026  
**Sürüm:** 0.1.0-test  
**Kullanım amacı:** Kişisel telefon/tablet testi

## Teslim edilen APK

```text
mobile/dist/ShoeHunter-Radar-0.1.0-test.apk
```

| Alan | Değer |
|---|---|
| Paket kimliği | `com.shoehunter.radar.debug` |
| Sürüm kodu | `1` |
| Sürüm adı | `0.1.0-test` |
| Minimum Android | Android 8.0 / API 26 |
| Hedef Android SDK | API 35 |
| İmza | Android debug, RSA 2048, APK Signature Scheme v2 |
| APK boyutu | 26.109 bayt |
| SHA-256 | `015D7087C77E89E4BCEF6B28B3CDB3FDD0D1876272E3403826026061C66529E8` |

APK, Android `apksigner` ile doğrulandı. Manifest ve paket bilgileri Android `aapt` ile okunarak kontrol edildi.
Android Lint sonucu: sıfır hata; yalnızca kişisel debug APK'sında bilinçli olarak açık bırakılan yerel HTTP erişimi için bir uyarı.

## Uygulama özellikleri

- İlk açılışta değiştirilebilir sunucu adresi
- Varsayılan test adresi: `http://192.168.1.131:3000`
- Telefon ve tablet ekran desteği
- Oturum çerezleri ve CSRF kullanan mevcut giriş sistemine uyum
- Android geri tuşuyla web geçmişinde gezinme
- Yenileme ve sunucu ayarı araç çubuğu
- Bağlantı hatası, tekrar deneme ve Wi-Fi ayarları ekranı
- Uygulama dışındaki mağaza bağlantılarını sistem tarayıcısında açma
- Kamera ile etiket/barkod fotoğrafı çekme veya galeriden seçme desteği
- Fotoğraftan ürün kodu, barkod/QR, beden ve fiyat önerisini Radar formuna aktarma
- Android İndirme Yöneticisi üzerinden dosya indirme
- Güvenli olmayan kamera/mikrofon izinlerini varsayılan olarak reddetme
- Debug derlemede WebView hata ayıklama; release derlemede kapalı
- Yerel ağ testleri için HTTP desteği; sonraki yayın sürümü HTTPS'e geçirilebilir

## Sunucu altyapısı

Test sırasında kullanılacak adresler:

```text
Web: http://192.168.1.131:3000
API: http://192.168.1.131:8000
```

Kontrol sonuçları:

- Web yanıtı: HTTP 200
- API sağlık kontrolü: HTTP 200
- API dinleme adresi: `0.0.0.0:8000`
- Mobil web kaynağı için CORS: izinli
- Kimlik bilgili istekler: izinli

Telefon ve bilgisayar aynı yerel ağda olmalıdır. Bilgisayarın IP adresi değişirse uygulamanın sağ üst köşesindeki sunucu ayarından yeni adres girilmelidir.

## Telefona veya tablete kurulum

1. `ShoeHunter-Radar-0.1.0-test.apk` dosyasını USB kablosu veya güvenilir bir dosya aktarım yöntemiyle Android cihaza kopyalayın.
2. Android dosya yöneticisinden APK'ya dokunun.
3. Android isterse yalnızca kullandığınız dosya yöneticisi için **Bilinmeyen uygulama yükleme** iznini açın.
4. Uygulamayı kurup açın.
5. Sunucu adresi alanında `http://192.168.1.131:3000` adresini onaylayın.
6. Mevcut ShoeHunter yönetici hesabıyla giriş yapın.

USB hata ayıklama açık bir cihaz bağlıysa proje içindeki `mobile/install-android-apk.ps1` betiği de kullanılabilir.

## Mobil görünüm doğrulaması

Mevcut web arayüzü iki boyutta kontrol edildi:

| Profil | Görünüm | Yatay taşma |
|---|---:|---:|
| Telefon | 390 × 844 | Yok |
| Tablet | 800 × 1280 | Yok |

Giriş ekranı, görünüm alanı etiketi ve tam ekran yerleşim iki profilde de doğrulandı.

## Bilinen test aşaması sınırları

- APK debug anahtarıyla imzalıdır; Google Play dağıtımı için kullanılmamalıdır.
- Bu sürüm kendi sunucunuzun web arayüzünü gösterir; bilgisayar kapalıysa uygulama veri alamaz.
- Windows Güvenlik Duvarı sorarsa sadece **Özel ağ** erişimine izin verilmelidir.
- APK yeni bir Firebase/FCM bildirim kanalı eklemez. Sunucudaki zamanlayıcı ve mevcut Telegram bildirimleri çalışmaya devam eder.
- Fiziksel cihaz USB ile bağlı olmadığı için bu bilgisayardan otomatik kurulum yapılamadı; APK imza ve paket seviyesinde doğrulandı.

## Sonraki yayın aşaması

Kişisel test sonrasında kalıcı release imza anahtarı, HTTPS alan adı, FCM bildirimleri, sürüm yükseltme mekanizması ve Play Store için AAB üretimi eklenebilir.
