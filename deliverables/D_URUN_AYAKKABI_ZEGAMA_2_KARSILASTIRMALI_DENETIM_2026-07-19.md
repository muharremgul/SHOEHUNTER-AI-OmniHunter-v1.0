# D:\urun_ayakkabi – Nike Zegama 2 Karşılaştırmalı Denetim Raporu

**Denetim tarihi:** 19 Temmuz 2026  
**Karşılaştırılan projeler:**

- Diğer proje: `D:\urun_ayakkabi`
- Bizim proje: `C:\Users\ÖGR1\Documents\Ayakkabi`
- Test sorgusu: `Zegama 2`
- Her iki motorun AI tarafından ürettiği ortak normalleştirilmiş sorgu: `Nike Zegama 2`

**Denetim türü:** Salt okunur kod, veritabanı ve canlı arama karşılaştırması. Kaynak kodda değişiklik yapılmamıştır.

## 1. Kısa cevap

`D:\urun_ayakkabi` ekranının daha fazla ürün göstermesinin tek nedeni daha güçlü arama değildir. Fark dört kaynaktan oluşmaktadır:

1. Diğer veritabanı Zegama 2 için daha uzun süre tarama yapmış ve daha fazla tarihsel kayıt biriktirmiştir.
2. Diğer veritabanındaki fazla sekiz ilanın beşi yanlış ürün veya aynı ürünün takip parametreleri nedeniyle çoğaltılmış kopyasıdır.
3. Bizim güncel motorda N11 statik aramadan tarayıcı aramasına geçirilmiştir. Canlı testte tarayıcı yolu zaman aşarken aynı güncel N11 sayfasının statik yolu altı doğru Zegama 2 URL’si üretmiştir.
4. Ham AI arama skoru marka adını model eşleşmesi gibi değerlendirebildiğinden Pegasus, Initiator, Ultrafly ve FLO’daki başka “2” modelleri de sonuç sayısına katılabilmektedir. Radar’ın kimlik eşleştirmesi bunların çoğunu doğru biçimde reddeder; bu nedenle “ham bulunan” ile “ürüne bağlanan” sayı aynı değildir.

Sonuç olarak diğer veritabanındaki **18 Radar ilanına karşı bizim 10 ilanımız** görünmektedir; ancak sekiz ilanın yalnızca üçü gerçekten Zegama ile ilgilidir. Bu üç kaydın biri stokta, biri stok dışı, biri ise stok durumu bilinmeyen tarihsel kayıttır.

## 2. Denetim yöntemi

Denetimde aşağıdaki kontroller yapılmıştır:

- İki projenin mağaza kayıtları ve arama yolu özellikleri karşılaştırıldı.
- İki `.env` dosyasındaki yalnızca veritabanı adları ve anahtarların tanımlı/boş durumu kontrol edildi; gizli anahtar değerleri okunup rapora alınmadı.
- İki motorun `Zegama 2` sorgusunu nasıl normalleştirdiği canlı olarak test edildi.
- Aynı dakika içinde her iki projenin sıfır-link arama akışı `Nike Zegama 2` ile, hiçbir ürün kaydetmeden çalıştırıldı.
- `urun_ayakkabi_db` ve `shoehunter_ai` veritabanlarında Zegama Radar’ı, adaylar, keşif çalışmaları ve bağlı ilanlar karşılaştırıldı.
- İki veritabanındaki Zegama Radar ürününe bağlı URL kümeleri çıkarılarak yalnızca diğer tarafta bulunan sekiz kayıt tek tek incelendi.
- Güncel N11 motoru tarayıcı yönlendirmesi dışında statik resmi arama HTML’iyle ayrıca test edildi.

## 3. Proje ve mağaza kapsamı karşılaştırması

| Ölçüt | D:\urun_ayakkabi | Bizim proje |
| --- | ---: | ---: |
| Kayıtlı mağaza motoru | 23 | 27 |
| Arama yolu olan N11 | Var | Var |
| N11’in varsayılan arama yöntemi | Statik HTML | Tarayıcı/JavaScript |
| Hepsiburada arama yöntemi | Statik HTML | Tarayıcı/JavaScript |
| Tarayıcı aramasına gönderilen motor | Yaklaşık 10 | Yaklaşık 16 |
| Varsayılan global tarayıcı eşzamanlılığı | 2 | 2 |
| Motor başına tarayıcı zaman aşımı | 34 saniye | 34 saniye |
| Toplu tarayıcı üst sınırı | 150 saniye | 150 saniye |

