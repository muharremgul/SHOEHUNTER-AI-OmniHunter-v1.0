# `D:\urun_ayakkabi` Karşılaştırmalı Proje Denetim Raporu

**Rapor tarihi:** 14 Temmuz 2026  
**Orijinal proje:** `C:\Users\ÖGR1\Documents\Ayakkabi`  
**İncelenen aday proje:** `D:\urun_ayakkabi`  
**Denetim türü:** Salt okunur kod, yapı, Git durumu ve sınırlı test denetimi  
**Kod değişikliği:** Yapılmadı

---

## 1. Yönetici özeti

`D:\urun_ayakkabi`, orijinal ShoeHunter/Ayakkabı projesinin daha yeni fikirler ve deneysel geliştirmeler içeren bir çalışma kopyasıdır. Özellikle Adidas ürün ayrıştırması, süresi dolmuş kuyruk işlerinin yeniden alınması, mağaza sağlık görünümü ve Telegram üzerinden alarm geri bildirimi alanlarında yenilikler bulunmaktadır.

Ancak aday proje mevcut haliyle bütünüyle orijinal projenin üzerine kopyalanmaya veya doğrudan üretime alınmaya hazır değildir. Faydalı geliştirmelerin yanında aşağıdaki önemli sorunlar tespit edilmiştir:

1. Düşük güvenli fiyat düşüşü akışında çalışma zamanı hatasına yol açabilecek tanımsız değişken kullanımı vardır.
2. Yeni Trendyol motorunun ürün URL deseni, yaygın gerçek Trendyol ürün adreslerini reddetmektedir.
3. Sunucu başlangıcında bütün çalışan kuyruk işlerinin sıfırlanması, çoklu worker ortamında aynı işin iki kez çalışmasına neden olabilir.
4. Telegram geri bildirim özelliğinde webhook kurulum ve doğrulama katmanı eksiktir.
5. Mağaza sağlık paneli farklı zaman aralıklarına ait metrikleri karıştırmakta ve devre kesici durumunu yanlış okuyabilmektedir.
6. Yeni özelliklerin önemli bölümü için kalıcı ve proje içine alınmış test kapsamı bulunmamaktadır.

**Genel karar:** Aday proje tamamen birleştirilmemelidir. İyileştirmeler küçük, bağımsız değişiklik paketleri halinde; testleri eklenerek ve aşağıdaki hatalar giderilerek seçici biçimde aktarılmalıdır.

---

## 2. Denetimin amacı ve kapsamı

Bu denetimin amacı, `D:\urun_ayakkabi` klasöründeki projenin orijinal projeye göre:

- yeni özelliklerini,
- değiştirilmiş davranışlarını,
- gerçekten iyileştirilmiş alanlarını,
- olası gerilemelerini,
- güvenlik ve işletim risklerini,
- test ve teslimata hazırlık durumunu

tespit etmektir.

Denetim sırasında hiçbir kaynak kod, yapılandırma, bağımlılık veya Git kaydı değiştirilmemiştir. İnceleme; dosya karşılaştırması, Git çalışma ağacı kontrolü, sözdizimi doğrulaması, seçili testlerin çalıştırılması ve kritik kod yollarının doğrudan incelenmesiyle gerçekleştirilmiştir.

Canlı internet mağazalarına karşı kapsamlı yük veya kazıma testi yapılmamıştır. Bu nedenle üçüncü taraf mağazaların güncel HTML yapılarıyla ilgili değerlendirmeler, yerel kod davranışı ve aday projede bulunan kanıt paketleriyle sınırlıdır.

---

## 3. Proje kökeni ve Git durumu

### 3.1 Orijinal proje

Orijinal çalışma ağacının son görülen Git başlığı:

- Commit: `712f3007f82bb0124cd4e1032296eb4f233dd5fa`
- Açıklama: `v1.1 motor ve AI arama duzeltmeleri`
- Tarih: 8 Temmuz 2026

Orijinal proje de çok sayıda commit edilmemiş geliştirme içermektedir. Bu nedenle karşılaştırma yalnızca iki Git commit'i arasında değil, iki klasörün mevcut çalışma ağacı durumları arasında yapılmıştır.

### 3.2 Aday proje

Aday projenin Git başlığı:

- Commit: `ebb4378f851bf4e5d351e322731757376238b139`
- Dal: `master`
- Açıklama: `İlk kurulum (Temiz v1.1 tabanlı)`
- Tarih: 13 Temmuz 2026

Aday projedeki esas yeniliklerin büyük bölümü commit edilmemiş durumdadır. Değişmiş veya yeni görülen başlıca ürün dosyaları şunlardır:

