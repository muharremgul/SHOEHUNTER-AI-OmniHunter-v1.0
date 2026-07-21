# Tüm Mağazalar Sepette Fiyat Uygulama ve Doğrulama Raporu

**Proje:** ShoeHunter AI / Ayakkabı  
**Denetim ve uygulama tarihi:** 18 Temmuz 2026  
**Kapsam:** Kayıtlı 27 mağaza motorunun tamamı  
**Ana konu:** Ürün sayfasında veya sepette oluşan fiyatın bulunması, koşullarının ayrıştırılması, saklanması, alarm ve arayüz davranışı  
**Durum:** Kodlama ve otomatik testler tamamlandı; mağaza bazlı canlı kanıt durumu aşağıda ayrı ayrı verilmiştir.

---

## 1. Yönetici özeti

Bu çalışma sonunda sepette fiyat desteği motor kabiliyeti bakımından **1/27’den 27/27’ye** çıkarıldı. Buradaki 27/27 ifadesi, 27 motorun tamamının aynı güvenli sepet teklifi çözümleme katmanını çalıştırdığı anlamına gelir. Her mağazada veya her üründe aktif kampanya bulunduğu anlamına gelmez.

Uygulanan temel ayrım:

- `current_price`: ürünün normal/güncel raf fiyatıdır.
- `cart_price`: yalnızca görünür sayfada kesin tutarı bulunan ve üyelik, kod, adet, beden, uygulama veya ödeme yöntemi koşulu taşımayan sepette fiyattır.
- `campaigns`: yüzdesi görünen fakat kesin tutarı görülmeyen ya da koşullu olan tekliflerdir.
- `cart_price_conditions`: kesin fiyatın koşulsuz olup olmadığını gösterir. Koşul varsa otomatik fırsat fiyatı üretilmez.
- `cart_price_source` ve `cart_price_confidence`: fiyatın hangi görünür kanıttan ve hangi güvenle alındığını saklar.

Bu ayrım özellikle önemlidir. Örneğin:

- Boyner’de normal fiyat 22.999 TL, sepette fiyat 16.999 TL olarak ayrı tutulur.
- Trendyol’da aynı kartta 599,90 TL normal fiyat, 581,90 TL sepette fiyat ve 552,80 TL Trendyol Plus fiyatı bulunabilir. Plus fiyatı sepette fiyatla karıştırılmaz.
- Sneaks Up’taki “45 ve üzeri bedenlerde sepette %20” teklifi bütün bedenler için kesin fiyat sayılmaz.
- Columbia’daki 1/2/3 ürün basamakları ve üyelik indirimi tek ürün için koşulsuz kesin fiyat gibi kaydedilmez.

## 2. Sonuçların kısa özeti

| Sonuç sınıfı | Mağaza sayısı | Mağazalar |
|---|---:|---|
| Güncel veya yerel yakalanmış kesin sepette fiyat kanıtı | 4 | Intersport, Boyner, Trendyol, n11 |
| Güncel koşullu/yüzdesel sepet kampanyası kanıtı | 6 | Sportive, Barçın, SuperStep, Sneaks Up, ASICS, Columbia |
| Canlı kontrol edildi; test edilen sayfada güncel teklif görünmedi veya eski bağlantı yönlendi | 4 | Adidas, FLO, SPX, The North Face |
| Bu turda güncel kesin teklif kanıtı bulunamadı | 13 | Decathlon, Nike, Puma, New Balance, Korayspor, Yalı Spor, Kaptan Spor, Kutupayısı, Hepsiburada, Amazon TR, Skechers TR, Brooks Türkiye, Salomon Türkiye |

**Önemli:** Son iki sınıftaki motorlarda özellik kapalı değildir. Motor, sonraki taramalarda görünür bir “sepette” teklifi çıktığında bunu tanıyacak şekilde çalışır. Kesin fiyat kanıtı bulunmadığı için bu ürünler adına sahte bir fiyat türetilmemiştir.

## 3. Önceki 1/27 durumunun nedeni

Önceki yapıda yalnız Intersport motorunda `supports_cart_price=True` bulunuyordu. Diğer motorların çoğunda normal fiyat ve eski fiyat seçicileri vardı; ancak sepette fiyat için ortak bir sözleşme, koşul analizi veya görünür teklif dedektörü yoktu.

Ek olarak önceki Intersport davranışında sepette fiyat bulunduğunda `current_price` alanının üzerine yazılıyordu. Bu durum şu yan etkilere yol açabiliyordu:

1. Normal fiyat ile sepette fiyat birbirinden ayrı gösterilemiyordu.
2. Sepet alarmı `cart_price < current_price` karşılaştırması yaptığı için iki değer eşitleniyor ve alarm koşulu etkisiz kalabiliyordu.
3. Fiyat geçmişinde raf fiyatı ile sepet fiyatı birbirine karışabiliyordu.

Yeni yapıda Intersport kazanımı korunarak fiyatlar ayrıldı. Yerel yakalanmış Intersport HTML’i ile yapılan gerçek parser kontrolünde sonuç:

- normal fiyat: **10.999 TL**
- sepette fiyat: **8.799,20 TL**
- normal fiyat kaynağı: `shelf`
- sepette fiyat kaynağı: `intersport:.product-item__offers`
- sepette fiyat güveni: `0.95`

## 4. Yeni sepet teklifi veri sözleşmesi

Örnek koşulsuz sonuç:

```json
{
  "current_price": 3999.0,
  "cart_price": 3399.0,
  "cart_price_source": "selector:[class*='sepette']",
  "cart_price_confidence": 0.94,
  "cart_price_conditions": [],
  "campaigns": [
    {
      "type": "cart",
      "label": "Sepette 3.399 TL",
      "conditional": false,
      "conditions": [],
      "exact_price": 3399.0
    }
  ]
}
```

Örnek koşullu sonuç:

```json
{
  "current_price": 7799.0,
  "cart_price": null,
  "cart_price_conditions": [],
  "campaigns": [
    {
      "type": "cart",
      "label": "45 ve üzeri bedenlerde sepette %20 indirim",
      "conditional": true,
      "conditions": ["quantity", "size"],
      "discount_percent": 20.0
    }
  ]
}
```

Koşullu teklifte `cart_price=null` bırakılması bilinçli bir güvenlik kararıdır. Motor, kullanıcının ilgilendiği bedenin kampanyaya dahil olduğunu ve sepette hangi yuvarlama kuralının uygulandığını kanıtlamadan tutar üretmez.

## 5. Tanınan teklif türleri ve koşullar

Ortak dedektör aşağıdaki görünür biçimleri tanır:

- `Sepette 3.399 TL`
- `Sepet Fiyatı: 3.399 TL`
- `Sepetteki Son Fiyat 3.399 TL`
- Etiket ve sonuç ayrı kardeş öğelerdeyse `22.999 TL / Sepette %26 / 16.999 TL`
- `SEPETTE` etiketiyle normal ve sepet fiyatının aynı kartta gösterilmesi

Aşağıdaki koşullar görüldüğünde kesin fiyat otomatik olarak promosyon fiyatına dönüştürülmez:

- adet veya miktar: `2 ve üzerine`, `3 ürün ve üzerinde`, `3 al 2 öde`
- üyelik: `üyelere`, `Friends`, `Club`, `Hopi`, `Trendyol Plus`
- kod veya kupon: `APP15`, `OUTLET25 koduyla`, `kupon`
- uygulama/mobil: `App'e özel`, `mobil uygulamada`
- beden: `45 ve üzeri bedenlerde`
- ödeme yöntemi: banka/kredi kartı, Maximum, Bonus, World, Axess, Paraf
- minimum sepet: `7.500 TL ve üzeri`
- birlikte alım/paket: `ayakkabı alışverişinle birlikte`
- ilk alışveriş veya ilk sipariş

## 6. Yanlış pozitiflere karşı eklenen korumalar

### 6.1 Gizli şablon koruması

ASICS sayfasında `Sepetteki Son Fiyat` metnini taşıyan fakat `display:none` olan ve fiyatı boş bırakılmış bir şablon bulundu. Gizli, `aria-hidden`, `display:none` veya `visibility:hidden` öğeler kesin fiyat kanıtı sayılmıyor.

### 6.2 Öneri kartı karışması koruması

Ürün sayfasının altındaki daha ucuz öneri kartlarının fiyatı ana ürünün sepette fiyatı olarak alınmıyor. Adaylar belge sırasıyla değerlendirilir ve ana üründeki ilk geçerli kesin teklif kazanır.

### 6.3 Üyelik/kupon/sepet fiyatı ayrımı

Trendyol canlı kartında şu üç fiyat aynı alanda görüldü:

- normal: 599,90 TL
- sepette: 581,90 TL
- Trendyol Plus ile: 552,80 TL