Bizim proje mağaza kapsamı bakımından geride değildir; Brooks Türkiye, Columbia Türkiye, Salomon Türkiye ve The North Face Türkiye gibi ek motorlarla daha geniştir. Sorun kapsam sayısı değil, artan JavaScript motorlarının aynı iki tarayıcı yuvasını ve aynı 150 saniyelik üst süreyi paylaşmasıdır.

## 4. AI sorgu normalleştirmesi

Her iki proje de canlı testte aynı sonucu üretmiştir:

```json
{
  "brand": "Nike",
  "model": "Zegama 2",
  "normalized_query": "Nike Zegama 2"
}
```

Bu nedenle farkın sebebi Gemini sorgu yorumlama katmanı değildir.

## 5. Aynı dakika içindeki canlı arama sonucu

Her iki motor da bu denetim anında ham toplam olarak **36 sonuç** döndürmüştür. Ancak sonuçların bileşimi ve doğruluğu aynı değildir.

### 5.1 D:\urun_ayakkabi canlı sonucu

| Mağaza | Ham sonuç | Zegama 2 ile gerçekten ilgili | Sorun/not |
| --- | ---: | ---: | --- |
| Nike TR | 6 | 0 | Beş Pegasus 42 ve bir yeni ACG Zegama; Zegama 2 değil |
| Sportive | 4 | 1 | Üç kayıt Zegama 2 değil, yeni ACG Zegama |
| Intersport | 6 | 6 | Doğru model/varyantlar |
| Korayspor | 6 | 6 | Doğru model/varyantlar |
| Yalı Spor | 3 | 3 | Doğru model/varyantlar |
| N11 | 6 | 6 URL | Başlık bütün kartlarda ilk karttan kopyalanmış; fiyat yok, ayrıntı zenginleştirme başarısız |
| Amazon TR | 4 | 2 | Initiator ve Ultrafly yanlış eşleşme |
| Barçın | 1 | 0 | V5 RNR Suede 2, yanlış model |
| Diğerleri | 0 | 0 | Engelli, zaman aşımı veya sonuç yok |
| **Toplam** | **36** | **24 aday URL** | 12 ham sonuç Zegama 2 değildir |

### 5.2 Bizim proje canlı sonucu

| Mağaza | Ham sonuç | Zegama 2 ile gerçekten ilgili | Sorun/not |
| --- | ---: | ---: | --- |
| Nike TR | 6 | 0 | Aynı Pegasus/ACG yanlış eşleşmeleri |
| Sportive | 4 | 1 | Üç yeni ACG Zegama, Zegama 2 değil |
| Intersport | 6 | 6 | Doğru model/varyantlar |
| Korayspor | 6 | 6 | Doğru model/varyantlar |
| Yalı Spor | 3 | 3 | Doğru model/varyantlar |
| Amazon TR | 4 | 2 | Initiator ve Ultrafly yanlış eşleşme |
| Barçın | 1 | 0 | V5 RNR Suede 2, yanlış model |
| FLO | 6 | 0 | MD Runner 2, Court Borough 2 ve benzeri yanlış modeller |
| N11 | 0 | 0 | Tarayıcı grubu zaman aşımına uğradı |
| Diğerleri | 0 | 0 | Engelli, zaman aşımı veya sonuç yok |
| **Toplam** | **36** | **18 aday URL** | 18 ham sonuç Zegama 2 değildir |

Ham toplamın bu testte eşit çıkması, iki sonucun aynı kalitede olduğu anlamına gelmez. Bizim tarafta kaybedilen altı doğru N11 URL’sinin yerini FLO’dan gelen altı yanlış “Nike + 2” sonucu doldurmuştur.

## 6. N11 regresyonunun kesin kanıtı

Diğer projede N11 şu şekilde tanımlanmıştır:

- Arama URL’si: `https://www.n11.com/arama?q={q}`
- Arama yöntemi: statik HTML

Bizim projede özel N11 motoru bulunmaktadır ancak `js_search = True` ve `use_browser = True` durumundadır. Bu nedenle sıfır-link araması N11’i statik istek grubuna değil tarayıcı grubuna yollar.

Canlı sonuç:

- Bizim normal arama akışımızdaki N11 tarayıcı görevi: **zaman aşımı, 0 sonuç**.
- Aynı güncel N11 motoru aynı resmi URL’yi statik olarak aldığında: **479.609 bayt HTML ve 6 Zegama 2 URL’si**.

Bu, N11 için veri kaybının mağaza tarafından tamamen engellenmekten değil, yanlış önceliklendirilmiş yürütme yolundan kaynaklandığını göstermektedir. Statik yol çalışırken tarayıcı yolunun zorunlu tutulması altı doğru adayı kaybettirmiştir.