- `backend/browser_runtime.py`
- `backend/engines.py`
- `backend/job_queue.py`
- `backend/security.py`
- `backend/server.py`
- `backend/services.py`
- `backend/stores/adidas.py`
- `backend/stores/trendyol.py` — yeni
- `frontend/src/pages/Alerts.jsx`
- `frontend/src/pages/Dashboard.jsx`
- `frontend/package-lock.json`

Ayrıca aşağıdaki tanılama yardımcıları eklenmiştir:

- `backend/audit_test.py`
- `backend/check_db.py`
- `backend/check_queue.py`
- `backend/cleanup_sessions.py`
- `syntax_check.py`

Birçok tek kullanımlık ağ ve mağaza test betiği ise silinmiş görünmektedir. Bunlar arasında `fetch_is.py`, `fetch_pw.py`, `test_adidas_pw.py`, `test_api_client.py`, `test_price.py` ve çeşitli Intersport test betikleri bulunmaktadır.

### 3.3 Çalışma ağacı temizliği

`D:\urun_ayakkabi\Yeni klasör` altında raporlar, ZIP dosyaları, kaynak kopyaları, geçmiş sürümler ve kanıt çıktıları yer almaktadır. Bunlar araştırma ve devir teslim açısından yararlı olsa da ürün deposunun kökünde tutulmaları uygun değildir. Kaynak depoya alınacaklarsa ayrı bir `docs/research` veya dış arşiv alanında düzenlenmeleri önerilir.

---

## 4. Doğrulama ve test sonuçları

### 4.1 Sözdizimi doğrulaması

Aday projenin kendi `syntax_check.py` betiğiyle aşağıdaki dosyalar Python AST düzeyinde başarıyla ayrıştırılmıştır:

- `backend/engines.py`
- `backend/stores/trendyol.py`
- `backend/stores/adidas.py`
- `backend/services.py`
- `backend/server.py`
- `backend/browser_runtime.py`

Sonuç: **6/6 sözdizimi başarılı.**

Bu kontrol yalnızca Python sözdiziminin geçerli olduğunu gösterir; çalışma zamanı, veri modeli, güvenlik ve iş mantığı doğruluğunu garanti etmez.

### 4.2 Seçili testler

Orijinal projenin çalışan Python ortamı kullanılarak aday proje üzerinde şu test dosyaları çalıştırılmıştır:

- `backend/tests/test_store_engine_parsers.py`
- `backend/tests/test_job_queue.py`
- `backend/tests/test_runtime_regressions.py`

Sonuç:

- **29 test geçti**
- **0 test başarısız**
- Starlette tarafında bir `PendingDeprecationWarning` görüldü

Test sonrasında aday projenin Git durumunda yeni bir değişiklik oluşmadığı kontrol edilmiştir.

### 4.3 Test kapsamındaki boşluklar

29 testin geçmesi olumlu olmakla birlikte yeni özelliklerin tamamını doğrulamamaktadır. Aşağıdaki yeni davranışlar mevcut kalıcı testlerle yeterince kapsanmamaktadır:

- Düşük güven seviyeli fiyat düşüşü alarmının atlanması
- Telegram geri bildirim butonları ve callback akışı
- Telegram webhook kimlik doğrulaması
- Mağaza sağlık endpoint'i ile Dashboard alan eşleşmesi
- Devre kesici durumunun arayüzde gösterilmesi
- Gerçek biçimli Trendyol ürün URL'lerinin tanınması
- Trendyol `__NEXT_DATA__` ürün, varyant ve satıcı ayrıştırması
- Sunucu yeniden başlatıldığında aktif ve süresi dolmuş işlerin ayrımı
- Çoklu worker ortamında aynı işin iki kez alınmaması

Aday projedeki Adidas raporu beş yeni testin daha önce başarıyla çalıştırıldığını belirtmektedir. İlgili `test_adidas_schema_robustness.py` dosyası `Yeni klasör\files_extracted` altında bulunmaktadır; fakat aktif `backend/tests` dizinine entegre edilmemiştir. Dolayısıyla bu testler normal proje test paketiyle otomatik olarak çalışmamaktadır.

### 4.4 Aday sanal ortamı

`D:\urun_ayakkabi\backend\.venv` klasörü mevcut olmasına rağmen bu ortamda `bs4` ve `pytest` kurulu değildir. Bu nedenle aday klasör, görünen `.venv` varlığına rağmen kendi başına tekrarlanabilir ve hazır bir geliştirme ortamı sağlamamaktadır.

---

## 5. Ayrıntılı iyileştirme analizi

## 5.1 Adidas ayrıştırıcısı

### Önceki davranış

