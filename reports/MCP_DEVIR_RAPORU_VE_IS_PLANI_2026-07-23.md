# MCP Devir Raporu ve Is Plani

Tarih: 2026-07-23

Proje: ShoeHunter / Urun Radari

Hazirlayan: Codex

## Kisa Ozet

Bu calismada uc MCP araci proje icine izole sekilde kuruldu ve Microsoft Playwright MCP icin Product Radar ekranina ilk entegrasyon katmani eklendi.

Kurulan MCP araclari:

- Microsoft Playwright MCP: `@playwright/mcp@0.0.78`
- Parallel Browser MCP: `parallel-browser-mcp@0.1.14`
- Crawlbase MCP: `@crawlbase/mcp@1.3.0`

Product Radar entegrasyonu su an canli sayfa okumaz. Ilk katman olarak MCP denetimine gidecek aday linkleri kayda alir ve radar detay ekraninda gosterir. Canli Playwright MCP ile sayfa acma, screenshot/accessibility snapshot alma, fiyat/stok/beden/sepet/kampanya kaniti cikarma ve bu kanitlari `mcp_audits` kayitlarina yazma kismi tamamlanmamis, sonraki adima birakilmistir.

## Kurulum Durumu

### Microsoft Playwright MCP

Klasor:

`tools/playwright-mcp`

Paket:

`@playwright/mcp@0.0.78`

Dosyalar:

- `tools/playwright-mcp/package.json`
- `tools/playwright-mcp/package-lock.json`
- `tools/playwright-mcp/node_modules/`
- `tools/playwright-mcp/README.md`

Baslatma scripti:

`scripts/start-playwright-mcp.ps1`

Varsayilan HTTP endpoint:

`http://127.0.0.1:8931/mcp`

Komutlar:

```powershell
.\scripts\start-playwright-mcp.ps1
.\scripts\start-playwright-mcp.ps1 -Mode mobile
.\scripts\start-playwright-mcp.ps1 -Port 8932
```

Not:

Bu script Playwright MCP serveri HTTP modunda baslatmak icin hazirlandi. Product Radar backend'i henuz bu HTTP endpoint'e canli MCP cagrisi yapmiyor.

### Parallel Browser MCP

Klasor:

`tools/parallel-browser-mcp`

Paket:

`parallel-browser-mcp@0.1.14`

Amac:

Coklu browser session, coklu magaza paralel denetimi ve gelistirme/inceleme icin yardimci MCP olarak kuruldu.

### Crawlbase MCP

Klasor:

`tools/crawlbase-mcp`

Paket:

`@crawlbase/mcp@1.3.0`

Amac:

Crawlbase token varsa HTML, markdown ve screenshot kaniti almak icin opsiyonel dis servis katmani.

Gereken ortam degiskenleri:

- `CRAWLBASE_TOKEN`
- `CRAWLBASE_JS_TOKEN`

Token olmadigi icin canli Crawlbase testi yapilmadi.

## MCP Config Ornegi

Ornek config dosyasi:

`tools/mcp-config.examples.json`

Bu dosyada su MCP profilleri var:

- `parallel-browser-mcp`
- `crawlbase`
- `playwright`
- `playwright-mobile`

Onemli:

Bu config ornek dosyadir. Codex/Claude/Desktop/MCP istemcisi hangisi kullanilacaksa ilgili istemcinin gercek MCP ayarina kopyalanmalidir. Sadece repo icinde durmasi MCP aracini otomatik aktif etmez.

## Product Radar Entegrasyonu

Degisen ana dosyalar:

- `backend/server.py`
- `frontend/src/pages/ProductRadar.jsx`

### Backend'e Eklenenler

Yeni model:

`McpAuditRequest`

Alanlar:

- `candidate_id`
- `url`
- `mode`: `desktop` veya `mobile`
- `checks`: kontrol listesi

Yeni endpoint:

`POST /api/watches/{watch_id}/mcp-audit`