## 7. Tarayıcı kuyruğu ve toplu zaman aşımı sorunu

Güncel projede yaklaşık 16 mağaza JavaScript/tarayıcı grubuna girmektedir. Tarayıcı havuzu varsayılan olarak aynı anda yalnızca iki sayfa çalıştırır. Her motor 34 saniyeye kadar bekleyebilir.

Kötü durum hesabı:

```text
16 motor / 2 eşzamanlı yuva = 8 dalga
8 dalga × 34 saniye = 272 saniyeye kadar teorik süre
Toplu aramanın üst sınırı = 150 saniye
```

Toplu süre hesabı kodda üçlü dalga varsayımı yaparken gerçek varsayılan tarayıcı eşzamanlılığı ikidir. Ayrıca hesaplanan süre 150 saniyede kesilmektedir. Sonuç olarak ilk motorlar yavaşladığında listenin sonundaki N11, Hepsiburada, Brooks, Salomon ve The North Face gibi motorlar başlamadan veya tamamlanmadan bütün görev grubu iptal edilebilmektedir.

Canlı testte bizim projede aşağıdaki motorlar aynı toplu aramada zaman aşımına uğramıştır:

- Adidas
- SuperStep
- SPX
- Kutupayısı
- Trendyol
- Hepsiburada
- N11
- Skechers
- Brooks
- Salomon
- The North Face

Bu durum mağaza motorlarının tamamının bozuk olduğunu kanıtlamaz; ortak tarayıcı bütçesinin etkileşimli arama için yetersiz ve adaletsiz dağıtıldığını gösterir.

## 8. Veritabanı birikimi karşılaştırması

İki proje farklı MongoDB veritabanları kullanmaktadır:

- Diğer proje: `urun_ayakkabi_db`
- Bizim proje: `shoehunter_ai`

Her iki veritabanında aynı kimlikli Zegama Radar kaydı bulunmasına rağmen tarama geçmişleri farklıdır.

| Ölçüt | urun_ayakkabi_db | shoehunter_ai | Fark |
| --- | ---: | ---: | ---: |
| Zegama keşif çalışması | 32 | 23 | Diğer DB +9 çalışma |
| Birikmiş aday | 58 | 45 | Diğer DB +13 aday |
| Reddedilmiş aday | 36 | 33 | Diğer DB +3 |
| `attached` aday | 22 | 12 | Diğer DB +10 |
| Radar ürününe bağlı mevcut ilan | 18 | 10 | Diğer DB +8 |
| Adında Zegama geçen bütün ürünlerin ilanı | 36 | 28 | Diğer DB +8 |

Bu tablo, diğer ekranın daha uzun süre toplanmış tarihsel veriyi gösterdiğini kanıtlamaktadır. Anlık arama yeteneği ile birikmiş veritabanı sayısı aynı ölçüm değildir.

## 9. Diğer veritabanındaki fazla sekiz ilanın incelemesi

İki Zegama Radar ürününün bağlı URL kümeleri karşılaştırılmıştır. Diğer veritabanında olup bizim veritabanımızda olmayan sekiz kayıt aşağıdadır.

| Sayı | Mağaza/kayıt | Değerlendirme |
| ---: | --- | --- |
| 2 | Amazon Nike Initiator, aynı ASIN fakat farklı `/ref=sr_1_2` ve `/ref=sr_1_3` yolları | Yanlış model ve yinelenen ürün |
| 3 | Amazon Nike Ultrafly, aynı ASIN fakat farklı `/ref=sr_1_6`, `/ref=sr_1_7`, `/ref=sr_1_10` yolları | Yanlış model ve üç kez sayılmış ürün |
| 1 | Amazon Nike Zegama Trail 2 | Gerçek ilgili ürün, stokta görünmüş |
| 1 | Intersport Nike Zegama 2 Kadın Siyah | Gerçek ilgili varyant fakat stok dışı |
| 1 | Yalı Spor Nike Zegama 2 Erkek Siyah | URL ilgili; stok durumu `unknown`, sayfa başlığı genel |

Sonuç:

- Görünen sekiz ilanın **beşi gerçek Zegama 2 değildir**.
- Beş yanlış kaydın içinde Amazon takip yolu nedeniyle çoğaltılmış aynı ASIN’ler vardır.
- Yalnızca üç kayıt Zegama ile ilgilidir.
- Bu üç kaydın yalnızca biri açık biçimde stokta, biri stok dışı, biri belirsizdir.