Orijinal Adidas ayrıştırıcısı yalnızca kök seviyede doğrudan `@type: ProductGroup` olan JSON-LD sözlüklerini işleyebiliyordu. Adidas veriyi liste, `@graph`, `mainEntity` veya başka bir iç içe yapı içinde sunduğunda ürün verisi bulunamayabiliyordu.

### Yeni davranış

`backend/stores/adidas.py` içinde aşağıdaki geliştirmeler yapılmıştır:

#### A. İç içe JSON-LD taraması

Yeni `_find_product_nodes()` fonksiyonu:

- kök sözlük,
- üst seviye liste,
- `@graph`,
- `mainEntity`,
- `item`,
- `product`

yapılarını belirli bir derinlik sınırıyla taramaktadır.

`ProductGroup` düğümleri, tekil `Product` düğümlerine tercih edilmektedir. Bu doğru bir tercihtir; `ProductGroup` çoğunlukla beden ve varyant açısından daha zengin veri sunar.

#### B. Tekil Product yedeği

`ProductGroup` bulunamadığında `offers` alanı bulunan tekil bir `Product` kullanılabilmektedir. Bu yolda:

- fiyat okunur,
- varsa genel stok durumu okunur,
- beden bilgisi uydurulmaz,
- güven değeri `0.6` olarak düşürülür,
- fiyat kaynağı ayrı biçimde işaretlenir.

Bu, veri kalitesi ile kullanılabilirlik arasında makul bir denge kurmaktadır.

#### C. DOM fiyat yedeği

JSON-LD bulunmadığında görünür fiyat etiketlerinden fiyat okuma desteği eklenmiştir. Sonuç:

- `confidence = 0.55`
- `price_source = dom_text:adidas_price_label`

olarak işaretlenmektedir. Beden ve stok verisi üretilmemektedir.

Bu yaklaşım, zayıf veriyi doğrulanmış veri gibi göstermediği için tasarım olarak olumludur. Ancak düşük güvenli fiyatların alarm ve fiyat geçmişi sistemine nasıl gireceği açık kurallarla test edilmelidir.

#### D. Hedefli tarayıcı beklemesi

`browser_runtime.py` içindeki `BrowserPool.fetch()` metoduna isteğe bağlı `browser_wait_selector` parametresi eklenmiştir. Adidas motoru için şu seçicilerden birinin oluşması en fazla beş saniye beklenmektedir:

- JSON-LD script etiketi
- fiyatla ilişkili `data-testid`
- `gl-price` sınıfı

Bu özellik motor bazında etkinleştirildiği için diğer mağazaların varsayılan davranışını değiştirmemektedir.

### Değerlendirme

Adidas değişiklikleri aday projenin en güçlü ve en somut iyileştirmesidir. Yine de şu koşullarla aktarılmalıdır:

1. `test_adidas_schema_robustness.py` aktif test dizinine alınmalı.
2. DOM fiyat yedeğinin yanlış eski fiyat veya başka ürün kartı fiyatı seçmediği doğrulanmalı.
3. Düşük güvenli fiyatlar için alarm ve fiyat geçmişi politikası düzeltilip test edilmeli.
4. Canlı sayfa doğrulaması, izin verilen düşük frekanslı yöntemle ayrıca yapılmalı.

---

## 5.2 HTTP karakter kodlaması

`backend/engines.py`, HTTP yanıtını önce UTF-8 olarak çözmeyi; bu başarısız olursa sunucunun bildirdiği karakter setine dönmeyi denemektedir.

Bu değişiklik, Türkçe sitelerin yanlış veya eksik charset bildirdiği durumlarda bozuk karakterleri azaltabilir. Bununla birlikte gerçekten ISO-8859-9 veya Windows-1254 döndüren sayfalarda UTF-8 denemesi zaten hata vereceği için bildirilmiş charset'e güvenli biçimde geri dönülmektedir.

**Değerlendirme:** Küçük fakat mantıklı bir dayanıklılık iyileştirmesi.

---

## 5.3 İş kuyruğu ve çökme sonrası toparlanma

`backend/job_queue.py` içindeki `claim_job()` artık iki tür işi alabilmektedir:

1. `pending` durumundaki işler
2. `running` durumda olup `lease_until` süresi dolmuş işler

Bu, worker çöktüğünde işin sonsuza kadar `running` durumunda kalmasını önleyen doğru bir lease kurtarma davranışıdır.

Ancak `backend/server.py` başlangıç akışında ayrıca bütün `running` işler koşulsuz biçimde `pending` yapılmaktadır. Bu iki yaklaşım birlikte değerlendirildiğinde:

