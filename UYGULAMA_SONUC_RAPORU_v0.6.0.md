# ShoeHunter AI v0.6.0 Uygulama Sonuç Raporu

**Kaynak denetim:** `son_kontron.md`  
**Uygulama tarihi:** 12 Temmuz 2026  
**Çalışma dizini:** `C:\Users\ÖGR1\Documents\Ayakkabi`  
**Hedef sürüm:** `0.6.0 Autonomous Product Discovery`

## 1. Yönetici Özeti

Kaynak rapordaki “Uygulanmaması gereken yöntemler” bölümü bilinçli olarak uygulanmadı. Bunun dışındaki P0, P1 ve P2 önerileri çalışan uygulamaya dönüştürüldü veya dış hesap/yetki gerektiren noktalar için güvenli entegrasyon sınırı hazırlandı.

Eski rapordaki **5,5/10** değerlendirmesi artık mevcut çalışma ağacını tanımlamıyor. Sistem yalnızca kayıtlı bağlantıları kontrol eden bir prototip olmaktan çıktı; kullanıcı artık **Ürün Radarı** oluşturarak ürünü, bedenleri, renk politikasını, hedef fiyatı, asgari indirimi, mağaza kapsamını ve tarama sıklığını takip edebiliyor.

Ana sonuçlar:

- Tek yönetici hesabı, güvenli oturum, CSRF, SSRF koruması ve kesin CORS listesi eklendi.
- `WatchQuery -> DiscoveryRun -> CandidateListing -> ProductMatcher -> Listing -> Observation -> Alert` akışı kuruldu.
- Ürün kimliği model kodu, GTIN/EAN, ASIN, nesil, cinsiyet, genişlik ve kritik model belirteçleriyle güçlendirildi.
- MongoDB tabanlı kalıcı iş kuyruğu, retry, dead-letter, idempotency ve dağıtık kilit eklendi.
- Normal işler ve ağ/tarayıcı işleri ayrı worker kuyruklarına ayrıldı.
- Sitemap, robots.txt ve isteğe bağlı Brave URL keşfi katmanı eklendi.
- Mağaza sağlık ölçümü, circuit breaker ve “veri alınamadı” ayrımı eklendi.
- Alarm tekilleştirme, bekleme süresi, stok dönüşü, fiyat düşüşü, 30/90 gün dip fiyatı ve özet bildirimleri eklendi.
- Yedek, doğrulama, geri yükleme önizleme, JSON/CSV dışa aktarma ve Mongo dump araçları eklendi.
- Docker Compose, ayrı API/worker/browser-worker/scheduler süreçleri, Caddy HTTPS profili ve GitHub Actions kuruldu.
- Masaüstü ve telefon arayüzleri gerçek tarayıcıda denetlendi.

Bu rapor “her mağaza bugün kesin çalışır” iddiasında bulunmaz. Canlı mağaza sözleşme testleri varsayılan test paketinden özellikle ayrılmıştır; mağaza HTML’i, erişim politikası veya dış servis hesabı zaman içinde değişebilir.

## 2. Öneri Uygulama Matrisi

| Kaynak rapor alanı | Sonuç | Uygulama özeti |
| --- | --- | --- |
| Sprint 0: Güvenlik ve doğruluk | Tamamlandı | Kimlik doğrulama, CSRF, SSRF, CORS, secret store, rate limit, veri hataları ve indeksler |
| Sprint 1: WatchQuery ve otonom keşif | Tamamlandı | Ürün Radarı, discovery run, aday ilan, otomatik bağlama ve inceleme kuyruğu |
| Sprint 2: Ürün kimliği ve eşleştirme | Tamamlandı | Kod tabanlı kimlik, kritik belirteçler, varyant ayrımı ve güven eşikleri |
| Sprint 3: Dayanıklı mağaza erişimi | Tamamlandı | Sitemap/robots/Brave, browser pool, hız bütçesi, health ve circuit breaker |
| Sprint 4: Veri kalitesi ve alarm motoru | Tamamlandı | Değişiklik bazlı geçmiş, alarm tekilleştirme, stok dönüşü ve dip fiyat |
| Sprint 5: Operasyon ve yayınlama | Tamamlandı | Docker, ayrı süreçler, yedek, CI, metrik, HTTPS profili ve kurulum yardımcısı |
| Sprint 6: OmniHunter hazırlığı | Temel tamamlandı | Kategori ve dinamik `attributes`, genel adaptör sözleşmesi ve kullanıcı alanı temeli |
| Aktif çoklu kullanıcı | Bilinçli olarak açılmadı | Mevcut ürün tek yönetici uygulamasıdır; kayıtlar `main` kullanıcı sınırında tutulur |
| Yasaklanan erişim yöntemleri | Uygulanmadı | CAPTCHA çözme, proxy havuzu, stealth, parmak izi sahteleme ve erişim atlatma yok |

