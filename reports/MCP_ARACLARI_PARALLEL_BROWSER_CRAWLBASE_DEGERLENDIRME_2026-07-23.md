# MCP Araclari Degerlendirme Raporu

Tarih: 2026-07-23

Kapsam:

- `etairl/parallel-browser-mcp`
- `crawlbase/crawlbase-mcp`
- `microsoft/playwright-mcp`
- ShoeHunter / Urun Radari projesine muhtemel katkisi

## Kisa Sonuc

Uc MCP araci da proje icine ana koddan izole sekilde kuruldu.

- `parallel-browser-mcp`: Yerel veya harici saglayicilar uzerinden birden fazla tarayici oturumunu ayni MCP server altinda paralel yonetir. Bizim proje icin en faydali tarafi, coklu magazalarda hizli test, DOM inceleme, ekran goruntusu alma ve ayni urunun farkli sitelerde paralel kontroludur.
- `@crawlbase/mcp`: Crawlbase altyapisiyla canli web sayfasi, markdown ve screenshot cekmeye yarar. Bizim proje icin en faydali tarafi, zor JS-render sayfalarda tekil denetim ve arama/urun sayfasi kaniti toplama olabilir. Ancak token ve servis maliyeti vardir.
- `@playwright/mcp`: Microsoft'un resmi Playwright MCP serveridir. Tarayici otomasyonunu structured accessibility snapshot uzerinden LLM'e sunar. Bizim proje icin en guvenilir genel test ve denetim aracidir.

Bu araclar urun radarinin kendi motorunun yerine gecmemelidir. Daha dogru konumlari:

- test/denetim yardimcisi,
- kampanya kaniti toplama yardimcisi,
- site motorlarini gelistirirken HTML/screenshot farklarini yakalama yardimcisi,
- manuel veya yarim otomatik kalite kontrol katmani.

## Kurulum Durumu

### Parallel Browser MCP

Yerel klasor:

`tools/parallel-browser-mcp`

Kurulan paket:

`parallel-browser-mcp@0.1.14`

Node gereksinimi:

`>=18`

Kurulum sonucu:

`npm install` basarili.

Audit sonucu:

`found 0 vulnerabilities`

### Crawlbase MCP

Yerel klasor:

`tools/crawlbase-mcp`

Kurulan paket:

`@crawlbase/mcp@1.3.0`

Node gereksinimi:

`>=18`

Kurulum sonucu:

`npm install` basarili.

Audit sonucu:

`found 0 vulnerabilities`

Not:

Crawlbase gercek crawl icin `CRAWLBASE_TOKEN` ve `CRAWLBASE_JS_TOKEN` ister. Bu tokenlar elimizde olmadigi icin canli Crawlbase istegi yapilmadi.

### Microsoft Playwright MCP

Yerel klasor:

`tools/playwright-mcp`

Kurulan paket:

`@playwright/mcp@0.0.78`

Node gereksinimi:

`>=18`

Kurulum sonucu:

`npm install` basarili.

Audit sonucu:

`found 0 vulnerabilities`

Komut dogrulamasi:

`playwright-mcp --help` basarili calisti.

Yerel HTTP modunda baslatma:

```powershell
.\scripts\start-playwright-mcp.ps1
.\scripts\start-playwright-mcp.ps1 -Mode mobile
```

Varsayilan endpoint:

`http://127.0.0.1:8931/mcp`

Not:

Bu adimda kullanici istegi nedeniyle site/uygulama testleri bilerek calistirilmadi. Testler sonraki komuta birakildi.

## Eklenen Dosyalar

- `tools/parallel-browser-mcp/package.json`
- `tools/parallel-browser-mcp/package-lock.json`
- `tools/parallel-browser-mcp/node_modules/`
- `tools/crawlbase-mcp/package.json`
- `tools/crawlbase-mcp/package-lock.json`
- `tools/crawlbase-mcp/node_modules/`
- `tools/playwright-mcp/package.json`
- `tools/playwright-mcp/package-lock.json`
- `tools/playwright-mcp/node_modules/`
- `tools/playwright-mcp/README.md`
- `tools/mcp-config.examples.json`
- `scripts/start-playwright-mcp.ps1`
- `reports/MCP_ARACLARI_PARALLEL_BROWSER_CRAWLBASE_DEGERLENDIRME_2026-07-23.md`

