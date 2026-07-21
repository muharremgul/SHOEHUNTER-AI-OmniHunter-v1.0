# Android Uygulaması Başlangıç Raporu

**Tarih:** 20 Temmuz 2026  
**Aşama:** Kişisel test kullanımı  
**Hedef cihazlar:** Android telefon ve tablet

## Hedef

Mevcut Ürün Radarı sitesini yeniden yazmadan Android uygulaması olarak kullanmak ve kurulabilir bir APK üretmek. Uygulama test döneminde kullanıcının kendi sunucusuna bağlanacak; sunucu adresi APK'yı yeniden derlemeden uygulama içinden değiştirilebilecek.

## Seçilen yaklaşım

Yerel Android uygulaması içinde güvenli bir WebView kabuğu kullanılacak. Bu yaklaşım mevcut React arayüzünü ve FastAPI altyapısını korur, yeni özelliklerin web ve Android tarafında aynı anda kullanılmasını sağlar.

Uygulama şunları içerecek:

- İlk açılışta sunucu adresi ayarı
- Yerel ağdaki `http://` test sunucularına kontrollü erişim
- Gelecekteki `https://` sunucuya hazır yapı
- Telefon ve tablet ekran desteği
- Android geri tuşu ve sayfa yenileme davranışı
- Bağlantı hatası ve tekrar deneme ekranı
- Dosya seçme/yükleme ve indirme desteği
- Harici bağlantıları güvenli biçimde sistem tarayıcısında açma
- Debug APK üretimi ve kurulum yönergesi

## Test sunucusu için önemli koşul

Telefondaki `127.0.0.1` bilgisayarı değil telefonu ifade eder. Telefon ve bilgisayar aynı ağdaysa uygulamaya bilgisayarın yerel ağ adresi girilmelidir; örneğin `http://192.168.1.50:3000`. Sunucu da yalnızca `127.0.0.1` yerine ağ arayüzünde dinlemelidir. Güvenlik duvarında sadece gerekli test portlarına yerel ağ izni verilmelidir.

## Dağıtım planı

İlk teslim debug imzalı APK olacaktır ve doğrudan telefon/tablete kurulabilecektir. Kişisel test tamamlandıktan sonra ayrı bir kalıcı imza anahtarı, sürümleme, release APK/AAB ve otomatik güncelleme hattı eklenebilir.
