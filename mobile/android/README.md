# ShoeHunter Android

Telefon ve tablet için kişisel test uygulamasıdır. Uygulama ilk açılışta ShoeHunter web sunucusunun adresini sorar ve adresi cihazda saklar.

## Sunucu adresi

Telefon ve bilgisayar aynı Wi-Fi ağında olmalıdır. Bilgisayarın yerel IP adresini kullanın:

```text
http://192.168.1.131:3000
```

Telefonda `localhost` veya `127.0.0.1` bilgisayarınıza bağlanmaz. IP değişirse uygulamanın sağ üstündeki ayar düğmesinden adresi güncelleyin.

## Derleme

Proje kökündeki PowerShell betiği taşınabilir araçları kullanarak APK üretir:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\mobile\build-android-apk.ps1
```

Çıktı:

```text
mobile\dist\ShoeHunter-Radar-0.1.0-test.apk
```

## USB ile kurulum

Android cihazda geliştirici seçenekleri ve USB hata ayıklama açıkken:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\mobile\install-android-apk.ps1
```

APK ayrıca telefona kopyalanıp dosya yöneticisinden doğrudan kurulabilir.