Motor, `data-testid="discounted-price"` ile sepette fiyatı doğrudan bağlar; daha düşük olduğu için Plus fiyatını yanlışlıkla sepette fiyat seçmez.

### 6.4 Kupon tutarı koruması

`Sepette 200 TL kupon fırsatı` metnindeki 200 TL, ürünün sepette satış fiyatı değildir. Bu teklif `coupon` kampanyası olarak tutulur ve `cart_price=200` üretilmez.

### 6.5 Raf fiyatını koruma

Sepette fiyat artık `current_price` üzerine yazılmaz. Hedef fiyat değerlendirmesi `current_price` ile `cart_price` değerlerinin düşüğünü kullanmaya devam ettiği için mevcut fırsat yakalama kazanımı korunur.

## 7. Canlı kullanıcı akışı doğrulamaları

### 7.1 Sportive

Test edilen [Nike Revolution 8 ürün sayfasında](https://www.sportive.com.tr/nike-revolution-8-erkek-gri-kosu-ayakkabi-hj9198-004-1/) 44 beden seçildi, ürün sepete eklendi ve mini sepet açıldı.

- ürün sayfası fiyatı: 3.699 TL
- mini sepet fiyatı: 3.699 TL
- sonuç: bu ürün için denetim anında sepette ek indirim yok
- sayfada uygulamaya/koda ve çoklu alıma bağlı sepet kampanyaları ayrıca görüldü; bunlar kesin fiyat sayılmadı

### 7.2 Boyner

[Kate Spade ürün sayfasında](https://www.boyner.com.tr/kate-spade-siyah-kadin-topuklu-ayakkabi-km793blk-p-15752389) şu görünür yapı doğrulandı:

- normal fiyat: 22.999 TL
- etiket: `Sepette %26 İndirim`
- kesin sepette fiyat: 16.999 TL
- satıcı: BOYNER

Beden seçim kutusu açıldı fakat canlı DOM’daki `listbox` boş döndü. Bu nedenle sepete ekleme düğmesiyle ikinci aşama tamamlanamadı. Ürün sayfasındaki kesin fiyat yapısı ve seçiciler doğrulandı; gerçek sepet HTML’i gönderilirse ikinci kanıt da fixture olarak eklenebilir.

### 7.3 n11

[n11 kadın ayakkabı kategori sayfasında](https://www.n11.com/ayakkabi-ve-canta/kadin-ayakkabi?m=Sepet365) aşağıdaki kart doğrulandı:

- normal fiyat: 2.445 TL
- etiket: `SEPETTE`
- kesin sepette fiyat: 1.833,75 TL
- DOM sınıfı: `basket-price`

Ürün sayfasına geçildiğinde beden seçilmeden fiyat alanı görünür değildi ve `Sepete Ekle` düğmesi pasifti. Bu nedenle kategori kartı kesin fiyat kanıtıdır; varyant seçilmiş ürün ve sepet HTML’i ikinci aşama için gereklidir.

### 7.4 Trendyol

[Trendyol Sedef kategori sayfasında](https://www.trendyol.com/sedef-gunluk-ayakkabi-x-b105367-c1352) aynı kartta normal, sepette, kupon ve Plus fiyatı birlikte doğrulandı. Yeni seçici ve koşul analizi bu değerleri birbirinden ayırıyor.

### 7.5 FLO

Arama indeksinde daha önce sepette fiyatla görülen ürün URL’i canlı testte ürün sayfası yerine kategori sayfasına yönlendi. Bu nedenle eski indeks değeri güncel kesin kanıt olarak kullanılmadı.

## 8. Mağaza bazlı ayrıntılı durum matrisi

| # | Mağaza | Denetim sonucu | Motorun yeni davranışı | Kesinleştirmek için gereken ek kanıt |
|---:|---|---|---|---|
| 1 | Decathlon TR | Bu turda güncel sepette teklif bulunamadı | Görünür kesin teklif çıkarsa fiyatı; yüzdesel/koşullu teklifi kampanya olarak yakalar | Kampanyalı ürün HTML’i + ürün sepetteyken sepet HTML’i |
| 2 | Adidas TR | Test edilen canlı kategori sayfasında görünür sepet metni yok; dönemsel indeks kanıtı güncel fiyat sayılmadı | `Sepette %…` metnini kampanya olarak saklar; kesin tutar yoksa hesaplamaz | Kampanyalı ürün ve sepet HTML çifti |
| 3 | Nike TR | Güncel kesin kanıt bulunamadı | Ortak görünür teklif dedektörü aktif | Kampanyalı ürün ve sepet HTML çifti |
| 4 | Puma TR | Güncel kesin kanıt bulunamadı | Ortak görünür teklif dedektörü aktif | Kampanyalı ürün ve sepet HTML çifti |
| 5 | New Balance TR | Güncel kesin kanıt bulunamadı | Ortak görünür teklif dedektörü aktif | Kampanyalı ürün ve sepet HTML çifti |
| 6 | Sportive | Canlı ürün sepete eklendi; 3.699 TL ürün ve sepet fiyatı aynı. Uygulama/kod ve çoklu alım kampanyaları görüldü | Kesin fark yoksa cart deal göstermez; koşullu teklifleri kampanya olarak saklar | Gerçekten aktif sepette indirimli ürünün ürün + sepet HTML’i |
| 7 | Intersport | Yerel yakalanmış HTML’de 10.999 TL normal, 8.799,20 TL sepette | Mevcut özel seçici korundu; raf ve sepet fiyatı ayrıldı | Mevcut fixture yeterli; dönemsel canlı tekrar önerilir |
| 8 | Barçın | [Sepette indirim sayfasında](https://www.barcin.com/sepette-indirim/) `2 ve Üzerine Sepette Ek %10` görüldü | `quantity` koşulu; tek ürün için kesin fiyat üretmez | İki ürünlü sepet HTML’i istenirse kampanya sepet toplamı ayrıca doğrulanabilir |
| 9 | Korayspor | Güncel kesin kanıt bulunamadı | Ortak görünür teklif dedektörü aktif | Kampanyalı ürün ve sepet HTML çifti |
| 10 | FLO | Eski ürün URL’i kategoriye yönlendi; güncel ürün kanıtı yok | Eski indeks fiyatını aktif fiyat saymaz | Güncel kampanyalı ürün ve checkout.flo.com.tr sepet HTML’i |
| 11 | SuperStep | [Sepette %50 kategori sayfası](https://www.superstep.com.tr/sepette-50/) canlı görüldü; kesin tutar doğrulanmadı | Yüzdeyi kampanya olarak saklar, tutar uydurmaz | Bir ürün sayfası + ürün eklenmiş sepet HTML’i |
| 12 | Sneaks Up | [Jordan ürününde](https://www.sneaksup.com/jordan-air-1-low-553558-300-sneaker-p-32112) `45 ve üzeri bedenlerde sepette %20` görüldü | `size` koşulu; 45 altı bedenlere fiyat yayılmaz | 45+ seçilmiş ürün ve sepet HTML’i |
| 13 | Yalı Spor | Güncel kesin kanıt bulunamadı | Ortak görünür teklif dedektörü aktif | Kampanyalı ürün ve sepet HTML çifti |
| 14 | Boyner | Ürün sayfasında 22.999 TL → sepette 16.999 TL kesin doğrulandı | Boyner kardeş fiyat yapısı ve normal fiyat restorasyonu eklendi | Beden listesi dolu bir ürünün sepet HTML’i ikinci kanıtı güçlendirir |
| 15 | Kaptan Spor | Güncel kesin kanıt bulunamadı | Ortak görünür teklif dedektörü aktif | Kampanyalı ürün ve sepet HTML çifti |
| 16 | SPX | Test edilen ürün URL’inde canlı sepet metni görünmedi; eski indeks sonucu güncel sayılmadı | `Sepette NET %…` görünürse kampanya, kesin sonuç görünürse cart_price | Güncel kampanyalı ürün ve sepet HTML çifti |
| 17 | Kutupayısı | Güncel kesin kanıt bulunamadı | Ortak görünür teklif dedektörü aktif | Kampanyalı ürün ve sepet HTML çifti |
| 18 | Trendyol | Kategori kartında normal, sepette, kupon ve Plus fiyatı birlikte doğrulandı | Sepette fiyatı Plus/kupondan ayıran özel DOM desteği eklendi | Seçilmiş varyantlı ürün veya sepet HTML’i ek güvence sağlar |
| 19 | Hepsiburada | Bu turda güncel kesin sepette fiyat kanıtı bulunamadı | Kupon tutarını ürün fiyatı saymaz; görünür kesin sepet fiyatını ayrı alır | Kampanyalı ürün HTML’i + sepet HTML’i; erişim engeli varsa kullanıcı tarayıcısından kayıt |
| 20 | n11 | Kategori kartında 2.445 TL → sepette 1.833,75 TL kesin doğrulandı | `basket-price` görünür yapısı ortak dedektörle yakalanır | Beden seçilmiş ürün + sepet HTML’i |
| 21 | Amazon TR | Güncel kesin sepet fiyat kanıtı bulunamadı | Kuponu kampanya olarak ayırır; kesin fiyat olmadan kupon tutarını fiyat saymaz | Kampanyalı ürün ve sepet HTML’i; kişisel/ödeme bilgileri temizlenmiş olmalı |
| 22 | ASICS TR | [Ürün sayfasında](https://www.asics.com.tr/gel130-645) `%25` sepet kampanyası görüldü; `Sepetteki Son Fiyat` alanı gizli ve boş şablondu | Gizli şablon yok sayılır; görünür yüzde kampanya olarak tutulur | Fiyatı dolu görünür ürün veya sepet HTML’i |
| 23 | Skechers TR | Güncel kesin kanıt bulunamadı | Ortak görünür teklif dedektörü aktif | Kampanyalı ürün ve sepet HTML çifti |
| 24 | Brooks Türkiye | Güncel kesin kanıt bulunamadı | Ortak görünür teklif dedektörü aktif; mevcut özel JSON-LD fiyat kazanımı korunur | Kampanyalı ürün ve sepet HTML çifti |
| 25 | Columbia Türkiye | [Ayakkabı sayfasında](https://www.columbia.com.tr/ayakkabi) 1 üründe %10, 2 üründe %20, 3+ üründe %30 ve üyeye ek %5 görüldü | `quantity` ve `membership` koşulları; tek koşulsuz fiyat üretmez | 1/2/3 ürün sepet HTML’leri istenirse her kademe ayrıca doğrulanabilir |
| 26 | Salomon Türkiye | Güncel kesin kanıt bulunamadı | Ortak görünür teklif dedektörü aktif | Kampanyalı ürün ve sepet HTML çifti |
| 27 | The North Face Türkiye | Test edilen canlı ayakkabı sayfasında görünür sepet metni yok; eski kod kampanyası güncel sayılmadı | Kodlu teklif görünürse koşullu kampanya olarak tutulur | Güncel kampanyalı ürün ve sepet HTML çifti |

## 9. Değiştirilen ana bileşenler

### Backend

- `backend/engines.py`
  - 27 motorun tamamında sepet teklifi kabiliyeti etkinleştirildi.
  - kesin fiyat, yüzde, koşul, kaynak ve güven analizi eklendi.
  - gizli DOM ve öneri kartı korumaları eklendi.
  - Intersport raf/sepet fiyatı ayrıldı.
- `backend/stores/structured_retail.py`
  - ortak sepet dedektörü tüm yapılandırılmış perakende motorlarına bağlandı.
  - sepette fiyatın normal fiyat üzerine yazılması kaldırıldı.
- `backend/stores/retailers.py`
  - Boyner’in güncel kardeş fiyat DOM’u desteklenerek normal fiyat geri yüklendi.
- `backend/services.py`
  - sepet fiyatı kaynak/güven/koşul alanları saklanıyor.
  - yalnız koşulsuz ve normal fiyattan düşük kesin tutar sepet alarmı oluşturuyor.
- `backend/discovery_service.py`, `backend/variant_service.py`, `backend/server.py`
  - yeni alanlar keşif, varyant, manuel link ve fiyat geçmişi yollarına taşındı.
- `backend/insights.py`
  - görünür ve yüksek güvenli sepet fiyatı satın alma güven puanına dahil edildi.

### Frontend

- `frontend/src/pages/ProductDetail.jsx`
  - kesin ve daha düşük sepet fiyatı ana fiyat olarak gösteriliyor.
  - normal fiyat yan sütunda üstü çizili gösteriliyor.
  - kesin fiyat olmayan koşullu sepet kampanyasının etiketi mağaza altında gösteriliyor.
- `frontend/src/pages/DebugLab.jsx`
  - sepet fiyatı kaynağı, güveni ve koşulları ham veri görünümüne eklendi.

## 10. Test sonuçları

### Backend tam test paketi

```text
124 passed, 1 skipped
```

Atlanan test mevcut paket tarafından koşullu bırakılmış bir testtir; sepette fiyat değişikliği nedeniyle atlanmamıştır.

### Sepette fiyat odaklı ve motor testleri

```text
67 passed
```

Kapsanan kritik senaryolar:

- 27 motorun tamamında `cart_price` kabiliyeti
- kesin görünür fiyatın normal fiyattan ayrı kalması
- adet, kod, beden, üyelik ve uygulama koşulları
- Boyner kardeş fiyat DOM’u
- öneri kartı kontaminasyonu
- Trendyol Plus/sepet/kupon ayrımı
- gizli ASICS şablonu
- Intersport eski kazanımının korunması

### Frontend

```text
Test Suites: 2 passed, 2 total
Tests: 8 passed, 8 total
```

### Üretim derlemesi

```text
Compiled successfully.
```

### Kod biçimi/diff kontrolü

`git diff --check` hata vermedi. Yalnız Windows satır sonu dönüşümü hakkında bilgi uyarıları görüldü.

## 11. HTML dosyaları nasıl gönderilmeli?

Evet, eksik mağazaların indirilmiş HTML’leri çözümü belirgin biçimde hızlandırır. Her mağaza için mümkünse aşağıdaki üç dosya gönderilmelidir:

1. **Ürün sayfası – beden seçilmeden önce**
2. **Ürün sayfası – kampanyaya uygun beden seçildikten sonra**
3. **Sepet sayfası veya açık mini sepet – ürün eklendikten sonra**

Önerilen adlandırma:

```text
hepsiburada_urun.html
hepsiburada_urun_beden_secili.html
hepsiburada_sepet.html
```

Her dosyanın yanında şu bilgiler bulunmalıdır:

- kaynak URL
- kayıt tarihi ve yaklaşık saat
- seçilen beden
- ürün adedi
- üye girişi yapılıp yapılmadığı
- kod/kupon uygulanıp uygulanmadığı
- ekranda görülen normal fiyat
- ekranda görülen sepette fiyat

Kişisel veri temizliği:

- ad, e-posta, telefon ve adres çıkarılmalıdır.
- çerez/token değerleri mümkünse temizlenmelidir.
- ödeme kartı veya ödeme adımı HTML’i gönderilmemelidir.
- siparişi tamamlama yapılmasına gerek yoktur; sepet görünümü yeterlidir.

## 12. Kabul ölçütü

Bir mağaza “kesin sepet fiyatı canlı doğrulandı” sınıfına ancak şu koşullarla yükseltilir:

1. Ürün kimliği ve seçilen varyant nettir.
2. Normal fiyat görünür ve ürüne bağlıdır.
3. Sepette fiyat görünür ve aynı ürüne bağlıdır.
4. Kod, üyelik, adet, beden veya ödeme yöntemi koşulu belirlenmiştir.
5. Fiyat başka ürünün öneri kartından gelmemektedir.
6. Gizli şablondan veya eski arama indeksinden gelmemektedir.
7. Parser fixture testi gerçek DOM yapısını temsil etmektedir.

## 13. Güvenlik ve operasyon sınırı

Bu çalışmada normal ürün görüntüleme, beden seçme, sepete ekleme ve mini sepet açma akışları kullanıldı. CAPTCHA çözme, erişim korumasını atlatma, kimlik sahteciliği, stealth/fingerprint değiştirme veya proxy rotasyonu uygulanmadı. Erişim/veri görünürlüğü yetersiz olduğunda sonuç `kanıt yok`, `koşullu` veya `engelli` olarak bırakıldı; fiyat uydurulmadı.

## 14. Nihai değerlendirme

Önceki “yalnız Intersport” yaklaşımı artık 27 motorun tamamını kapsayan, ancak kanıt kalitesini düşürmeyen ortak bir sepet teklifi altyapısına dönüştürüldü. En önemli kazanım yalnız daha fazla mağazada metin aramak değildir; normal fiyat, kesin sepet fiyatı, üyelik fiyatı, kupon, miktar ve beden koşullarının birbirinden ayrılmasıdır.

Şu an sistem:

- **27/27 motor kabiliyeti** gösterir.
- kesin fiyatı yalnız kanıt varsa kullanır.
- koşullu kampanyayı kullanıcıya gösterir fakat yanlış fiyat alarmı üretmez.
- Intersport’un çalışan seçicisini ve diğer fiyat/stok/kimlik kazanımlarını korur.
- yeni HTML kanıtları geldiğinde mağaza sınıfına seçici eklenmeden de ortak dedektörle çalışabilir; gerekirse fixture ile mağaza özel seçici güçlendirilir.
