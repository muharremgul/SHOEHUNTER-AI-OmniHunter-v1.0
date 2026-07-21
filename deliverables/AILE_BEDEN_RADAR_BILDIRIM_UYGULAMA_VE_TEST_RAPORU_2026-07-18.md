# Aile, Beden, Ürün Radarı ve Akıllı Bildirimler Uygulama/Test Raporu

**Proje:** ShoeHunter AI  
**Rapor tarihi:** 18 Temmuz 2026  
**Kapsam:** Aile bireyleri için çoklu beden takibi, ayakkabı dışındaki ürün sınıfları, Radar/link/AI kaynak birliği, yeni bildirim sınıfları, %3 fiyat düşüşü, altı saatlik Radar keşfi ve ürün ekranındaki takip işaretleri.

## 1. Yönetici özeti

İstenen yapı uygulanmıştır. Sistem artık bir aile bireyi için birden fazla ayakkabı numarasını, farklı aile bireylerini ve ayakkabı dışındaki üst giyim, pantolon ve dış giyim bedenlerini ayrı profiller halinde saklayabilir. Ürün Radarı oluşturulurken bu profiller seçilebilir; seçilen kişilerin ilgili ürün sınıfındaki bedenleri Radar sorgusuna birleştirilir.

Bildirim altyapısı yalnızca Radar tarafından bulunan ürünlerle sınırlı değildir. Ürün linkiyle eklenen, AI aramasıyla eklenen ve Radar keşfiyle bulunan ürünler aynı fiyat/stok değerlendirme katmanından geçirilir. Ürün veya mağaza bedeni güvenilir biçimde sağlayabiliyorsa bildirimde beden/numara gösterilir; beden doğrulanamıyorsa sistem tahmin üretmek yerine **Doğrulanamadı** bilgisini kullanır.

Ürün listesi ve ürün ayrıntısı ekranlarında ürün sınıfı ile takip kaynağı gösterilir. Radar üzerinden izlenen ürünlerde ayrıca belirgin **RADAR İLE TAKİPTE** işareti ve bağlı Radar sayısı bulunur. Böylece tek ürün altında onlarca mağaza bağlantısı olsa bile ürünün Radar kökenli olduğu anlaşılır.

Tüm otomatik backend testleri, frontend bileşen testleri ve üretim derlemesi başarılıdır. Uygulama yerel olarak çalıştırılmış, API ve arayüz sağlık kontrolleri `200 OK` vermiş, giriş ekranı gerçek tarayıcıda görsel olarak doğrulanmıştır.

## 2. Uygulanan bildirim sınıfları

| Kullanıcıya görünen sınıf | Sistem olayı | Tetikleme koşulu | Beden/numara davranışı | Tekrar aralığı |
| --- | --- | --- | --- | --- |
| Son beden fırsatı | `last_size_deal` | Yalnızca bir beden/numara mevcut ve görünür bir indirim kanıtı var | Radar varsa takip edilen bedenle eşleşir; link/AI ürününde mevcut tek beden yazılır | 12 saat |
| Bedenin yeniden stokta | `size_restock` | Stok yoktan vara döner veya daha önce kapalı olan beden açılır | İlgili beden ve aile profili yazılır | 6 saat |
| Düşük fiyattan yeniden stokta | `discounted_restock` | Beden geri gelirken fiyat önceki/geçerli referansa göre düşüktür | Geri gelen beden ve hedef kişi yazılır | 6 saat |
| Tek renk / tek beden geri geldi | `single_variant_restock` | Stok geri gelir, yalnızca bir beden vardır ve ürün adında doğrulanmış renk bilgisi bulunur | Tek beden açıkça yazılır | 6 saat |
| Fiyat düştü, bedenin mevcut | `tracked_size_price_drop` | Fiyat gerekli eşiği aşacak şekilde düşer ve takip edilen beden stoktadır | Eşleşen beden ve aile profili yazılır | 12 saat |
| Sepette fiyat | `cart_price` | Koşulsuz ve güvenilir sepet fiyatı ilk kez veya değişerek doğrulanır | Varsa beden bağlamı korunur | 12 saat |
| Sepette fiyat devam ediyor | `cart_price_continues` | Aynı koşulsuz sepet fiyatı sonraki kontrolde de geçerlidir | Mevcut beden bağlamı kullanılır | 24 saat |
| Stok kritik | `critical_stock` | Önceki ölçüme göre envanter sinyali azalır ve 1 veya 2 seviyesine iner | Takip edilen/mevcut bedenler yazılır | 12 saat |
| Hedef fiyat | `target_price` | Kullanıcının ürün/mağaza kuralındaki hedef fiyat sağlanır | Uygun olduğunda beden bağlamı eklenir | 24 saat |
| Hedefe yakın | `near_target` | Ürün tanımlı hedef fiyata yaklaşır | Uygun olduğunda beden bağlamı eklenir | 24 saat |
| Dönem dibi | `period_low` | Güncel fiyat 30 veya 90 günlük doğrulanmış düşük seviyededir | Uygun olduğunda beden bağlamı eklenir | 24 saat |