## Parallel Browser MCP Ne Saglar?

Kaynaklara gore `parallel-browser-mcp`, her tarayici oturumuna sayisal bir `sessionId` verir ve su tip araclari MCP uzerinden sunar:

- oturum baslatma/kapatma,
- URL acma,
- tiklama,
- form doldurma,
- screenshot alma,
- DOM snapshot alma,
- JavaScript degerlendirme,
- mouse/klavye islemleri,
- selector bekleme.

Desteklenen saglayicilar:

- Playwright ile lokal Chromium,
- Browserbase,
- Anchor Browser,
- Cloudflare Browser Run.

Bizim projede faydali oldugu yerler:

- Ayni urun icin 10-30 magazayi paralel goruntu/DOM testinden gecirmek.
- Yeni site motoru yazarken sayfada fiyat, beden, stok ve sepet fiyatinin nerede durdugunu hizli tespit etmek.
- "Biz neden D:\\urun_ayakkabi kadar urun bulamadik?" gibi kiyaslarda ayni anda birden fazla arama sayfasi acip farklari kaydetmek.
- Uretim motoruna kod yazmadan once, manuel denetim ve selector dogrulama yapmak.

Sinirlari:

- Kendi basina urun eslestirme zekasi degildir.
- Kendi basina fiyat/beden veri modeli degildir.
- Lokal Playwright kullanildiginda IP, oturum ve site erisim sinirlari yine aynidir.
- Cloud/browser saglayicilari kullanilirsa maliyet, gizlilik ve hesap yonetimi gerekir.

## Crawlbase MCP Ne Saglar?

Kaynaklara gore Crawlbase MCP temel olarak uc canli web araci sunar:

- `crawl`: HTML alma,
- `crawl_markdown`: okunabilir markdown cikarma,
- `crawl_screenshot`: sayfa ekran goruntusu alma.

Crawlbase tarafinda Normal Token ve JavaScript Token ayrimi vardir:

- Normal token daha statik sayfalar icin,
- JS token client-side render edilen sayfalar ve screenshot gibi durumlar icin.

Bizim projede faydali oldugu yerler:

- Google Lens benzeri dis kaynak kaniti toplamaya yakin bir yardimci olabilir.
- JS ile render edilen urun sayfalarinda HTML snapshot almak icin kullanilabilir.
- Kampanya kaniti bulunamayan magazalarda tek seferlik denetim icin yararli olabilir.
- Urun sayfasi screenshotlarini rapora delil olarak eklemek icin pratik olabilir.

Sinirlari:

- Ucretli API / token bagimliligi getirir. Bu, daha once avantaj gordugumuz "ucretsiz API kullanmama" ilkesine ters olabilir.
- Her sayfayi surekli Crawlbase ile kontrol etmek maliyet ve bagimlilik yaratir.
- Ana radar motoru yerine kullanilirsa sistem dis servise fazla bagimli hale gelir.

## Microsoft Playwright MCP Ne Saglar?

Microsoft Playwright MCP, Playwright'in resmi MCP arabirimidir. LLM'e sayfayi agir screenshot analizi yerine structured accessibility snapshot ile verir. Bu, buton, link, input, liste, fiyat metni ve beden secenekleri gibi alanlari daha deterministik okumaya yardim eder.

Kurulumda dogrulanan baslica kabiliyetler:

- Chromium/Chrome, Firefox, WebKit veya Edge secme.
- Headless veya gorunur tarayici calistirma.
- Mobil cihaz emulasyonu: `--mobile` veya `--device`.
- Belirli viewport boyutu verme.
- Console ve network kayitlari alma.
- PDF, vision ve devtools kabiliyetlerini acma.
- Storage state ile oturum/cookie durumu tasima.
- Isolated mod ile temiz, gecici profil kullanma.
- HTTP port modu ile MCP serveri ayri servis gibi calistirma.
- Service worker engelleme.
- Proxy parametresi verme.