## 3. Güvenlik

### 3.1 Kimlik doğrulama ve oturum

`backend/security.py` içinde:

- Argon2 parola hash’i,
- eski bcrypt hash’lerini doğrulama desteği,
- sunucu taraflı oturum kaydı,
- HttpOnly ve SameSite cookie,
- HTTPS kurulumunda `Secure` cookie,
- CSRF cookie/header eşleştirmesi,
- başarısız giriş sınırlaması,
- oturum süresi ve güvenli çıkış

uygulandı.

İlk kurulumda `ADMIN_PASSWORD` boşsa kullanıcı güvenli ilk açılış ekranından yönetici parolasını oluşturur. Parola veritabanında açık metin tutulmaz.

### 3.2 SSRF ve URL güvenliği

Kullanıcı tarafından verilen URL için:

- yalnızca `https` kabul edilir,
- alan adı mağaza allowlist’inde olmak zorundadır,
- bilinmeyen alan adına genel motor üretilmez,
- DNS sonucu tekrar doğrulanır,
- localhost, özel ağ, link-local, loopback ve metadata IP’leri reddedilir,
- yönlendirme sonrası URL tekrar doğrulanır,
- yanıt süresi, yönlendirme sayısı ve gövde boyutu sınırlandırılır.

Bu koruma link ekleme, aday ilan, browser assist ve mağaza motoru erişimlerinde ortak kullanılır.

### 3.3 CORS, başlıklar ve hız sınırı

- `CORS_ORIGINS` kesin adres listesidir; wildcard + credentials kullanılmaz.
- API güvenlik başlıkları ekler.
- Giriş, arama, tarama ve ağır rotalar ayrı hız bütçelerine sahiptir.
- Global ve mağaza başına HTTP/Playwright eşzamanlılık sınırları vardır.

### 3.4 Telegram ve AI gizliliği

- Telegram tokeni API tarafından geri döndürülmez.
- Token şifreli secret store içinde saklanır.
- Arayüz yalnızca `configured: true` bilgisini gösterir.
- Telegram HTML içeriği escape edilir ve URL doğrulanır.
- Profil bilgileri varsayılan olarak AI sağlayıcısına gönderilmez.
- Kullanıcı açık rıza verdiğinde paylaşım yapılır ve kullanılan sağlayıcı kaydedilir.
- Sağlayıcı durumu, geçmiş saklama süresi ve “AI geçmişini sil” işlemi Profil ekranındadır.

### 3.5 Depo güvenliği

- Gerçek `.env`, anahtar, yedek, debug HTML/görsel ve yerel önbellekler `.gitignore` kapsamındadır.
- Depo taramasında OpenAI/GitHub/Telegram/Slack biçiminde gömülü secret bulunmadı.
- Çalışma kodunda veya tanılama betiklerinde stealth/impersonation paketi kalmadı.
- `SECURITY.md` güvenlik ve secret yenileme prosedürünü açıklar.

## 4. Ürün Radarı ve Otonom Keşif

`backend/discovery_service.py` ve `frontend/src/pages/ProductRadar.jsx` ile yeni ana nesne `WatchQuery` uygulandı.

Desteklenen alanlar:

- ham ve kanonik sorgu,
- marka, model, nesil, cinsiyet ve kategori,
- birden fazla beden,
- renk fark etmez / koyu / belirli renk / renk hariç tutma,
- hedef fiyat,
- asgari indirim yüzdesi ve TL tutarı,
- mağaza kapsamı,
- zorunlu ve istenmeyen model belirteçleri,
- bilinen model kodları,
- keşif sıklığı,
- ilan yenileme sıklığı,
- son ve sonraki keşif zamanı,
- aktif/duraklatılmış durum.