Bu yüzden “18’e karşı 10” farkını “sekiz kaçırılmış güncel fırsat” olarak yorumlamak doğru değildir. Kalite süzgecinden sonra anlamlı tarihsel fark üç, açık stoklu fark ise birdir.

## 10. Ham arama skoru neden yanlış sonuçları yüksek puanlıyor?

Her iki projedeki ham arama skoru `token_set_ratio` kullanmaktadır. Bu benzerlik yöntemi, kısa başlık sorgunun bir alt kümesiyse aşırı yüksek puan verebilir.

Örnek:

```text
Sorgu: Nike Zegama 2
Amazon kart başlığı: Nike
Ham skor: 100
```

Başlık yalnızca “Nike” olduğunda model adı ve nesil kanıtı bulunmamasına rağmen skor 100 olabilmektedir. Aynı nedenle:

- Nike Pegasus 42,
- Nike Initiator,
- Nike Ultrafly,
- Nike V5 RNR Suede 2,
- Nike MD Runner 2,
- Nike Court Borough 2

ham sonuç listesine girebilmektedir.

Radar’ın ürün kimliği eşleştirmesi daha katıdır. Örneğin Pegasus 42 adayları `generation_mismatch`, yeni ACG Zegama adayları `protected_model_token_mismatch` kanıtıyla reddedilmiştir. Bu reddetmeler ürün kaybı değil, doğru kalite kontrolüdür.

## 11. Güncel Radar çalışmasının gerçek durumu

Bizim veritabanındaki 19 Temmuz çalışması şu sonucu üretmiştir:

- Ham mağaza adayı: 30
- Otomatik eşleşme: 9
- Reddedilen: 21
- Yeni eklenen ilan: 7

Bu çalışma sırasında:

- Nike, Sportive, Intersport, Korayspor, SuperStep ve Trendyol sonuç üretmiştir.
- N11, Amazon ve Yalı Spor devre kesici nedeniyle ertelenmiştir.
- Hepsiburada engelli durumuna düşmüştür.
- Boyner zaman aşımına uğramıştır.

Dolayısıyla Radar hiç ürün bulamamış değildir; son çalışmada yedi yeni ilan eklemiştir. Ancak belirli mağazaların devre kesici/arama yolu durumu toplamı sınırlandırmıştır.

## 12. Kök nedenlerin önem sırası

### P0 – N11 yanlış yürütme yolu

N11’in statik resmi arama sayfası altı aday verirken tarayıcı grubunda zaman aşımına uğraması, doğrudan ve tekrarlanabilir bir ürün kaybıdır.

### P0 – Etkileşimli arama ile toplu tarayıcı bütçesi uyumsuzluğu

16 tarayıcı motoru, iki yuva ve 150 saniye üst sınırı aynı anda kullanıldığında son mağazaların tamamlanma şansı düşmektedir.

### P0 – Ham sonuç sayısının kalite sayısı gibi sunulması

36 ham sonucun 12–18 adedi çalışmaya göre yanlış modeldir. Kullanıcı ekranda “ürün bulundu” sayısını kalite göstergesi sanmaktadır.

### P1 – Amazon URL tekilleştirmesi

ASIN aynı olduğu halde `/ref=sr_1_x` yol parçaları farklı URL kabul edilmekte ve aynı ürün birden fazla ilan olarak birikebilmektedir.

### P1 – Ayrı veritabanlarının senkron olmaması

Bir veritabanındaki tarihsel Radar birikimi diğerinde otomatik olarak görünmemektedir. Projeler aynı kod ailesinden gelse de veri kümeleri bağımsızdır.

### P1 – Devre kesicinin keşif kapsamını daraltması

N11, Amazon ve Yalı Spor gibi mağazalar açık devre durumundayken Radar çalışması onları tamamen erteler. Bu koruma mağazaya yük bindirmemek için doğrudur; fakat kontrollü iyileşme denemesi yoksa uzun süre veri kaybına dönüşebilir.

## 13. Önerilen iyileştirmeler – bu denetimde uygulanmadı

### 13.1 Arama sonuçlarını dört ayrı sayaçla gösterme

Tek “toplam sonuç” yerine:

1. Ham aday
2. Kesin model eşleşmesi
3. Benzersiz ürün/varyant
4. Fiyatı ve stoku doğrulanmış aktif teklif

gösterilmelidir. Böylece 36 ham sonuç ile 18/24 doğru aday arasındaki fark kullanıcıya açık olur.

### 13.2 N11 için statik-önce, tarayıcı-yedek akışı