- `claim_job()` içindeki süresi dolmuş lease kurtarması doğru ve yeterlidir.
- Sunucu başlangıcındaki toplu sıfırlama fazla geniştir.
- Başka bir sağlıklı worker tarafından hâlen yürütülen iş de yeniden kuyruğa alınabilir.
- Aynı ürün kontrolü, alarm üretimi veya yedekleme işi iki kez çalışabilir.

**Öneri:** Yalnızca `lease_until <= now` olan işler kurtarılmalı; aktif lease sahibi işler korunmalıdır. Bu davranış çoklu worker entegrasyon testiyle doğrulanmalıdır.

---

## 5.4 Düşük güvenli fiyat alarmı koruması

Yeni kod, `confidence < 0.65` olan ayrıştırma sonuçlarından otomatik fiyat düşüşü alarmı üretmemeyi amaçlamaktadır. Bu özellikle Adidas DOM fallback gibi tahmini kaynaklar için doğru bir güvenlik katmanıdır.

Ancak mevcut uygulamada `alert_targets` yalnızca yüksek güven dalında tanımlanmaktadır. Düşük güven dalı tamamlandıktan sonra kod yine `for watch in alert_targets` satırına ilerlemektedir.

Muhtemel sonuç:

```text
UnboundLocalError: local variable 'alert_targets' referenced before assignment
```

Bu hata şu koşullarda tetiklenebilir:

1. Önceki fiyat geçerlidir.
2. Yeni fiyat önceki fiyattan düşüktür.
3. Yeni verinin güven değeri `0.65` altındadır.

Bu yalnızca bildirimi atlamakla kalmayabilir; ürün kontrolünün kalan stok, sepet fiyatı ve geçmiş işlemlerini de yarıda kesebilir.

**Önem derecesi:** Kritik  
**Aktarım kararı:** Düzeltilmeden alınmamalı.

---

## 5.5 Trendyol özel mağaza motoru

Yeni `backend/stores/trendyol.py` aşağıdaki hedeflerle oluşturulmuştur:

- `__NEXT_DATA__` içinden ürün bulma
- JSON-LD fallback
- ürün fiyatı ve eski fiyat
- beden/varyant bilgisi
- genel stok durumu
- satıcı bilgisi
- arama sonuçlarının JSON veya DOM kartlarından çıkarılması
- Playwright desteği

Bu özellik seti, önceki genel `make_engine()` tanımına göre teorik olarak önemli bir ilerlemedir.

### Kritik URL deseni problemi

Yeni motorun `product_pattern` değeri şu biçimi zorunlu tutmaktadır:

```text
/p/<ürün-adı>-p-<sayısal-id>
```

Yaygın Trendyol ürün adresleri ise şu yapıdadır:

```text
/<marka>/<ürün-adı>-p-<sayısal-id>
```

Yerel doğrudan kontrolde:

```text
https://www.trendyol.com/nike/air-max-90-p-123456 -> False
https://www.trendyol.com/p/air-max-90-p-123456    -> True
```

Bu nedenle yeni motor gerçek ürün bağlantılarını ürün linki olarak kabul etmeyebilir. Arama sonuçları doğru çıkarılsa bile `is_product_link()` filtresinde elenebilir.

### Diğer Trendyol riskleri

- Yeni motor için özel fixture ve test yoktur.
- `_TRENDYOL_PRODUCT_RE` tanımlanmış fakat ürün doğrulama akışında ayrıca kullanılmamaktadır.
- `__NEXT_DATA__` alan isimleri varsayımsaldır ve gerçek HTML fixture'ıyla kanıtlanmamıştır.
- Fiyat alanı sözlük veya biçimlendirilmiş metin olduğunda `float()` başarısız olabilir.
- Satıcı ifadesindeki koşullu ifade önceliği, `brand` sözlük değilse mevcut `merchantName`/`sellerName` değerinin de kaybolmasına yol açabilir.
- Beden varyantı alanlarının gerçek Trendyol veri modeliyle eşleştiği test edilmemiştir.

**Değerlendirme:** Tasarım fikri değerlidir; mevcut uygulama üretime hazır değildir. Önce gerçek anonimleştirilmiş fixture'lar ve URL testleri eklenmelidir.

---

## 5.6 Telegram geri bildirim sistemi

Yeni sistem alarm mesajının altına üç buton eklemektedir:

- Satın aldım
- Beden yoktu
- Yanlış ürün

Butona basıldığında `feedback:<alert_id>:<code>` biçimindeki callback verisinin `/telegram/callback` endpoint'ine gelmesi ve alarm belgesinin güncellenmesi amaçlanmaktadır. Alarm ekranı da kaydedilen geri bildirimi renkli bir rozetle göstermektedir.