### 2.1 Son beden fırsatı ile kritik stok arasındaki fark

Bu iki olay bilerek ayrılmıştır:

- **Son beden fırsatı**, yalnızca bir beden kaldığını ve ayrıca görünür bir fiyat avantajı bulunduğunu kanıtlar.
- **Stok kritik**, mağazanın verdiği adet veya beden sayısı sinyalinin önceki kontrole göre azalıp 1–2 seviyesine indiğini gösterir; indirim bulunması şart değildir.

Bu ayrım, “tek beden kaldı” ile “stok azaldı” bilgisinin aynı alarm gibi değerlendirilmesini engeller.

### 2.2 Tek renk/tek beden geri geldi kanıtı

Bu bildirim yalnızca tek beden bulunduğu için üretilmez. Yanlış renk iddiasını önlemek için ürün adından güvenilir bir renk belirteci de çıkarılmalıdır. Renk kanıtı yoksa daha genel **Beden yeniden stokta** bildirimi kullanılır.

### 2.3 Sepette fiyat devam ediyor kanıtı

Bu sınıf yalnızca koşulsuz ve sayısal sepet fiyatında çalışır. Üyelik, kupon, banka/kart, uygulamaya özel veya kişiye özel kampanya açıkça koşul içeriyorsa bu fiyat “kesin genel sepet fiyatı” sayılmaz. Aynı doğrulanmış sepet fiyatı sonraki kontrolde değişmeden bulunursa devam bildirimi oluşturulur; sürekli mesaj yağmurunu önlemek için 24 saatlik bekleme uygulanır.

## 3. Yüzde 3 fiyat düşüşü davranışı

Genel fiyat düşüşü eşiği **%3** olarak uygulanmıştır.

- Radar kaydında kullanıcı özel bir yüzde veya tutar eşiği vermediyse, önceki geçerli fiyata göre en az %3 düşüş alarm üretmeye adaydır.
- Kullanıcı özel yüzde eşiği girdiyse özel eşik önceliklidir.
- Kullanıcı yalnızca parasal düşüş tutarı girdiyse sistem ayrıca %3 şartı dayatmaz; tanımlanan tutar kuralını uygular.
- Takip edilen beden aynı anda stoktaysa genel fiyat alarmı yerine daha anlamlı **Fiyat düştü, bedenin mevcut** sınıfı kullanılır.
- Radar kaydı bulunmayan link/AI ürünleri için de genel %3 düşüş değerlendirmesi yapılır.

Bu yapı, küçük fiyat oynaklıklarının gereksiz alarm üretmesini azaltırken kullanıcı kuralının genel varsayılanı ezmesine izin verir.

## 4. Altı saatlik Ürün Radarı

Yeni Radar kayıtlarının keşif sıklığı varsayılan olarak **6 saat** yapılmıştır. Eski kurulumlarda boş, tanımsız veya eski 12 saatlik varsayılanı kullanan Radar kayıtları veritabanı yükseltmesi sırasında 6 saate taşınır.

Önemli operasyon ayrımı:

- **Radar keşfi:** Yeni mağaza bağlantıları ve yeni varyant adayları için varsayılan 6 saatte bir çalışır.
- **Mevcut ilan kontrolü:** Fiyat/stok kontrol zamanlayıcısının ayrı aralığı vardır; mevcut yerel ayarda 30 dakikadır.
- Otomatik çalışma için Ayarlar ekranında zamanlayıcının etkin olması gerekir. Zamanlayıcı kapalıysa 6 saat değeri kayıtlı kalır ancak kendiliğinden tarama başlatmaz.

## 5. Kural yakalama

Kural motoru korunmuş ve yeni kaynak yapısıyla uyumlu bırakılmıştır.

- Ürün bazlı hedef fiyat kuralları bütün aktif mağaza ilanlarında değerlendirilir.
- Kural, ürün Radar’dan, doğrudan linkten veya AI aramasından gelmiş olsa da aynı ürün/ilan üzerinde çalışır.
- Yeni kural oluşturulduğunda mevcut ilanlar beklemeden değerlendirilir.
- Sonraki fiyat/stok kontrollerinde kurallar tekrar uygulanır.
- Mağaza fiyatı veya stok verisi güvenilir biçimde çıkarılamadıysa kural “yakalandı” sayılmaz; yanlış pozitif üretmek yerine kanıt bekler.