Önerilen sıra:

1. Resmi N11 arama HTML’ini statik olarak iste.
2. Ürün kartları bulunursa sonucu kullan.
3. Statik yanıt gerçekten boş, eksik veya koruma sayfasıysa tarayıcıya geç.
4. Tarayıcı zaman aşımında statik sonuçları kaybetme.

Bu denetimde statik yolun altı adayı verdiği kanıtlanmıştır.

### 13.3 Tarayıcı görevlerini tek toplu son tarihten ayırma

- Gerçek eşzamanlılık değeri ile süre hesabı aynı kaynaktan okunmalıdır.
- Her mağaza sonucu tamamlandıkça korunmalıdır; tek motorun yavaşlığı bütün grubu iptal etmemelidir.
- Etkileşimli kullanıcı araması zamanlayıcı kontrollerinden daha yüksek öncelik almalıdır.
- Gerekirse etkileşimli arama ve arka plan kontrolü ayrı tarayıcı havuzlarına ayrılmalıdır.

### 13.4 Model eşleşmesinde zorunlu çekirdek belirteç

`Nike Zegama 2` sorgusunda en az şu şartlar aranmalıdır:

- Marka uyumu: Nike
- Korunan model belirteci: Zegama
- Nesil: 2 veya açık eşdeğeri

Yalnızca “Nike” veya yalnızca “2” eşleşmesi sonuç kabul edilmemelidir.

### 13.5 Amazon ASIN tabanlı kanonikleştirme

Amazon URL’si `/dp/{ASIN}` biçimine indirgenmeli; `/ref=sr_1_x` ve benzeri yönlendirme parçaları kimliğe dahil edilmemelidir. Aynı ASIN tek ilan olmalıdır.

### 13.6 Devre kesici iyileşme denemesi

Açık devrede bütün keşfi ertelemek yerine süre dolduğunda tek, düşük maliyetli sağlık isteği yapılmalı; başarı halinde mağaza yeniden aramaya alınmalıdır. Kullanıcı araması için devre kesici durumu ekranda ayrıca gösterilmelidir.

### 13.7 Tek kanonik veritabanı veya kontrollü veri birleştirme

İki proje paralel kullanılacaksa Radar, aday ve ilan geçmişinin hangi veritabanında kanonik olduğu belirlenmelidir. Kör kopyalama yapılmamalı; ürün kimliği, mağaza slug’ı, model kodu/ASIN ve kanonik URL üzerinden tekilleştirilmiş bir birleştirme planı kullanılmalıdır.

## 14. Mevcut projenin daha iyi olduğu noktalar

Denetim yalnız eksikleri göstermemektedir. Bizim proje aşağıdaki alanlarda daha ileridir:

- 27 mağaza motoru ile daha geniş kapsam.
- Brooks, Columbia, Salomon ve The North Face desteği.
- Resmi katalog tohumu içeren ek keşif katmanı.
- Radar/link/AI takip kaynağı ayrımı.
- Aile profili ve çoklu beden bağlamı.
- Daha katı ürün kimliği eşleştirmesi sayesinde Pegasus ve yeni ACG Zegama gibi yanlış ürünlerin Radar’a bağlanmaması.
- Ürün sınıfı, Radar işareti ve ayrıntılı bildirim sınıfları.

Bu nedenle çözüm eski projeyi bütünüyle geri almak değildir. Doğru yaklaşım, eski projedeki çalışan N11 statik yolunu ve faydalı tarihsel kayıtları, güncel projenin daha güvenilir kimlik/uyarı yapısına kontrollü biçimde taşımaktır.

## 15. Nihai hüküm

Kullanıcı gözlemi gerçektir: diğer veritabanı Zegama 2 ürününde daha yüksek sayı göstermektedir. Ancak farkın büyük bölümü kalite ve veri geçmişi kaynaklıdır.

Sayısal hüküm:

```text
Diğer Radar ilanı:             18
Bizim Radar ilanı:             10
Görünen fark:                   8
Yanlış/çoğaltılmış kayıt:       5
Gerçek ilgili tarihsel fark:    3
Açıkça stokta olan gerçek fark: 1
```

Canlı aramada doğrulanmış teknik kayıp ise N11’deki altı doğru URL’dir. Bunun kök nedeni statik sayfa çalışmasına rağmen N11’in yoğun tarayıcı grubuna zorlanmasıdır. En yüksek öncelikli iyileştirme, N11’i statik-önce hibrit akışa almak ve tarayıcı görevlerinin ortak 150 saniyelik iptal sınırını yeniden tasarlamaktır.