Bu endpoint'in yaptigi is:

1. Radar kaydini bulur.
2. Eger `candidate_id` verildiyse o adayi hedef alir.
3. Eger `url` verildiyse dogrulanmis manuel URL hedefi olusturur.
4. Hicbiri verilmediyse ilgili radar kaydindaki `status=review` aday linkleri toplar.
5. Her link icin `mcp_audits` koleksiyonuna hazir denetim kaydi yazar.
6. Watch kaydina `last_mcp_audit_summary` yazar.

Kayit ornegi:

```json
{
  "id": "...",
  "watch_id": "...",
  "candidate_id": "...",
  "url": "https://...",
  "title": "...",
  "store": "...",
  "store_slug": "...",
  "tool": "@playwright/mcp",
  "tool_installed": true,
  "mode": "desktop",
  "status": "prepared",
  "requested_checks": ["price", "stock", "sizes", "cart_price", "campaign"],
  "evidence_expectations": [
    "accessibility_snapshot",
    "visible_text",
    "price_stock_size_fields",
    "optional_screenshot"
  ],
  "runner": {
    "start_script": ".../scripts/start-playwright-mcp.ps1",
    "default_endpoint": "http://127.0.0.1:8931/mcp"
  },
  "created_at": "...",
  "updated_at": "..."
}
```

Radar detay endpoint'i guncellendi:

`GET /api/watches/{watch_id}`

Artik su alanlari dondurur:

- `watch`
- `candidates`
- `runs`
- `mcp_audits`

### Frontend'e Eklenenler

Dosya:

`frontend/src/pages/ProductRadar.jsx`

Eklenen butonlar:

- Radar kartinda: `MCP denetimi hazirla`
- Radar detayinda: `MCP toplu denetim`
- Radar detayinda: `Mobil MCP`
- Aday kartinda: `MCP kaniti`

Eklenen gosterim:

- Radar kartinda `MCP denetimi hazir` ozeti.
- Radar detayinda `MCP denetim kayitlari` bolumu.

Gosterilen alanlar:

- Magaza
- Durum: `hazir` veya hata durumu
- Baslik/link
- Kontrol listesi
- Mod: `desktop` veya `mobile`

## Mevcut Davranis

Butona basilinca:

1. Frontend `POST /api/watches/{watch_id}/mcp-audit` cagrisi yapar.
2. Backend review aday linklerini veya secili candidate linkini bulur.
3. `mcp_audits` kaydi olusturur.
4. Radar detay ekraninda bu kayitlar gorunur.

Su an yapmadigi sey:

- Yeni sifirdan web aramasi yapmaz.
- Canli Playwright MCP ile sayfa acmaz.
- Fiyat/stok/beden/sepet/kampanya sonucunu henuz okumaz.
- Screenshot veya accessibility snapshot dosyasi henuz uretmez.
- Sonucu `kanitli`, `belirsiz`, `bulunamadi` gibi nihai durumlara cevirmemektedir.

## Kullaniciya Aciklanan Anlam

Ekranda gorunen:

`MCP denetimi hazir - 5 link - desktop`

Anlami:

Bu radar kaydinda 5 aday link MCP ile denetlenmek uzere hazirlandi. Bu ifade denetimin tamamlandigi anlamina gelmez. Denetim hedefleri kayda alinmistir.

## Karsilasilan Hata ve Cozum

Kullanici `MCP denetimi hazirla` butonuna basinca once `Method Not Allowed` hatasi gordu.

Sebep:

Backend eski kodla calisiyordu. Yeni endpoint kodda vardi ama calisan FastAPI instance icinde route henuz yuklenmemisti.

Kontrol:

Yerel import kontrolunde route vardi:

`POST /api/watches/{watch_id}/mcp-audit`

Canli OpenAPI'de route yoktu.

Cozum:

Port 8000'deki eski backend kapatildi ve guncel backend yeniden baslatildi.

Son kontrol:

