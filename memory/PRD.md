# ShoeHunter AI / OmniHunter — PRD & Memory

## Orijinal Problem Tanımı
Kullanıcının MD dosyasında (ShoeHunterAI_OmniHunter_Master_Proje_Tanimi.md) detaylı tanımlanan sistem:
Türkiye pazarında spor ayakkabı odaklı, AI destekli fiyat/stok/beden/varyant/fırsat takip sistemi.
Temel ilkeler: yanlış alarm üretme (beden stokta değilse alarm yok), sepet indirimi yakalama,
pz-variant/JSON-LD okuma, zero-link AI arama, Spektrum Modu, Telegram bildirimleri, scheduler.
Kullanıcının eski Flask kodu /app kök dizininde referans olarak duruyor (models/, stores/, services/ vb).

## Kullanıcı Seçimleri
- GitHub repo 404 döndü; eski Flask kodu zaten workspace'e yüklüydü (referans alındı, Intersport parser mantığı taşındı)
- Telegram: token backend/.env icinde tutulur; repoya veya not dosyalarina gercek token yazilmaz. chat_id backend/.env icinde tutulur.
- AI: Emergent Universal Key (GPT-5.4)
- Mağaza: mümkün olduğunca çok mağaza

## Mimari
- Backend: FastAPI (/app/backend) — server.py (API), engines.py (mağaza motorları), services.py (kontrol/alarm/telegram/batch), ai_service.py (AI Koç SSE + arama normalizasyonu)
- Frontend: React 18 + Tailwind (dark "Hypebeast Terminal" tema, Outfit/IBM Plex Sans/JetBrains Mono, volt yeşil #CCFF00), sayfalar: Panel, Ürünler, Ürün Detay, Uyarılar, AI Arama, AI Koç, Ayarlar, Debug Lab, Profil
- DB: MongoDB (products, listings, price_history, rules, alerts, check_runs, settings, user_profile, ai_messages) — uuid id'ler
- Scheduler: APScheduler (ayarlardan aç/kapa + aralık)

## Mağaza Motorları (engines.py)
- Intersport (özel parser): Sitede standart `<button>` yerine `<pz-button>`, `<pz-variant-option>` (Web Components) kullanılmaktadır. `in_stock` bilgisi `js-add-to-cart` / `add-to-cart` içeren butonların varlığı ile tespit edilir. Beden detayları (sizes) `<pz-variant-option>` etiketlerindeki `selectable` özelliği kontrol edilerek çekilir (2026-07 güncellemesi). pz-price, .product-price içinde min/max fiyat (güncel/eski), .product-item__offers sepet indirimi, JSON-LD fallback (+>15000/10 bug düzeltmesi), pz-variant key=integration_beden beden/stok (selectable attr), SKU. Arama: /list/?search_text={q}, ürün pattern /urun/
- Generic JSON-LD motoru: 20+ mağaza (Sportive, Barçın, Korayspor, FLO, SuperStep, SneaksUp, Yalıspor, Boyner, Decathlon, SPX, Kutupayısı, Trendyol, HB, n11, Amazon TR, marka siteleri). JSON-LD → meta → CSS selector öncelik sırası
- Bot koruması: Trendyol/HB/n11/Korayspor/Decathlon/Yalıspor 403 veriyor — arama sonuçlarında "blocked" olarak dürüstçe gösteriliyor
- Sportive/FLO/Barçın vb. arama sayfaları JS-rendered → statik aramada sonuç yok (bilinen kısıt)

## Alarm Karar Motoru (services.py: evaluate_product_rules)
fiyat ≤ hedef + istenen beden stokta + cooldown dışında → alarm + Telegram
Spektrum modu: koşulu sağlayan en ucuz listing bildirilir. Telegram mesajında "bildirim anında stokta görünüyordu".

## Yapılanlar (2026-06 / oturum 2 — v1.1)
- [x] AI Buy Advisor: insights.py (compute_price_insight: min7/30/90g, avg30, is_near_lowest; compute_buy_decision: fiyat 0-40 + stok 0-20 + profil 0-25 + güven 0-15; kararlar AL/ALINABİLİR/BEKLE/SADECE ÇOK UCUZSA/UYGUN DEĞİL/BELİRSİZ). GET /api/products/{id}/buy-advice. Ürün detayında BuyAdviceCard (skor barları + gerekçe/risk). Telegram alarm mesajına AI Yorumu + alert.ai_decision/ai_score/ai_comment
- [x] Arama zenginleştirme: top 8 sonuç için ürün sayfası taranıp price/old_price/image/sizes_in_stock ekleniyor (_enrich_results). UI kartlarında önizleme resmi + fiyat + stoktaki numara rozetleri
- [x] Playwright arama motoru (browser_search.py, chromium /pw-browsers, PLAYWRIGHT_BROWSERS_PATH backend/.env'de): Sportive/Barçın/FLO/SuperStep/SPX/Kutupayısı js_search=True. FLO captcha tespiti → 'blocked'. Barçın motoru çalışıyor (alakalı sorguda sonuç veriyor); Sportive/SuperStep/SPX/Kutupayısı DOM'a ürün koymuyor → dürüstçe 0 sonuç
- [x] Generic motora gömülü JSON fiyat okuma (__NEXT_DATA__, sellingPrice regex fallback)
- [x] Testing agent 2. tur: 23/23 backend + frontend %100

## Yapılanlar (2026-06 / ilk oturum)
- [x] Tam MVP: ürün/link takibi, fiyat geçmişi, beden bazlı stok, kurallar, alarm motoru, Telegram (test edildi, gerçek mesaj gitti), toplu kontrol, scheduler, AI Koç (SSE streaming), AI Arama (zero-link, Intersport'tan gerçek sonuçlar), Debug Lab, Profil, Ayarlar
- [x] Gerçek E2E doğrulama: Brooks Glycerin 22 (5399 TL, beden 45/45.5 stokta) — doğru alarm ✓, sahte alarm engelleme ✓ (beden 44), cooldown ✓
- [x] Testing agent: backend 19/19, frontend %100 (test dosyası: /app/backend/tests/test_shoehunter.py, regression: pytest -m 'not slow')
- [x] Duplicate URL kontrolü /track/quick'e eklendi
- [x] "İhtiyaç → öneri → takip" akışı: AI Koç yanıt sonuna [MODELLER]: satırı ekler (system prompt), frontend chip olarak gösterir, tıklanınca /ai-arama?q= ile otomatik arama başlar (AICoach.jsx splitModels, AISearch.jsx useSearchParams). E2E doğrulandı: chip → arama → Intersport 6 sonuç → Takibe Al.

## Backlog (öncelikli)
- P1: Sportive/SuperStep/SPX/Kutupayısı için site-özel XHR/API keşfi (Playwright DOM'da ürün yok; Segmentify vb. arama API'leri incelenmeli)
- P1: Ürün ailesi (ProductFamily) — aynı modelin renklerini gruplama (Spektrum modunun tam sürümü); GTS/non-GTS ayrımı
- P1: Marketplace detay parser (Trendyol/HB ürün linki ile embedded JSON okuma — arama engelli ama detay sayfaları denenebilir)
- P2: _enrich_results hafifletme (sadece meta+JSON-LD çek), server.py router modülerizasyonu
- P2: Fiyat geçmişi grafiğinde mağaza bazlı çoklu çizgi
- P2: AI Koç önerilerinden tek tıkla AI Arama'ya geçiş
- P2: Backup/Export sayfası, CheckRun detay görünümü
- P3: OmniHunter genişlemesi (ayakkabı dışı kategoriler), çoklu kullanıcı/SaaS

## Notlar
- Seed veri: 1 ürün (Brooks Glycerin 22 Siyah, Intersport), 2 kural, 1 alarm
- Telegram testleri gerçek kullanıcıya gider — spam yapma
- Eski Flask kodu /app kökünde duruyor (app.py, stores/, services/...) — çalışan sistem /app/backend + /app/frontend
