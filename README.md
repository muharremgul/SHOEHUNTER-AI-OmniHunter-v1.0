# ShoeHunter AI v0.6.0

ShoeHunter AI; Türkiye'deki desteklenen mağazalarda ürün, fiyat, stok, beden ve kampanya takibi yapan tek kullanıcılı bir web uygulamasıdır. Kullanıcı bir mağaza bağlantısını izleyebilir veya **Ürün Radarı** oluşturarak yalnızca ürün adını, bedenleri ve hedef fiyatı tanımlayabilir.

## Bileşenler

- `backend/`: FastAPI, MongoDB, mağaza adaptörleri, ürün eşleştirme, alarm ve güvenlik katmanı.
- `frontend/`: React yönetim paneli ve kurulabilir PWA.
- `worker.py`: Kalıcı iş kuyruğunu tüketir; Docker'da normal işler ile ağ/tarayıcı işleri ayrı süreçlere yönlendirilir.
- `scheduler_worker.py`: Süresi gelen işleri benzersiz anahtarla kuyruğa yazar.
- `docker-compose.yml`: MongoDB, API, worker, browser-worker, scheduler ve frontend kurulumu.

Ana veri akışı:

```text
Ürün Radarı -> Keşif Çalışması -> Aday İlan -> Eşleştirme
             -> Ürün/İlan -> Fiyat ve Stok Gözlemi -> Alarm
```

## Hızlı Yerel Kurulum

Windows'ta yönlendirmeli kurulum:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup-local.ps1
```

Bu yardımcı örnek `.env` dosyalarını oluşturur, yerel şifreleme anahtarını üretir ve gerekli bağımlılıkları kurar. Yönetici parolası ilk açılış ekranında belirlenir.

Gereksinimler: Python 3.11/3.12, Node.js 20/22, MongoDB 7 ve Chromium için Playwright.

Backend:

```powershell
Copy-Item backend\.env.example backend\.env
python -m pip install -r backend\requirements.txt
python -m playwright install chromium
Set-Location backend
python -m uvicorn server:app --host 127.0.0.1 --port 8000
```

`EMBEDDED_SCHEDULER=true` olan basit yerel kurulumda API, kalıcı kuyruğu tüketen tek bir gömülü işçi de başlatır. Üretim ve Docker kurulumunda bu değer `false` olmalı; normal worker, browser-worker ve scheduler ayrı süreçler olarak çalışmalıdır.

Frontend için ayrı bir terminal:

```powershell
Set-Location frontend
npm ci
npm start
```

- Arayüz: `http://127.0.0.1:3000`
- API sağlık kontrolü: `http://127.0.0.1:8000/api/health`

İlk açılışta yönetici parolası oluşturma ekranı gelir. `ADMIN_PASSWORD` önceden tanımlandıysa hesap ilk backend başlangıcında otomatik oluşturulur.

## Docker Kurulumu

```powershell
Copy-Item backend\.env.example backend\.env
docker compose up -d --build
```

Docker; `mongo`, `api`, `worker`, `browser-worker`, `scheduler` ve `frontend` servislerini ayrı çalıştırır. Durum kontrolü:

```powershell
docker compose ps
docker compose logs api worker browser-worker scheduler
```

Veritabanı, yedekler ve şifreleme anahtarı Docker volume içinde kalıcıdır.

## Ortam Ayarları

Temel ayarlar `backend/.env.example` içinde açıklanmıştır.