### Olumlu yönler

- Alarm kalitesini gerçek kullanıcı sonucuyla ilişkilendirme imkânı sağlar.
- Yanlış ürün ve beden bulunamaması gibi sorunlar ölçülebilir hale gelebilir.
- Gelecekte mağaza/parser kalite puanına girdi sağlayabilir.
- Teknik parser alarmlarının müşteriye gönderilmemesi bildirim gürültüsünü azaltır.

### Eksikler ve riskler

1. Kod tabanında Telegram `setWebhook` çağrısı bulunmamaktadır.
2. Genel erişilebilir webhook URL'si için yapılandırma veya kurulum dokümanı yoktur.
3. Telegram webhook secret token başlığı doğrulanmamaktadır.
4. Callback endpoint'i uygulamanın genel kökünde ve kimlik doğrulamasızdır.
5. `code` değeri yalnızca `bought`, `no_size`, `wrong` değerleriyle sınırlandırılmamaktadır.
6. Alarm güncellemesinin gerçekten bir belgeyi değiştirip değiştirmediği kontrol edilmemektedir.
7. Callback tekrarlarının idempotentliği ve denetim kaydı test edilmemiştir.
8. Digest modunda geri bildirim butonları kullanılmamaktadır; davranış farkı belgelenmemiştir.
9. Telegram callback testi bulunmamaktadır.

### Güvenli tamamlanma ölçütleri

- Webhook kurulumu açıkça yapılandırılmalı.
- Telegram secret header doğrulanmalı.
- İzin verilen callback kodları beyaz listeyle sınırlandırılmalı.
- Bilinmeyen alarm ID'leri için kontrollü sonuç dönülmeli.
- Tekrarlı callback güvenli olmalı.
- Entegrasyon testi eklenmeli.

**Değerlendirme:** Ürün fikri iyi; uygulama yarım ve güvenlik açısından tamamlanmamış.

---

## 5.7 Teknik alarmların müşteriden ayrılması

`parser_failure` ve `listing_missing` tipleri geliştiriciye özel kabul edilerek Telegram müşterisine gönderilmemektedir. Alarm kaydı `dev_only` durumuyla veri tabanında tutulmaktadır.

Bu, müşteri deneyimi açısından olumlu bir değişikliktir. Ancak geliştirici alarmlarının yalnızca uygulama loguna yazılması uzun vadede yeterli olmayabilir. Merkezi log, hata izleme veya ayrı teknik bildirim kanalı düşünülmelidir.

**Değerlendirme:** Koşullu olarak alınabilir; teknik alarm görünürlüğünün kaybolmaması sağlanmalıdır.

---

## 5.8 Mağaza sağlık endpoint'i ve Dashboard paneli

Dashboard'a aşağıdaki alanları gösteren yeni bir tablo eklenmiştir:

- mağaza adı
- başarı yüzdesi
- engellenen istek sayısı
- ortalama gecikme
- devre kesici durumu

Bu, operasyon ekibinin mağaza bazlı sorunları görmesi açısından önemli bir ürün iyileştirmesi olabilir.

### Tespit edilen veri uyumsuzlukları

#### A. Zaman aralığı karışıklığı

Panel başlığında “Son 24 saat” yazmaktadır. Buna rağmen başarı oranı:

```text
success_count / (success_count + failure_count)
```

ile, toplam dönem sayaçlarından hesaplanmaktadır. Ortalama gecikme ise `health_snapshot()` tarafından son 24 saatlik olaylardan hesaplanmaktadır.

Sonuç olarak aynı satırda yaşam boyu başarı oranı ile 24 saatlik gecikme yan yana gösterilmektedir.

#### B. Kullanılmayan doğru alanlar

Backend zaten:

- `success_rate_24h`
- `checks_24h`
- `blocked_rate_24h`

alanlarını üretmektedir. Frontend bunları kullanmamaktadır.

#### C. Devre kesici alanı yanlış

Sağlık verisi devre durumunu:

- `circuit_state`
- `circuit_open_until`

alanlarında tutmaktadır. Yeni endpoint ise `doc.get("circuit_open")` okumaktadır. Bu alan mevcut olmadığından devre açık olduğu halde arayüz “kapalı” gösterebilir.

#### D. Hata gizleme

Endpoint hata aldığında boş liste dönmektedir. Frontend de istek hatasını sessizce yok saymaktadır. Bu durumda kullanıcı “sağlık verisi yok” ile “sağlık sistemi bozuk” durumlarını ayıramaz.

### Değerlendirme

Panelin tasarım yönü doğru, fakat mevcut veriler operasyonel karar için güvenilir değildir. Alan eşlemesi ve zaman penceresi düzeltilmeden üretimde kullanılmamalıdır.

