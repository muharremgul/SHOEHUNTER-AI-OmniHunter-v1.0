# Android ve Yerel Ağ Kullanımı

ShoeHunter, Android telefon ve tabletlerde aynı Wi-Fi ağı üzerinden PWA olarak kullanılabilir.

## Başlatma

Proje klasöründe PowerShell açın:

```powershell
.\scripts\start-lan.ps1
```

Başlatıcı bilgisayarın güncel yerel IP adresini bulur, bu adresi backend CORS listesine ekler ve iki adres gösterir:

```text
Telefon/tablet adresi: http://192.168.1.34:3000
API adresi: http://192.168.1.34:8000
```

Telefon ve bilgisayar aynı Wi-Fi ağındayken ilk adresi Chrome ile açın. Yönetici hesabı daha önce oluşturulmadıysa ilk kurulum ekranı gelir; oluşturulduysa kullanıcı adı ve parola istenir.

## Ana Ekrana Ekleme

Chrome menüsünde **Ana ekrana ekle** veya **Uygulamayı yükle** komutunu kullanın. PWA tam ekran açılır; veri için bilgisayardaki backend çalışmaya devam etmelidir.

## Bağlantı Sorunları

1. Telefonda `http://BILGISAYAR_IP:8000/api/health` adresini açın. JSON durum bilgisi görünmelidir.
2. Bilgisayar ve telefonun aynı ağda olduğundan emin olun.
3. Windows Güvenlik Duvarı'nda Python/Node için yalnızca özel ağ erişimine izin verin.
4. VPN, misafir Wi-Fi veya istemci yalıtımı cihazların birbirini görmesini engelleyebilir.
5. Bilgisayar IP'si değiştiyse eski süreçleri kapatıp `start-lan.ps1` komutunu yeniden çalıştırın.

Arayüz, API adresini sayfanın açıldığı ana bilgisayardan üretir. Özel bir API adresi gerekiyorsa tarayıcı konsolunda:

```js
localStorage.setItem("shoehunter_backend_url", "http://192.168.1.34:8000");
location.reload();
```

Sıfırlamak için:

```js
localStorage.removeItem("shoehunter_backend_url");
location.reload();
```

## Güvenlik

Yerel ağ da tamamen güvenilir kabul edilmez; bu nedenle yönetici oturumu ve CSRF koruması telefonda da etkindir. Uygulamayı internetten erişilebilir yapmak için doğrudan 3000/8000 portlarını modemden açmayın. HTTPS reverse proxy, `COOKIE_SECURE=true`, güçlü parola ve kesin `CORS_ORIGINS` kullanın.