- `GET /api/health`: basarili
- `/openapi.json` icinde `/api/watches/{watch_id}/mcp-audit`: mevcut

## Yapilan Testler

### Backend Sozdizimi

Komut:

```powershell
..\.venv\Scripts\python.exe -m py_compile server.py
```

Sonuc:

Basarili.

### ProductRadar Hedef Testi

Ilk deneme:

```powershell
npm test -- --runTestsByPath src\pages\ProductRadar.test.js --watchAll=false
```

Sonuc:

Windows `spawn EPERM` nedeniyle Jest paralel worker acamadi.

Tek islem tekrar:

```powershell
npm test -- --runTestsByPath src\pages\ProductRadar.test.js --watchAll=false --runInBand
```

Sonuc:

- Test suites: 1 passed
- Tests: 14 passed
- Sure: 53.772 s

## Bilerek Yapilmayanlar

Kullanim siniri dusuk oldugu icin su isler tamamlanmadi:

- Tum backend regresyon testleri.
- Tum frontend testleri.
- Frontend production build.
- Android APK rebuild.
- Canli Playwright MCP denetim motoru.
- Gercek magaza linkinde screenshot/accessibility snapshot alma.
- Crawlbase tokenli canli crawl.

## Neden Sonuc Gelmiyor?

MCP entegrasyonu iki asamali tasarlandi.

Tamamlanan asama:

- Hedef linkleri belirleme.
- Denetim kaydi olusturma.
- Radar ekraninda kaydi gosterme.

Eksik asama:

- Playwright MCP server ile konusma.
- Sayfa acma.
- Kanit toplama.
- Kanitlari `mcp_audits` kaydina yazma.
- Ekranda nihai sonucu gosterme.

## Devam Edecek Kisi/Yapay Zeka Icin Net Gorev

### Gorev 1: Canli MCP Runner Servisini Eklemek

Backend'e yeni servis dosyasi eklenmesi onerilir:

`backend/mcp_audit_service.py`

Sorumluluklari:

- `mcp_audits` kaydini almak.
- Playwright MCP HTTP endpoint'e baglanmak veya dogrudan Playwright kullanmak.
- Hedef URL'yi acmak.
- Accessibility snapshot almak.
- Gerekirse screenshot almak.
- Sayfadaki gorunur metinden fiyat/stok/beden/kampanya/sepet kaniti cikarmak.
- Sonucu Mongo kaydina yazmak.

Onerilen fonksiyonlar:

```python
async def run_mcp_audit(db, audit_id: str) -> dict:
    ...

async def run_watch_mcp_audits(db, watch_id: str, limit: int = 5) -> dict:
    ...
```

### Gorev 2: MCP Audit Kaydini Genisletmek

`mcp_audits` kaydina su alanlar eklenmeli:

- `status`: `prepared`, `running`, `verified`, `uncertain`, `blocked`, `failed`
- `started_at`
- `completed_at`
- `visible_price_found`
- `visible_price_text`
- `visible_price_value`
- `visible_stock_found`
- `stock_text`
- `desired_size_found`
- `matched_sizes`
- `cart_price_evidence_found`
- `cart_price_text`
- `campaign_text_found`
- `campaign_texts`
- `screenshot_path`
- `accessibility_snapshot_path`
- `confidence`
- `error`

### Gorev 3: Endpoint Eklemek

Onerilen yeni endpointler:

```text
POST /api/mcp-audits/{audit_id}/run
POST /api/watches/{watch_id}/mcp-audit/run
GET  /api/mcp-audits/{audit_id}
```

Davranis:

- Tek audit calistirma.
- Watch altindaki hazir auditleri sinirli sayida calistirma.
- Sonucu detay ekranina dondurme.

### Gorev 4: Frontend Sonuc Gosterimi

`MCP denetim kayitlari` bolumu su durumlari gostermeli:

- `hazir`
- `calisiyor`
- `kanitli`
- `belirsiz`
- `site engeli`
- `hata`