Bizim projede en faydali oldugu yerler:

- Urun detay sayfasinda fiyat, beden, stok, sepette fiyat ve kampanya metinlerini denetleme.
- Mobil gorunumde site farklarini test etme.
- "Radara link ile eklenen urun neden taranmadi?" gibi akislarda sayfanin gercek UI durumunu inceleme.
- Frontend testlerinde kullanici gibi tiklama/doldurma/arama akisini dogrulama.
- Zegama 2 gibi daha cok sonuc bulan dis proje ile bizim radar arasindaki farki sayfa duzeyinde denetleme.
- Sepet fiyatinin gorunur olup olmadigini, kampanya metninin DOM'da mi yoksa sadece goruntude mi oldugunu ayirma.

Sinirlari:

- Kendisi urun eslestirme motoru degildir.
- Kendisi fiyat mantigi veya kategori zekasi uretmez.
- Her sitede CAPTCHA/erisim korumasi varsa bunu asmak icin kullanilmamali.
- MCP tool cagrilari buyuk accessibility snapshot urettigi icin uzun taramalarda token ve performans maliyeti olabilir.

## Uc Arac Arasinda Tercih

ShoeHunter icin siralama:

1. `@playwright/mcp`: En guvenilir ve resmi genel test/denetim araci. Lokal calisir, Microsoft kaynakli, dokumantasyonu kuvvetli. Bizim icin birinci tercih.
2. `parallel-browser-mcp`: Coklu session ihtiyaci varsa faydali. Birden fazla magazayi ayni anda acma senaryosunda Playwright MCP'den daha pratik olabilir.
3. `@crawlbase/mcp`: Token varsa zor sayfalarda ek kanit almak icin iyi. Fakat surekli radar motorunda varsayilan olmamali.

En mantikli kombinasyon:

- Gunluk lokal gelistirme/test: `@playwright/mcp`
- Ayni anda cok site deneme: `parallel-browser-mcp`
- Zor sayfa / JS-render / dis kanit: `@crawlbase/mcp`

## ShoeHunter Icin Onerilen Kullanim

### 1. Ana Motor Degil, Denetim Motoru

Bu iki arac ana fiyat takip motoru olmamali. Ana motor yine bizim mevcut site motorlari, HTML parserlari, urun eslestirme ve bildirim mantigi olmali.

En dogru mimari:

- Mevcut radar: asil veri toplama.
- Microsoft Playwright MCP: genel UI/site denetimi.
- Parallel Browser MCP: site motoru gelistirme ve selector/ekran denetimi.
- Crawlbase MCP: token varsa zor sayfalarda ek kanit ve snapshot.

### 2. Zor Site Denetim Modu

Bir magazada fiyat, beden veya sepet fiyat kaniti yakalanamiyorsa:

1. Once mevcut motor calisir.
2. Sonuc belirsizse Parallel Browser ile DOM/screenshot denetimi yapilir.
3. Hala belirsizse ve token varsa Crawlbase ile HTML/markdown/screenshot kaniti alinir.
4. Kanit bulunursa site motoruna kalici selector veya parser kurali eklenir.

Bu yontem maliyeti dusuk tutar. Crawlbase sadece gerekli noktada kullanilir.

### 3. Coklu Magaza Test Hatti

Parallel Browser MCP, ozellikle "hepsini sec" veya coklu magaza denemelerinde test yardimcisi olabilir:

- Her magaza icin ayri session,
- arama sayfasi acma,
- urun linklerini toplama,
- fiyat/beden DOM alanlarini snapshotlama,
- goruntu ile raporlama.

Bu, manuel test suresini ciddi azaltabilir.

## Risk ve Guvenlik Degerlendirmesi

Bu araclar tarayici kontrolu ve canli web erisimi verdigi icin guclu araclar sinifindadir.