## 6. Aile ve çoklu beden modeli

Profil ekranı aşağıdaki yapıyı destekler:

1. Birden fazla aile bireyi oluşturma.
2. Aynı kişi için birden fazla ayakkabı numarası kaydetme; örneğin `42` ve `43`.
3. Kişi başına ürün sınıfına göre ayrı beden listeleri tutma.
4. Radar oluştururken bir veya birden fazla aile bireyini seçme.
5. Seçili kişilerin ilgili ürün sınıfındaki bedenlerini birleştirerek mağaza sonuçlarıyla eşleştirme.

Desteklenen ürün sınıfları:

| Sistem sınıfı | Arayüz etiketi | Örnek bedenler |
| --- | --- | --- |
| `shoes` | Ayakkabı | 38, 39, 42, 42.5, 43 |
| `tops` | Üst giyim | XS, S, M, L, XL |
| `pants` | Pantolon | 30, 32, 34 veya W32/L32 |
| `outerwear` | Dış giyim | S, M, L, XL |

Ürün adı açık bir sınıf işareti içeriyorsa sınıf otomatik tahmin edilir. Manuel ekleme ekranında kullanıcı sınıfı doğrudan seçebilir. Belirsiz durumda sistem eski veya tahmini bir bedeni kesin bilgi gibi kullanmaz.

## 7. Radar, link ve AI kaynak birliği

Ürünlerde takip kaynağı metadata olarak tutulur:

- `radar`: Ürün Radarı keşfi veya aktif Radar kaydı.
- `link`: Kullanıcının doğrudan ürün bağlantısıyla eklemesi.
- `ai_search`: AI arama ekranından takibe alma.
- `manual`: Manuel ürün kaydı.
- `legacy`: Eski, kaynak alanı bulunmayan kayıt.

Aynı ürün birden fazla kanaldan eklenmişse kaynaklar birleştirilir; mevcut kazanımlar silinmez. Örneğin önceden linkle eklenmiş ürün daha sonra Radar ile eşleşirse ürün hem **Link** hem **Radar** kaynağını gösterir.

Aktif Radar kayıtları ürün listesi çağrısında ayrıca sayılır. Ürünün kendi metadata alanı eski olsa bile aktif Radar ilişkisi bulunursa arayüzde Radar işareti gösterilir.

## 8. Ürün ekranındaki yeni görünür bilgiler

### 8.1 Ürün listesi

Her ürün kartında:

- ürün sınıfı,
- takip kaynakları,
- bağlı Radar sayısı,
- bağlı mağaza linki/ilan sayısı,
- Radar ilişkisi varsa belirgin **RADAR İLE TAKİPTE** işareti

gösterilir.

### 8.2 Ürün ayrıntısı

Ürün ayrıntısında aynı sınıf ve kaynak bilgileri korunur. Aktif Radar sayısı **RADAR İLE TAKİPTE · N Radar** biçiminde görünür. Ürünün altındaki mağaza bağlantıları mevcut yapıda kalır; sınıflandırma bu bağlantıların yerine geçmez.

## 9. Bildirim mesajında beden ve kişi bilgisi

Bildirim üretildiğinde sistem şu sırayı izler:

1. Radar/aile profili varsa takip edilen bedenlerle mevcut mağaza bedenlerini eşleştirir.
2. Eşleşen kişi veya kişiler mesajın hedef kitlesine eklenir.
3. Radar profili yoksa mağazadan doğrulanan mevcut/geri gelen beden kullanılır.
4. Mağaza beden verisi sunmuyorsa **Doğrulanamadı** yazılır.

Bu nedenle link ve AI ürünleri de yeni bildirim sınıflarından yararlanır; ancak aileye özel “kimin bedeni” bilgisi için ürünün bir aile profiline/Radar kaydına bağlanması gerekir.

## 10. Değişikliklerin teknik yerleri