Keşif akışı:

1. Kullanıcı radar oluşturur.
2. Sorgu deterministik ürün kimliğine çevrilir.
3. Seçilen mağazalarda arama yapılır.
4. Sonuç yoksa izinli katmanlı URL keşfi devreye girer.
5. Her aday ürün eşleştirme motorundan geçer.
6. `0.92+` sonuç otomatik bağlanır.
7. `0.75-0.92` sonuç inceleme kuyruğuna gider.
8. Daha düşük veya kritik belirteç çakışmalı sonuç reddedilir.
9. Yeni ilan bağlandığında listing, ilk fiyat gözlemi ve alarm oluşturulur.

İnceleme ekranında:

- doğru eşleşme,
- farklı varyant,
- aynı aile,
- yanlış ürün

kararları bulunur.

Planlı kontroller yalnızca `next_refresh_at` zamanı gelen ilanları tarar. Kullanıcının “Tüm Linkleri Kontrol Et” işlemi ise tüm aktif ilanları `browser` kuyruğuna zorunlu kontrol olarak bırakır; tarama API sürecinde çalışmaz.

## 5. Keşif Kaynakları ve Mağaza Dayanıklılığı

Uygulanan sıra:

1. Mağazanın resmî/izinli arama yüzeyi,
2. robots.txt içinden sitemap keşfi,
3. sitemap URL adayları ve `lastmod`,
4. ürün URL’sinde JSON-LD, OpenGraph ve gömülü state,
5. isteğe bağlı Brave Search API ile yalnızca aday URL keşfi,
6. sınırlı standart HTTP,
7. gerekli olduğunda sınırlı Playwright render.

Fiyat ve stok için arama motoru özeti kaynak kabul edilmez; gerçek ürün sayfası doğrulanır.

Her mağaza adaptörü yeteneklerini bildirir:

- arama,
- ürün detayı,
- beden,
- sepet fiyatı,
- varyant,
- satıcı verisi,
- browser gereksinimi,
- keşif yöntemi.

Standart adaptör sonucu başlık, kanonik URL, marka/model/model kodu, cinsiyet, renk, beden, fiyat türleri, para birimi, satıcı, stok, güven ve kanıt alanlarını taşır.

`backend/store_health.py` şu ölçümleri tutar:

- son başarı ve hata,
- 24 saat başarı oranı,
- engellenme oranı,
- ortalama gecikme,
- parser sürümü,
- fiyat/stok örnek başarısı,
- circuit durumu.

Bir mağaza 403/429 veya parser hatası verdiğinde ürün “stok yok” sayılmaz. Sonuç `blocked`, `error` veya `unknown` olur ve circuit breaker gereksiz tekrarları geciktirir.

## 6. Ürün Kimliği ve Eşleştirme

`backend/product_identity.py` içinde başlık benzerliği tek karar olmaktan çıkarıldı.

Öncelik sırası:

1. GTIN/EAN,
2. MPN ve üretici model kodu,
3. SKU/style code,
4. ASIN,
5. kritik model belirteçleri,
6. marka/model/nesil/cinsiyet/genişlik uyumu,
7. normalize başlık benzerliği.

Korunan ayrımlar arasında `GTS`, `GTX`, `Gore-Tex`, `Max`, `Wide`, `Extra Wide`, `Premium`, `2.0`, `v14/v15`, trail/road, kadın/erkek/çocuk ve nesil bilgisi vardır.

`family_key` artık tek kimlik değildir. Ürün için ayrı `canonical_key`, `identity`, `identity_version` ve `family_key` tutulur.

Beden normalizasyonu tam, yarım ve üçte bir EU ölçülerini ortak biçime getirir. Radar tek beden yerine beden grubu kabul eder.

## 7. Veri Kalitesi ve Alarm Motoru

### 7.1 Fiyat ve stok geçmişi

- Fiyat veya stok değişmediyse yeni geçmiş satırı yazılmaz.
- Değişiklik yoksa yalnızca son kontrol alanları güncellenir.
- Stok durumu `in_stock`, `out_of_stock`, `unknown`, `blocked`, `not_found`, `error` olarak korunur.
- Sepet, normal, eski, kupon/kampanya ve satıcı alanları ayrı taşınır.