Onemli sinir:

Robots kurallarini, CAPTCHA'lari veya erisim korumalarini atlatmaya yonelik stealth, proxy rotasyonu, kimlik sahteciligi veya benzeri yontemler urun koduna ozellik olarak eklenmemelidir. Guvenli ve surdurulebilir kullanim; kamuya acik sayfalar, normal hiz limitleri, site kurallarina uyum, manuel denetim ve kullanici tarafindan saglanan HTML/screenshot kanitlari uzerinden olmali.

Crawlbase'in pazarlama metinlerinde anti-bot/proxy gibi kabiliyetler gecse de ShoeHunter icin onerilen kullanim bu degildir. Bizim acimizdan dogru kullanim "kanit alma ve denetim"dir.

## Bizim Siteye Faydasi Var mi?

Evet, fakat dogru yerde kullanilirsa.

En yuksek fayda:

- site motoru gelistirme,
- coklu site test otomasyonu,
- kampanya/sepet fiyati kaniti,
- HTML/screenshot arastirma,
- radar sonuc farklarini denetleme.

Daha dusuk fayda:

- surekli uretim taramasi,
- her urun icin Crawlbase kullanma,
- ana akim magazalarda agresif veri cekme.

Uretimde en mantikli secim:

- Varsayilan: mevcut radar motorlari.
- Yardimci: Parallel Browser ile lokal test.
- Opsiyonel: Crawlbase token varsa sadece belirsiz/zor vakalarda ek kanit.

## Uygulama Plani

1. MCP araclarini simdilik proje icinde izole tut.
2. Site motoru yazarken `tools/mcp-config.examples.json` icindeki ornekleri kullan.
3. Crawlbase tokenlari eklenirse once 5-10 URL'lik kontrollu test yap.
4. Elde edilen HTML/screenshot kanitlarindan kalici site parser kurali uret.
5. Surekli radar taramasinda dis servis kullanimi icin kota, maliyet ve hata limiti koy.
6. Playwright MCP'yi ilk etapta Decathlon, Intersport, Adidas, Nike, Hepsiburada, Trendyol gibi sitelerin UI denetiminde kullan.

## Radar Entegrasyon Durumu

2026-07-23 itibariyla MCP ozelligi Product Radar ekranina ilk katman olarak eklendi.

Eklenen radar yetenekleri:

- Radar kartindan `MCP denetimi hazirla`.
- Radar detay ekranindan desktop MCP toplu denetim hazirlama.
- Radar detay ekranindan mobil MCP denetim hazirlama.
- Tek aday link icin `MCP kaniti` hazirlama.
- Backend tarafinda `POST /api/watches/{watch_id}/mcp-audit`.
- Radar detay cevabinda `mcp_audits` kayitlari.
- Watch kaydinda `last_mcp_audit_summary` ozeti.

Bu katman canli tarama sonucunu henuz doldurmaz; Playwright MCP ile yapilacak denetim icin hedef linkleri, kontrol basliklarini ve runner bilgisini kayda alir. Canli sayfa kaniti, screenshot ve accessibility snapshot doldurma adimi sonraki test/entegrasyon komutuna birakildi.

Kullanici istegi nedeniyle bu adimda test calistirilmadi.

## Kaynaklar

- Parallel Browser MCP GitHub / npm bilgileri: `https://github.com/etairl/parallel-browser-mcp`
- Parallel Browser MCP paket ozeti: `parallel-browser-mcp@0.1.14`
- Crawlbase MCP GitHub / npm bilgileri: `https://github.com/crawlbase/crawlbase-mcp`
- Crawlbase MCP paket ozeti: `@crawlbase/mcp@1.3.0`
- Crawlbase MCP dokumantasyonu: `https://crawlbase.com/docs/ai-mcp`
- Microsoft Playwright MCP GitHub / npm bilgileri: `https://github.com/microsoft/playwright-mcp`
- Microsoft Playwright MCP paket ozeti: `@playwright/mcp@0.0.78`