| Dosya | Başlıca değişiklik |
| --- | --- |
| `backend/size_profiles.py` | Ürün sınıfı çıkarımı, aile/beden yardımcıları |
| `backend/services.py` | %3 fiyat düşüşü, yeni stok/beden/sepet bildirimleri, link/AI genel değerlendirmesi |
| `backend/alerting.py` | Yeni alarm sınıfları ve tekrar bekleme süreleri |
| `backend/server.py` | Takip kaynağı, ürün sınıfı, Radar sayısı ve API çıktıları |
| `backend/discovery_service.py` | Radar ürünlerinde sınıf/kaynak metadata’sı ve 6 saat varsayılanı |
| `backend/database_setup.py` | Eski 12 saatlik varsayılanların 6 saate yükseltilmesi |
| `frontend/src/pages/Profile.jsx` | Aile bireyi ve çoklu ürün sınıfı bedeni yönetimi |
| `frontend/src/pages/ProductRadar.jsx` | Aile profili seçimi, birleştirilmiş bedenler, 6 saat varsayılanı |
| `frontend/src/pages/Products.jsx` | Sınıf, kaynak ve Radar işareti |
| `frontend/src/pages/ProductDetail.jsx` | Ayrıntıda sınıf/kaynak/Radar sayısı |
| `frontend/src/pages/Alerts.jsx` | Yeni bildirim sınıfı etiketleri ve beden gösterimi |

## 11. Test ve doğrulama sonuçları

| Kontrol | Sonuç |
| --- | --- |
| Backend tam test paketi | **136 başarılı, 1 atlandı** |
| Yeni bildirim/aile odaklı backend testleri | **14 başarılı** |
| Frontend test paketleri | **5 paket, 14 test başarılı** |
| Üretim derlemesi | **Başarılı** |
| JavaScript üretim paketi | `main.c4e6c545.js`, gzip 242.59 kB |
| CSS üretim paketi | `main.3426b1e5.css`, gzip 5.73 kB |
| API sağlık kontrolü | **200 OK**, veritabanı bağlı |
| Arayüz sağlık kontrolü | **200 OK** |
| Gerçek tarayıcı kontrolü | ShoeHunter yönetici giriş ekranı düzgün görüntülendi |

Testlerde özellikle şu senaryolar kapsanmıştır:

- Tam %3 fiyat düşüşünde takip edilen beden alarmı.
- İndirimli bedenin yeniden stokta görünmesi.
- Yalnız bir renk/beden varyantının geri gelmesi.
- Aynı sepet fiyatının sonraki kontrolde devam etmesi.
- Linkle eklenen ürünün stok sinyalinin kritik seviyeye düşmesi.
- Radar ürününde ürün sınıfı, Radar kaynağı ve Radar sayısı.
- Manuel ürünün sınıf ve takip kaynağı çıktısı.
- Ürün kartı sınıflandırma yardımcılarının frontend davranışı.

## 12. Kanıt sınırları ve operasyonel notlar

1. **Mağaza verisi belirleyicidir.** Beden, renk, stok adedi veya sepet fiyatı mağaza sayfasında güvenilir biçimde yoksa sistem bu alanı kesinmiş gibi üretmez.
2. **Sepette fiyat mağaza bazlıdır.** Bir mağazada çalışan kanıt, başka mağazaya otomatik genellenmez. Ayrıntılı mağaza kanıt durumu ayrı sepet fiyatı raporlarında tutulur.
3. **Son beden her zaman ucuz değildir.** Bildirim ancak tek beden ile görünür indirim kanıtı birlikteyse “Son beden fırsatı” adını alır.
4. **Altı saat varsayılandır.** Mağaza erişim sorunları, devre kesici, iş kuyruğu veya zamanlayıcının kapalı olması gerçek çalışma zamanını geciktirebilir.
5. **Erişim korumaları aşılmaz.** CAPTCHA çözme, kimlik sahteciliği, stealth parmak izi, konut proxy rotasyonu veya mağaza erişim kontrolünü atlatma uygulanmamıştır. Bu sınır veri doğruluğunu ve hesabın/altyapının güvenliğini korur.
6. **Canlı ana akım pazar yerleri değişkendir.** Trendyol, Hepsiburada, N11 ve Amazon gibi sitelerde HTML/API sözleşmeleri değişebilir; motor sağlık ve kanıt sinyalleri izlenmeye devam edilmelidir.

## 13. Sonuç

Kullanıcının temel çıkarımı teknik yapıya dönüştürülmüştür: fayda yalnızca “ürün ucuzladı” bilgisinden değil, **doğru kişinin doğru bedeninin doğru anda mevcut olması** bilgisinden doğar. Yeni sistem fiyat, stok, beden, aile profili, takip kaynağı ve Radar ilişkisini aynı alarm bağlamında birleştirmektedir.

Uygulama şu anda yerel olarak çalışır durumdadır:

- Arayüz: `http://localhost:3000`
- API: `http://127.0.0.1:8000`

Yönetici parolası otomatik doldurulmamış; giriş ekranı kullanıcıya açık bırakılmıştır.