---

## 5.9 MongoDB saat dilimi farkındalığı

MongoDB istemcisine `tz_aware=True` eklenmiştir. Bu değişiklik, MongoDB'den gelen zamanların UTC farkındalıklı `datetime` olarak dönmesini sağlar ve naive/aware zaman karşılaştırma hatalarını azaltabilir.

Projedeki `as_utc()` benzeri uyumluluk kodları göz önünde bulundurulduğunda olumlu bir tutarlılık geliştirmesidir. Yine de tüm tarih alanlarının bazen ISO metni, bazen `datetime` olarak saklanması ayrı bir veri modeli standardizasyon konusu olarak kalmaktadır.

**Değerlendirme:** Alınması önerilen küçük ve yararlı değişiklik.

---

## 5.10 Çerez SameSite değişikliği

Oturum ve CSRF çerezleri `SameSite=Strict` yerine `SameSite=Lax` yapılmıştır.

### Olası fayda

- Dış bağlantıdan uygulamaya dönülen üst seviye GET yönlendirmelerinde oturumun korunmasını kolaylaştırabilir.
- Bazı mobil veya LAN kullanım akışlarında uyumluluğu artırabilir.

### Risk

- Çerez politikasını önceki duruma göre gevşetir.
- Bu değişikliğin gereksinimi veya hedeflenen kullanıcı akışı belgelenmemiştir.
- CSRF korumasının tüm yazma endpoint'lerinde tutarlı uygulandığını kanıtlayan yeni test yoktur.

**Değerlendirme:** Açık bir ihtiyaç ve güvenlik testi olmadan otomatik aktarılmamalıdır.

---

## 5.11 Frontend bağımlılık kilidi

`frontend/package-lock.json` içinde:

- proje sürümü `1.0.0` yerine `0.6.0` olarak düzeltilmiş,
- TypeScript `6.0.3` sürümünden `4.9.5` sürümüne düşmüştür.

Proje sürümünün `package.json` ile eşleşmesi olumlu olabilir. Ancak TypeScript sürüm düşüşünü açıklayan doğrudan bir bağımlılık değişikliği görülmemiştir. Bu muhtemelen farklı npm/Node ortamında kilit dosyasının yeniden oluşturulmasından kaynaklanmaktadır.

**Değerlendirme:** Kilit dosyası doğrudan alınmamalı; desteklenen Node/npm sürümünde temiz kurulumla yeniden üretilmeli ve frontend test/build doğrulanmalıdır.

---

## 6. Yeni yardımcı betiklerin değerlendirilmesi

### `syntax_check.py`

Seçili Python dosyalarını AST ile kontrol eden küçük ve zararsız bir yardımcıdır. Ancak dosya listesi sabit olduğu için tüm projeyi kapsamaz. CI içindeki mevcut Ruff/pytest sürecinin yerini tutmaz.

### `backend/audit_test.py`

Yerel çalışan API'ye bağlanan canlı denetim betiğidir. Sabit olarak:

- `localhost:8001/api`
- `admin`
- `Admin12345678`

değerlerini kullanmaktadır.

Bu nedenle kalıcı depo dosyası olarak uygun değildir. Parola örneği yanlış kullanım alışkanlığı yaratabilir. Ortam değişkenleri ve açık test ortamı şartlarıyla yeniden tasarlanmalıdır.

### `check_db.py`, `check_queue.py`, `cleanup_sessions.py`

Operasyonel tanılama açısından yararlı olabilirler; ancak:

- güvenli kullanım açıklaması,
- salt okunur/yazma davranışı ayrımı,
- hedef veri tabanı doğrulaması,
- üretimde kullanım koruması

belgelenmeden dağıtıma eklenmemelidir.

---

## 7. Risk kaydı