| Değişken | Amaç |
| --- | --- |
| `MONGO_URL`, `DB_NAME` | MongoDB bağlantısı ve veritabanı |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD` | İlk yönetici hesabı |
| `SETUP_TOKEN` | İlk kurulum ekranına isteğe bağlı ek anahtar |
| `CORS_ORIGINS` | İzin verilen kesin frontend adresleri |
| `COOKIE_SECURE` | HTTPS kurulumunda `true` olmalı |
| `APP_SECRET_KEY` | Secret store şifreleme anahtarı; üretimde güçlü ve kalıcı olmalı |
| `EMBEDDED_SCHEDULER` | Basit yerel kurulum için `true`, ayrı worker için `false` |
| `WORKER_QUEUE` | Ayrı worker sürecinde `default` veya ağ/tarayıcı işleri için `browser` |
| `BRAVE_SEARCH_API_KEY` | Yalnızca aday URL keşfi için isteğe bağlı kaynak |
| `NOTIFICATION_MODE` | `immediate` veya saatlik `digest` |
| `BACKUP_DIR`, `BACKUP_RETENTION_DAYS` | Yedek yolu ve saklama süresi |
| `AI_HISTORY_RETENTION_DAYS` | AI sohbet geçmişi saklama süresi |
| `GLOBAL_FETCH_CONCURRENCY` | Global statik istek bütçesi |
| `STORE_FETCH_CONCURRENCY` | Mağaza başına statik istek bütçesi |
| `GLOBAL_BROWSER_CONCURRENCY` | Global Playwright sayfa bütçesi |

Telegram ve AI anahtarları isteğe bağlıdır. Telegram tokeni API tarafından geri döndürülmez; veritabanında şifreli tutulur veya ortam değişkeninden okunur.

## Güvenlik

- Bütün yönetim rotaları oturum gerektirir.
- Parolalar Argon2 ile saklanır; eski kurulum uyumluluğu için güvenli geri dönüşler vardır.
- Oturum çerezi `HttpOnly` ve `SameSite=Strict`; veri değiştiren istekler CSRF doğrulamalıdır.
- Yalnızca HTTPS ve desteklenen mağaza alan adları kabul edilir.
- DNS sonucu özel, yerel, link-local veya metadata IP'sine gidiyorsa URL reddedilir.
- Her yönlendirme yeniden doğrulanır; süre, yönlendirme ve yanıt boyutu sınırlıdır.
- CORS joker değer kullanmaz.
- Debug rotaları yönetici oturumu arkasındadır ve header/cookie alanlarını döndürmez.
- CAPTCHA çözme, konut proxy'si, cihaz parmak izi sahteleme, gizli API taklidi veya erişim kontrolü atlatma kullanılmaz.

İnternete açık kurulumda HTTPS zorunludur. Örnek Caddy profili:

```powershell
Copy-Item .env.example .env
# .env içine gerçek SHOEHUNTER_DOMAIN ve PUBLIC_BACKEND_URL değerlerini girin.
# backend/.env içinde COOKIE_SECURE=true ve HTTPS originini CORS_ORIGINS'e ekleyin.
docker compose --profile https up -d --build
```

## Ürün Radarı

Radar kaydı ürün adı, birden fazla beden, cinsiyet, renk politikası, kesin hedef fiyat, minimum düşüş, mağaza kapsamı ve keşif sıklığını destekler.

Eşleştirme sırası model kodu/GTIN/SKU gibi kesin kimlikleri, korunan model belirteçlerini ve başlık benzerliğini kullanır. Yüksek güven otomatik bağlanır; orta güven kullanıcı incelemesine gider; düşük güven reddedilir. İnceleme kuyruğu doğru ürün, farklı varyant, aynı aile ve yanlış ürün kararlarını saklar.

## Mağaza Erişimi

Katmanlar sırayla kullanılır:

1. Mağazanın herkese açık arama ve ürün sayfası.
2. `robots.txt` ve sitemap ile ürün URL'si keşfi.
3. JSON-LD, OpenGraph, meta ve gömülü uygulama verisi.
4. Yapılandırıldıysa Brave Search ile yalnızca aday URL keşfi.
5. Düşük hızlı, önbellekli statik istek.
6. Gerekirse sınırlı Playwright tarayıcı havuzu.
7. Kullanıcının kendi tarayıcısından açıkça gönderdiği doğrulanmış veri.

Parser başarısızlığı “stok yok” sayılmaz. Mağaza `blocked`, `error` veya `unknown` durumuna geçer; devre kesici artan bekleme uygular. Ayarlar ekranı son 24 saatlik mağaza başarı oranını gösterir.

## Amazon Notu

Amazon HTML motoru ASIN, seçili varyant, beden stok durumu, satıcı, kargo ve kupon alanlarını ayrıştırır. Resmî katalog entegrasyonu yalnızca uygun Amazon Associates/Creators API hesabı, geçerli kullanım izni ve güncel resmî SDK ile kurulmalıdır. Eski PA-API 5 yeni kurulum için kullanılmaz.

## Yedekleme

Arayüzde **Ayarlar > JSON Yedeği Oluştur** işi kuyruğa ekler. Zamanlayıcı her gün otomatik yedek oluşturur. JSON yedekleri atomik yazılır, SHA-256 ile doğrulanır ve saklama süresine göre temizlenir.

```powershell
python scripts\backup.py
python scripts\verify_backup.py backups\shoehunter-TARIH.json
python scripts\restore_backup.py backups\shoehunter-TARIH.json
python scripts\restore_backup.py backups\shoehunter-TARIH.json --apply
```

İlk restore komutu yalnızca önizleme yapar. Uygulama verisini temizleyerek geri yüklemek için ayrıca `--replace` gerekir. Yönetici parolası, oturumlar ve secret store JSON yedeğine dahil edilmez.

MongoDB araçları kuruluysa tam arşiv:

```powershell
.\scripts\mongo-backup.ps1
.\scripts\mongo-restore.ps1 -Archive .\backups\shoehunter-mongo-TARIH.archive.gz -Apply
```

## Test ve Kalite

```powershell
python -m compileall -q backend scripts
python -m pytest -q -m "not live"
Set-Location frontend
npm test -- --watchAll=false --passWithNoTests
npm run build
```

Canlı mağaza sözleşme testleri varsayılan olarak kapalıdır:

```powershell
$env:LIVE_STORE_TESTS="1"
$env:LIVE_STORE_URLS='["https://desteklenen-magaza/urun"]'
python -m pytest -q -m live
```

GitHub Actions; Python derleme, Ruff, Black, Mypy, Pytest, frontend test/build, bağımlılık denetimleri ve secret scanning çalıştırır.

## Yerel Ağ ve Android

```powershell
.\scripts\start-lan.ps1
```

Başlatıcı o anki yerel IP'yi CORS listesine ekler ve telefon adresini ekranda gösterir. Ayrıntılar [MOBIL_KULLANIM.md](MOBIL_KULLANIM.md) dosyasındadır.