### 7.2 Alarm türleri

- yeni mağazada ürün,
- yeni varyant,
- istenen bedenin yeniden stoğa girmesi,
- fiyat düşüş oranı/tutarı,
- 30 veya 90 gün dip fiyatı,
- sepet fiyatı düşüşü,
- hedef fiyat + beden,
- yakın hedef fiyat isteğe bağlı bildirimi,
- listing kaybı,
- parser/mağaza veri hatası.

Her alarmda:

- `deduplication_key`,
- cooldown,
- ilk/son görülme,
- gönderim durumu,
- `is_read`,
- güven,
- kanıt

alanları bulunur.

Saatlik digest modu aynı ürünün fırsatlarını tek Telegram özetinde birleştirebilir.

### 7.3 Veri bütünlüğü

MongoDB başlangıç migrasyonu:

- URL ve ürün kanonikleştirme,
- listing ve ürün tekilleştirme,
- ilişkili kayıtların korumalı taşınması,
- Telegram secret migrasyonu,
- unique ve TTL index oluşturma

işlemlerini yapar.

Önemli indeksler:

- listing URL unique,
- ürün canonical key unique,
- kullanıcı + radar sorgusu unique,
- alarm dedup key unique,
- job idempotency key unique,
- queue + status + run_at,
- aday watch + URL unique,
- session ve health TTL indeksleri.

Ürün silme artık listing, rule, geçmiş ve alarm kayıtlarını birlikte temizler. Ürün listesi Mongo aggregation kullanır; ürün başına ayrı sorgu yapan N+1 akışı kaldırıldı.

## 8. Kaynak Rapordaki Somut Hatalar

| Hata | Sonuç |
| --- | --- |
| Amazon fallback sonunda `return []` | `return sizes` olarak düzeltildi |
| Universal alarmda `is_read` yok | Ortak alarm üreticisi her alarmda alanı yazıyor |
| Türkçe mojibake | Çalışma kaynakları UTF-8; arayüz ve bildirim metinleri düzeltildi |
| Ürün silmede alarm cascade eksik | Cascade tamamlandı |
| Ürün listesinde N+1 | Aggregation pipeline uygulandı |
| Değişmeyen fiyatın sürekli yazılması | Değişiklik bazlı geçmiş uygulandı |
| Hedefin %10 üstünde örtülü alarm | `hard_target`, `near_target_enabled`, `near_target_percent` ayrıldı |
| Stokta olmayan ürünlerin tamamen gizlenmesi | Stokta/Tümü/Stok Bekleniyor/Engelli/Hatalı/Pasif sekmeleri eklendi |
| Sürüm numaraları farklı | Backend, frontend, `VERSION.txt` ve `pyproject` `0.6.0` oldu |
| Veritabanı unique indeksleri eksik | Başlangıç migrasyonu ve indeksler eklendi |

Ürünler sayfasının varsayılanı **Stokta** ve fiyat sıralaması ucuzdan pahalıyadır. Stok bekleyen ürün silinmez; yeniden stoğa girdiğinde otomatik olarak Stokta görünümüne döner.

## 9. Amazon Düzeltmesi ve Resmî API Kararı

Amazon HTML motoru:

- ASIN,
- seçili varyant,
- bedenlerin stok durumu,
- satıcı,
- kargo,
- kupon/kampanya,
- belirsiz stok ayrımı

alanlarını işler.

Kaynak raporda Amazon Product Advertising API öneriliyordu. Bu öneri 2026 itibarıyla eskidi: Amazon resmî belgeleri PA-API’nin 15 Mayıs 2026 tarihinde kullanımdan kaldırıldığını ve Creators API’ye geçilmesi gerektiğini belirtir. Bu nedenle eski PA-API kodu eklenmedi.

Gelecekte resmî entegrasyon yapılacaksa:

- uygun Amazon Associates hesabı,
- Creators API kabul koşulları,
- gerekli nitelikli satış koşulu,
- resmî erişim kimlikleri,
- güncel resmî SDK

sağlanmalıdır.

Kaynaklar:

- [Amazon PA-API SearchItems belgesi ve kapanış bildirimi](https://webservices.amazon.com/paapi5/documentation/search-items.html)
- [Amazon Creators API belgeleri](https://affiliate-program.amazon.com/creatorsapi/docs/)
- [Amazon Associates kullanım politikaları](https://affiliate-program.amazon.com/help/operating/policies?ac-ms-src=ac-nav)

## 10. İş Kuyruğu ve Süreç Ayrımı

`backend/job_queue.py` MongoDB tabanlı kalıcı kuyruğu sağlar:

- benzersiz idempotency key,
- zamanlanmış `run_at`,
- atomik claim,
- lease,
- üstel retry,
- dead-letter koleksiyonu,
- dağıtık kilit,
- tamamlanan job TTL temizliği.

Kuyruklar:

- `default`: yedek ve bildirim özeti gibi normal işler,
- `browser`: listing kontrolü, keşif, varyant ve ağır mağaza işleri.

Basit yerel kurulumda API içindeki tek gömülü worker her iki kuyruğu tüketebilir. Docker/üretim kurulumunda:

- `api`,
- `worker`,
- `browser-worker`,
- `scheduler`

ayrı süreçlerdir. Böylece tarayıcı işi API’yi veya yedek işini bloke etmez.

## 11. Arayüz ve Mobil Kullanım

Eklenen/güncellenen ekranlar:

- giriş ve ilk yönetici kurulumu,
- Ürün Radarı,
- aday eşleşme incelemesi,
- stok durum sekmeleri,
- mağaza sağlık bilgileri,
- güvenli Telegram ayarı,
- yedek ve dışa aktarma,
- AI gizlilik rızası ve geçmiş silme,
- sürüm göstergesi,
- mobil üst ve alt gezinme.

LAN bağlantısı için frontend API adres çözümü düzeltildi. Telefon `10.x.x.x:3000` üzerinden açıldığında API için yanlışlıkla `localhost:8000` kullanmaz; sayfanın gerçek LAN hostunu kullanır.

Gerçek tarayıcı smoke testi:

- yönetici girişi,
- dashboard,
- radar oluşturma,
- ürün listesi stok sekmeleri,
- ayarlar ve token maskeleme,
- 390×844 telefon görünümü,
- yatay sayfa taşması,
- tarayıcı console error/warning

kontrollerini geçti. Console hata/uyarı sayısı sıfırdı.

## 12. Yedek, Kurulum ve Yayınlama

### 12.1 Yedek

- Atomik JSON yedek,
- SHA-256 checksum,
- şema sürümü,
- saklama süresi temizliği,
- yedek doğrulama,
- değişiklik yapmayan restore önizlemesi,
- kontrollü apply/replace restore,
- ürün JSON ve fiyat geçmişi CSV,
- Mongo dump/restore PowerShell araçları

eklendi.

Bu denetimde gerçek yerel veritabanından yeni bir yedek alındı; checksum ve şema 2 doğrulaması geçti. Geri yükleme önizlemesi veri değiştirmeden başarıyla tamamlandı.

### 12.2 Kurulum

`scripts/setup-local.ps1`:

- örnek `.env` dosyalarını hazırlar,
- güçlü `APP_SECRET_KEY` üretir,
- Python sanal ortamını oluşturur,
- backend ve frontend bağımlılıklarını kurar,
- Chromium kurar,
- MongoDB/Docker varlığını denetler.

Script sözdizimi PowerShell parser ile doğrulandı.

### 12.3 Docker ve HTTPS

`docker-compose.yml` servisleri:

- `mongo`,
- `api`,
- `worker`,
- `browser-worker`,
- `scheduler`,
- `frontend`,
- isteğe bağlı `caddy` HTTPS profili.

YAML yapılandırması parser ile doğrulandı. Bu bilgisayarda Docker çalıştırılabilir dosyası bulunmadığı için gerçek `docker compose up` testi yapılamadı.

## 13. CI ve Test Sonuçları

### Backend

- `pytest -m "not live"`: **38 geçti, 1 canlı test ayrıldı**.
- Ruff kritik Python kontrolleri: geçti.
- Black seçili güvenlik/domain/test dosyaları: geçti.
- Mypy güvenlik, kimlik, alarm ve iş kuyruğu: geçti.
- Python `compileall`: geçti.
- Sürüm tutarlılığı: `0.6.0`, geçti.
- `pip check`: kırık bağımlılık yok.

Python 3.14 üzerinde FastAPI/Starlette kaynaklı 138 gelecekte kaldırılacak API uyarısı vardır. Bunlar test hatası değildir; CI Python 3.11 üzerinde tanımlıdır.

Yerel paket kaynağı `pip-audit` paketini sunmadığı için Python güvenlik denetimi bu makinede çalıştırılamadı. GitHub Actions akışı `pip-audit -r backend/requirements.txt` adımını içerir ve GitHub ortamında zorunludur.

### Frontend

- Jest: **5/5 geçti**.
- Üretim build: başarılı; `index.html` ve hash’li JS/CSS üretildi.
- `npm audit --omit=dev --audit-level=critical`: **0 açık**.

### GitHub Actions

Her push/PR için:

- compileall,
- version check,
- Ruff,
- Black,
- Mypy,
- Pytest,
- pip-audit,
- npm test,
- npm build,
- npm audit,
- gitleaks

çalışacak şekilde `.github/workflows/ci.yml` eklendi.

## 14. Bilinçli Olarak Kullanılmayan Yöntemler

Aşağıdakiler ana uygulamada, mağaza motorlarında ve tanılama betiklerinde kullanılmıyor:

- CAPTCHA çözme servisi,
- konut proxy havuzu,
- cihaz parmak izi sahteleme,
- saldırgan User-Agent rotasyonu,
- Playwright stealth,
- `curl_cffi` impersonation,
- gizli/kimlik doğrulamalı API taklidi,
- erişim kontrolü atlatma,
- sahte oturum çiftliği.

Engellenen mağaza için doğru sonuç `blocked/unknown` ve artan bekleme süresidir. Sistem “stok yok” şeklinde sahte kesinlik üretmez.

## 15. Dış Yapılandırma Gerektiren Noktalar

Kod hazırdır; aşağıdaki değerler operatöre aittir:

- `ADMIN_PASSWORD` veya ilk açılışta oluşturulan yönetici parolası,
- kalıcı `APP_SECRET_KEY`,
- gerçek frontend adreslerini içeren `CORS_ORIGINS`,
- HTTPS için `COOKIE_SECURE=true`,
- Telegram token/chat ID,
- kullanılacak AI sağlayıcısının anahtarı,
- isteğe bağlı Brave Search API anahtarı,
- resmî Amazon entegrasyonu istenirse uygun Creators API hesabı ve yetkileri.

Canlı mağaza testleri ağ yükü ve mağaza politikaları nedeniyle opt-in bırakılmıştır. Bir mağazanın yapısı değişirse parser sağlık sistemi bunu “stok yok” olarak değil, geliştirici/mağaza sağlık sorunu olarak gösterecektir.

## 16. Çalışma Ağacı Notu

Bu çalışma sırasında commit veya GitHub push yapılmadı. Çalışma ağacında bu görevden önce var olan çok sayıda geçici dosya silme/değişiklik kaydı bulunuyordu; bunlar geri alınmadı. Sonraki temiz repo/commit işleminde kaynak dosyalar ile eski `gecici/`, araştırma çıktıları ve kişisel tanılama betikleri bilinçli olarak ayrılmalıdır.

Denetim için açılan 3000 ve 8000 portlarındaki test servisleri kapatıldı. Test amacıyla oluşturulan geçici veritabanı silindi. Sahiplik izni nedeniyle kaldırılamayan yerel araç önbellekleri `.gitignore` içindedir ve repoya girmez.

## 17. Nihai Karar

Kaynak raporun temel hedefi gerçekleşti:

> Kullanıcı bağlantıyı değil, ürünü takip eder.

ShoeHunter AI v0.6.0 artık güvenli tek yönetici oturumu, sürekli ürün keşfi, deterministik eşleştirme, mağaza dayanıklılığı, doğru alarm üretimi, kalıcı iş kuyruğu ve yayınlama araçları olan bir uygulamadır.

Kalan risk kod mimarisinden çok dış dünyadadır: mağaza sayfalarının değişmesi, mağaza erişim politikaları, dış servis anahtarları ve üretim sunucusunun doğru yapılandırılması. Bu riskler health/circuit/CI/canlı sözleşme testi katmanlarıyla görünür ve yönetilebilir hâle getirildi.