| No | Önem | Alan | Bulgu | Olası etki | Karar |
|---:|:---:|---|---|---|---|
| R-01 | Kritik | Alarm sistemi | Düşük güven dalında `alert_targets` tanımsız | Ürün kontrolü çalışma zamanı hatasıyla kesilir | Düzeltilmeden alma |
| R-02 | Kritik | Trendyol | URL deseni gerçek ürün adreslerini reddediyor | Trendyol arama/kontrol sonuçları çalışmaz | Yeniden geliştir |
| R-03 | Yüksek | İş kuyruğu | Başlangıçta tüm `running` işler sıfırlanıyor | Çoklu worker'da yinelenen işlem/alarm | Yalnız süresi dolanı kurtar |
| R-04 | Yüksek | Telegram | Webhook doğrulaması ve kurulumu yok | Özellik çalışmaz veya sahte callback kabul eder | Tamamlanmadan açma |
| R-05 | Yüksek | Sağlık paneli | Zaman pencereleri ve devre alanı yanlış | Yanlış operasyonel karar | Alanları düzelt |
| R-06 | Orta | Test | Yeni özellik testleri aktif pakette yok | Gerilemeler CI'da yakalanmaz | Testleri entegre et |
| R-07 | Orta | Bağımlılıklar | Açıklanmayan TypeScript düşüşü | Build/uyumluluk farkı | Kilidi yeniden üret |
| R-08 | Orta | Güvenlik | SameSite Strict → Lax | Çerez politikası gevşer | Gereksinimi doğrula |
| R-09 | Orta | Depo düzeni | ZIP, kopya kaynak ve kanıt dosyaları kökte | Depo şişmesi ve kaynak belirsizliği | Arşive taşı |
| R-10 | Düşük | Ortam | Aday `.venv` eksik bağımlılıklı | Kurulum tekrarlanamaz | Ortamı yeniden kur |

---

## 8. Önerilen aktarım planı

Değişiklikler tek bir toplu kopyalama yerine aşağıdaki bağımsız paketler halinde ele alınmalıdır.

### Paket 1 — Adidas dayanıklılığı

Alınabilecek dosya/alanlar:

- `backend/stores/adidas.py` içindeki JSON-LD taraması
- tekil Product fallback
- kontrollü DOM fiyat fallback
- `browser_wait_selector` desteği
- `backend/engines.py` içindeki selector aktarımı
- `backend/browser_runtime.py` içindeki isteğe bağlı bekleme

Zorunlu testler:

- kök ProductGroup
- liste içindeki ProductGroup
- `@graph` içindeki ProductGroup
- tekil Product fallback
- DOM fiyat fallback
- veri bulunamaması
- eski/yeni fiyat ayrımı
- düşük güvenli verinin alarm üretmemesi
- diğer motorlarda bekleme davranışının değişmemesi

### Paket 2 — Lease tabanlı kuyruk kurtarma

Alınabilecek değişiklik:

- `claim_job()` içinde süresi dolmuş `running` işin yeniden alınması

Alınmaması gereken bölüm:

- Başlangıçta tüm `running` kayıtların koşulsuz `pending` yapılması

Zorunlu testler:

- süresi dolmamış iş alınmaz
- süresi dolmuş iş alınır
- iki worker aynı işi alamaz
- girişim sayısı doğru artar
- lease sahibi/worker bilgisi doğru güncellenir

### Paket 3 — Teknik alarm ayrımı

- Müşteriye gönderilmeyecek teknik alarm tipleri açıkça tanımlanmalı.
- Teknik ekip için alternatif görünürlük kanalı sağlanmalı.
- Digest ve immediate modları birlikte test edilmeli.

### Paket 4 — Mağaza sağlık paneli

- Backend doğrudan normalize edilmiş 24 saatlik oranı sunmalı.
- Frontend `success_rate_24h` ve `checks_24h` kullanmalı.
- Devre durumu `circuit_state` ve `circuit_open_until` üzerinden hesaplanmalı.
- Veri yok ve sistem hatası durumları ayrılmalı.
- Panelde metrik penceresi açıkça belirtilmeli.

### Paket 5 — Telegram geri bildirimi

- Webhook kurulumu ve kaldırılması için yönetim akışı eklenmeli.
- Secret token doğrulaması yapılmalı.
- Callback kodları doğrulanmalı.
- Uçtan uca entegrasyon testi eklenmeli.
- Gizlilik ve veri saklama süresi tanımlanmalı.

### Paket 6 — Trendyol motoru

Mevcut dosya doğrudan alınmamalıdır. Önce:

1. Gerçek URL biçimleri için test matrisi hazırlanmalı.
2. Anonimleştirilmiş HTML/JSON fixture'ları eklenmeli.
3. URL deseni `/<marka>/<slug>-p-<id>` yapısını desteklemeli.
4. Fiyat veri tipleri normalize edilmeli.
5. Satıcı ifade önceliği düzeltilmeli.
6. Beden/stok verisi gerçek fixture ile doğrulanmalı.
7. Cloudflare/robot ve hız sınırı davranışı belgelenmeli.

---

## 9. Birleştirme öncesi kabul ölçütleri

Aşağıdaki koşullar sağlanmadan aday değişikliklerin üretime alınmaması önerilir:

- [ ] Kritik `alert_targets` hatası giderildi.
- [ ] Düşük güven fiyat testi eklendi.
- [ ] Gerçek Trendyol URL testi geçiyor.
- [ ] Trendyol fixture testleri eklendi.
- [ ] Aktif lease'e sahip işler başlangıçta korunuyor.
- [ ] Çoklu worker kuyruk testi geçiyor.
- [ ] Telegram webhook secret doğrulaması var.
- [ ] Telegram callback kodları beyaz listeyle doğrulanıyor.
- [ ] Mağaza sağlık paneli yalnızca 24 saatlik veriyi doğru gösteriyor.
- [ ] Açık devre durumu arayüzde doğru görünüyor.
- [ ] Adidas sağlamlık testleri aktif `backend/tests` dizininde.
- [ ] Frontend temiz bağımlılık kurulumu başarılı.
- [ ] Frontend test ve üretim build'i başarılı.
- [ ] Tüm backend test paketi başarılı.
- [ ] Yeni kod için Ruff/biçim/statik kontrol başarılı.
- [ ] `Yeni klasör` araştırma çıktıları ürün deposundan ayrıldı.
- [ ] Sabit parola içeren denetim betiği kaldırıldı veya güvenli yapılandırıldı.
- [ ] Değişiklikler anlamlı ve ayrı Git commit'lerine bölündü.

---

## 10. Dosya bazlı karar özeti

| Dosya | Değişiklik | Değerlendirme | Öneri |
|---|---|---|---|
| `backend/stores/adidas.py` | Esnek JSON-LD ve fallback zinciri | Güçlü iyileştirme | Testleriyle seçerek al |
| `backend/browser_runtime.py` | Motor bazlı seçici bekleme | Yararlı | Zaman aşımı testiyle al |
| `backend/engines.py` | UTF-8 fallback, selector aktarımı, Trendyol motoru kaydı | Kısmen iyi | Trendyol kaydını ayır |
| `backend/job_queue.py` | Süresi dolmuş running iş kurtarma | Doğru iyileştirme | Çoklu worker testiyle al |
| `backend/server.py` | tz-aware, sağlık endpoint'i, startup reset, Telegram callback | Karışık | Bölerek değerlendir |
| `backend/services.py` | Telegram feedback, teknik alarm filtresi, confidence filtresi | Fikir iyi, kritik hata var | Düzeltilmeden alma |
| `backend/stores/trendyol.py` | Yeni özel motor | Test edilmemiş ve URL hatalı | Baştan doğrula |
| `backend/security.py` | SameSite Lax | Gereksinimi belirsiz | Güvenlik kararı beklesin |
| `frontend/src/pages/Alerts.jsx` | Telegram feedback rozeti | Backend tamamlanırsa yararlı | Özellikle birlikte al |
| `frontend/src/pages/Dashboard.jsx` | Mağaza sağlık paneli | Alanları yanlış yorumluyor | Düzelterek al |
| `frontend/package-lock.json` | Sürüm eşleme ve TS düşüşü | Belirsiz | Temiz ortamda yeniden üret |
| `backend/audit_test.py` | Canlı kontrol betiği | Sabit parola içeriyor | Bu haliyle alma |
| `syntax_check.py` | Sınırlı AST kontrolü | Zararsız ama yetersiz | CI yerine kullanma |

---

## 11. Sonuç

`D:\urun_ayakkabi` projesi, orijinal projeye göre özellikle Adidas ayrıştırma dayanıklılığı ve kuyruk lease kurtarması alanlarında gerçek teknik ilerlemeler içermektedir. Mağaza sağlık görünümü ve Telegram geri bildirimi de ürün açısından değerli yönlerdir.

Bununla birlikte proje şu anda deneysel geliştirme aşamasındadır. Kritik fiyat alarmı hatası, Trendyol URL uyumsuzluğu, çoklu worker riski, tamamlanmamış Telegram güvenliği ve hatalı sağlık metriği eşlemesi sebebiyle aday klasörün tamamı güvenilir bir “iyileştirilmiş sürüm” olarak kabul edilmemelidir.

Nihai öneri:

> Aday projeyi topluca kopyalamayın. Adidas, kuyruk lease kurtarması ve teknik alarm ayrımı gibi faydalı bölümleri bağımsız değişiklik paketleri halinde; her biri için test, güvenlik kontrolü ve geri alma planı oluşturarak orijinal projeye aktarın. Trendyol, Telegram ve mağaza sağlık panelini ise mevcut haliyle değil, rapordaki kabul ölçütlerini karşılayacak şekilde tamamladıktan sonra değerlendirin.

---

## 12. Denetim notu

Bu rapor hazırlanırken uygulama kaynak kodlarında, yapılandırmalarda, bağımlılıklarda ve Git geçmişinde değişiklik yapılmamıştır. Oluşturulan tek dosya bu denetim raporudur.