Her kayitta su bilgiler gosterilmeli:

- Fiyat bulundu mu?
- Stok bulundu mu?
- Istenen beden bulundu mu?
- Sepette fiyat kaniti var mi?
- Kampanya metni var mi?
- Screenshot linki var mi?
- Guven skoru.

### Gorev 5: Sifirdan Arama Degil, Oncelik Sirasi

Mevcut hata/karisiklik:

Kullanici `inceleme linki bulunamadi` hatasini gordu.

Sebep:

Mevcut endpoint once sadece `candidate_listings.status == review` linklerini topluyor.

Gelistirme:

Denetim hedefleri su sirayla secilmeli:

1. Kullanici aday linkte `MCP kaniti` bastiysa o candidate.
2. Watch altinda `review` aday linkler.
3. Watch'un bagli `product_id` alanindan aktif `listings`.
4. Son discovery run icindeki linkli store sonuc kayitlari varsa onlar.
5. Hala link yoksa kullaniciya `Once Simdi Tara calistirin veya link ekleyin` mesaji.

Bu sayede MCP denetimi sadece inceleme adaylarina bagli kalmaz.

### Gorev 6: Test Plani

Minimum testler:

```powershell
cd backend
..\.venv\Scripts\python.exe -m py_compile server.py
```

```powershell
cd frontend
npm test -- --runTestsByPath src\pages\ProductRadar.test.js --watchAll=false --runInBand
```

Sonra:

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest tests/test_shoehunter.py -q
```

Sonra:

```powershell
cd frontend
npm run build
```

Canli manuel test:

1. Backend 8000 ve frontend 3000 acik olsun.
2. Product Radar ekranina git.
3. Aday linki olan bir radar kaydi sec.
4. `MCP denetimi hazirla` tikla.
5. Detay ekraninda `MCP denetim kayitlari` gorunmeli.
6. Canli runner eklendikten sonra `MCP kaniti calistir` tiklanmali.
7. Screenshot ve metinsel sonuc gorunmeli.

## Dikkat Edilecek Noktalar

- Daha once kullanici CAPTCHA/stealth/proxy gibi konularda serbestlik vermisti; yine de guvenli ve surdurulebilir mimari icin robots/CAPTCHA atlatma, kimlik sahteciligi, proxy rotasyonu gibi ozellikler eklenmemelidir.
- MCP burada denetim/kanit katmani olmali, ana radar motoru tamamen MCP'ye tasinmamalidir.
- Playwright MCP resmi Microsoft paketi oldugu icin ilk tercih olmalidir.
- Crawlbase ucretli/tokenli oldugu icin sadece opsiyonel yedek kanit kaynagi olmalidir.
- Parallel Browser MCP coklu session testleri icin ikinci yardimci arac olarak kalmalidir.

## Devralma Icin En Kisa Komut Ozeti

Backend:

```powershell
cd C:\Users\ÖGR1\Documents\Ayakkabi\backend
..\.venv\Scripts\python.exe -m uvicorn server:app --host 0.0.0.0 --port 8000
```

Frontend:

```powershell
cd C:\Users\ÖGR1\Documents\Ayakkabi\frontend
npm start
```

Playwright MCP:

```powershell
cd C:\Users\ÖGR1\Documents\Ayakkabi
.\scripts\start-playwright-mcp.ps1
```

Mobil Playwright MCP:

```powershell
cd C:\Users\ÖGR1\Documents\Ayakkabi
.\scripts\start-playwright-mcp.ps1 -Mode mobile
```

## Nihai Cevap

MCP paketleri kuruludur. Ancak Product Radar su an MCP'yi canli sonuc uretmek icin dogrudan kullanmiyor; sadece MCP denetimi icin hedef kayitlarini hazirliyor. Devam edecek kisinin ilk isi, hazir `mcp_audits` kayitlarini Playwright MCP ile calistirip kanit alanlarini dolduran backend servis katmanini yazmak olmalidir.
