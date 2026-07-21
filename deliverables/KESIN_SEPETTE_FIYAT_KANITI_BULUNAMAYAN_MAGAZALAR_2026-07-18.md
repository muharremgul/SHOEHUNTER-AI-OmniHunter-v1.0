# Kesin Sepette Fiyat Kanıtı Bulunamayan Mağazalar

**Proje:** ShoeHunter AI / Ayakkabı  
**Denetim tarihi:** 18 Temmuz 2026  
**Kapsam:** Sistemde kayıtlı 27 mağaza motoru  
**Eksik kesin kanıt:** 23 mağaza  
**Kesin kanıtı doğrulanan ve bu listenin dışında kalan mağazalar:** Intersport, Boyner, Trendyol ve n11

## Executive Summary

- **23 mağazada kesin tutarlı sepette fiyat kanıtı henüz yoktur.** Bu ifade motorların özelliği desteklemediği anlamına gelmez; 27 motorun tamamında ortak sepette fiyat çözümlemesi aktiftir.
- **5 mağazada kampanya görünür, ancak kesin sonuç fiyatı görünmez veya teklif koşulludur.** Bu mağazalarda yüzde ya da kampanya metni saklanır fakat kesin `cart_price` üretilmez.
- **Sportive’de gerçek sepet akışı tamamlandı, ancak test edilen üründe fiyat değişmedi.** Dolayısıyla çalışan sepet doğrulandı fakat indirimli sepet fiyatı kanıtlanmadı.
- **17 mağazada güncel, görünür ve sayısal bir sepette fiyat çifti bulunamadı.** Bu mağazalar için kampanyalı ürün, seçilmiş varyant ve ürün eklenmiş sepet HTML’leri gereklidir.

## Kesin kanıt ölçütü

Bir mağazanın bu listeden çıkarılabilmesi için aşağıdaki kanıtlardan biri bulunmalıdır:

1. Ürün veya listeleme sayfasında normal fiyat ile kesin sepette fiyatın aynı ürün üzerinde görünür olması.
2. Ürün sepete eklendikten sonra normal ürün fiyatından farklı, sayısal ve doğrulanabilir bir sepet fiyatının görünmesi.
3. İndirimin hangi ürün ve varyanta ait olduğunun açık olması.
4. Üyelik, kupon kodu, uygulama, belirli beden, ödeme yöntemi veya çoklu ürün şartı varsa bu şartın ayrıca kaydedilmesi.

Yalnızca “Sepette %20”, “Kupon fırsatı” veya “2 ürüne ek indirim” metni kesin fiyat kanıtı sayılmaz. Böyle teklifler kampanya kanıtıdır fakat tek başına kesin `cart_price` değildir.

## A. Kampanya görüldü, kesin sonuç fiyatı kanıtlanamadı — 5 mağaza

| No | Mağaza | Görülen kanıt | Kesin kanıtı engelleyen durum | Gerekli HTML |
|---:|---|---|---|---|
| 1 | Barçın | “2 ve Üzerine Sepette Ek %10 İndirim” kampanyası görüldü | Adet koşulu var; tek ürün için kesin sonuç fiyatı görünmedi | Aynı kampanyadan iki uygun ürünün sepette olduğu sayfa |
| 2 | SuperStep | “Sepette %50” kampanya kategorisi görüldü | Yüzde mevcut, ürün bazlı kesin sonuç tutarı doğrulanmadı | Kampanyalı ürün sayfası, seçilmiş beden ve ürün eklenmiş sepet |
| 3 | Sneaks Up | “45 ve üzeri bedenlerde sepette %20” görüldü | İndirim belirli bedenlere bağlı; kesin sonuç tutarı görünmedi | 45 veya üzeri beden seçilmiş ürün sayfası ve sepet |
| 4 | ASICS Türkiye | `%25` sepet kampanyası görüldü | “Sepetteki Son Fiyat” alanı gizli ve boş şablondu | Son fiyat alanı görünür/dolu olan ürün veya ürün eklenmiş sepet |
| 5 | Columbia Türkiye | 1 üründe %10, 2 üründe %20, 3+ üründe %30 ve üyeye ek %5 görüldü | Adet ve üyelik koşulları iç içe; tek kesin fiyat yok | Aynı ürün için 1, 2 ve 3 adetli sepetler; üyelik durumu ayrıca belirtilmeli |

## B. Sepet akışı çalıştı, fakat indirimli fiyat oluşmadı — 1 mağaza

| No | Mağaza | Yapılan doğrulama | Sonuç | Eksik kanıt |
|---:|---|---|---|---|
| 6 | Sportive | Beden seçildi ve ürün gerçek sepete eklendi | Ürün sayfası ve sepet fiyatı 3.699 TL olarak aynı kaldı | Aktif sepette indirimi olan uygun ürünün ürün ve sepet HTML çifti |

Sportive motoru ve sepet akışı çalışmaktadır. Eksik olan, test anında normal fiyattan daha düşük bir sepet fiyatı üreten uygun kampanyalı üründür.

## C. Güncel kesin sepette fiyat kanıtı bulunamayanlar — 17 mağaza

| No | Mağaza | Denetim sonucu | Gerekli kanıt |
|---:|---|---|---|
| 7 | Decathlon Türkiye | Güncel, görünür ve kesin sepette fiyat çifti bulunamadı | Kampanyalı ürün, seçilmiş varyant ve ürün eklenmiş sepet HTML’i |
| 8 | Adidas Türkiye | Test edilen canlı kategori sayfasında görünür sepet metni yoktu; eski indeks sonucu güncel kabul edilmedi | Güncel kampanyalı ürün ve sepet HTML çifti |
| 9 | Nike Türkiye | Güncel kesin sepette fiyat kanıtı bulunamadı | Kampanyalı ürün, seçilmiş numara ve sepet HTML’i |
| 10 | Puma Türkiye | Güncel kesin sepette fiyat kanıtı bulunamadı | Kampanyalı ürün, seçilmiş numara ve sepet HTML’i |
| 11 | New Balance Türkiye | Güncel kesin sepette fiyat kanıtı bulunamadı | Kampanyalı ürün, seçilmiş numara ve sepet HTML’i |
| 12 | Korayspor | Güncel kesin sepette fiyat kanıtı bulunamadı | Kampanyalı ürün ve ürün eklenmiş sepet HTML’i |
| 13 | FLO | Eski ürün bağlantısı kategoriye yönlendi; eski fiyat güncel kabul edilmedi | Güncel kampanyalı ürün, seçilmiş beden ve `checkout.flo.com.tr` sepet HTML’i |
| 14 | Yalı Spor | Güncel kesin sepette fiyat kanıtı bulunamadı | Kampanyalı ürün ve ürün eklenmiş sepet HTML’i |
| 15 | Kaptan Spor | Güncel kesin sepette fiyat kanıtı bulunamadı | Kampanyalı ürün ve ürün eklenmiş sepet HTML’i |
| 16 | SPX | Test edilen ürün bağlantısında canlı sepet metni görünmedi; eski indeks sonucu güncel kabul edilmedi | Güncel kampanyalı ürün ve ürün eklenmiş sepet HTML’i |
| 17 | Kutupayısı | Güncel kesin sepette fiyat kanıtı bulunamadı | Kampanyalı ürün ve ürün eklenmiş sepet HTML’i |
| 18 | Hepsiburada | Güncel kesin sepette fiyat kanıtı bulunamadı | Kampanyalı ürün, seçilmiş varyant ve ürün eklenmiş sepet HTML’i |
| 19 | Amazon Türkiye | Güncel kesin sepette fiyat kanıtı bulunamadı | Kampanyalı ürün ve ürün eklenmiş sepet HTML’i; kupon uygulanıyorsa kupon durumu belirtilmeli |
| 20 | Skechers Türkiye | Güncel kesin sepette fiyat kanıtı bulunamadı | Kampanyalı ürün, seçilmiş numara ve sepet HTML’i |
| 21 | Brooks Türkiye | Güncel kesin sepette fiyat kanıtı bulunamadı | Kampanyalı ürün, seçilmiş numara ve sepet HTML’i |
| 22 | Salomon Türkiye | Güncel kesin sepette fiyat kanıtı bulunamadı | Kampanyalı ürün, seçilmiş numara ve sepet HTML’i |
| 23 | The North Face Türkiye | Test edilen canlı ayakkabı sayfasında görünür sepet metni yoktu; eski kod kampanyası güncel kabul edilmedi | Güncel kampanyalı ürün ve ürün eklenmiş sepet HTML’i |

## Öncelikli HTML toplama sırası

En yüksek kullanım ve doğrulama değeri için aşağıdaki sıra önerilir:

1. Hepsiburada
2. Amazon Türkiye
3. Sportive — aktif sepette indirimli bir ürün
4. SuperStep
5. FLO
6. ASICS Türkiye
7. Columbia Türkiye — 1, 2 ve 3 ürün kademeleri
8. Sneaks Up — kampanyaya uygun 45+ beden
9. Barçın — iki uygun ürün
10. Kalan resmi mağazalar ve spor perakendecileri

## Her mağaza için gönderilmesi gereken dosyalar

Mümkünse her mağaza için üç ayrı HTML gönderilmelidir:

1. `magaza_urun.html` — kampanya görülen ürün sayfası.
2. `magaza_varyant_secili.html` — beden/numara/renk seçildikten sonraki sayfa.
3. `magaza_sepet.html` — aynı ürün sepete eklendikten sonraki sepet sayfası.

Dosyalarla birlikte kısa bir metin dosyasında aşağıdakiler belirtilmelidir:

- Ürün bağlantısı
- Seçilen beden, numara veya renk
- Üyelik açık mı kapalı mı
- Kupon kodu uygulanmış mı
- Mobil uygulama veya web sitesi kullanılmış mı
- Sepette kaç ürün bulunduğu
- Görülmesi beklenen normal fiyat ve sepette fiyat

## Güvenlik ve veri temizliği

HTML dosyaları gönderilmeden önce aşağıdaki bilgiler temizlenmelidir:

- ad, soyad, telefon ve e-posta,
- açık adres ve teslimat bilgileri,
- oturum belirteçleri ve çerez değerleri,
- üyelik numarası,
- ödeme kartı bilgileri,
- ödeme ve sipariş tamamlama adımına ait içerikler.

Sepet sayfası yeterlidir; ödeme veya sipariş oluşturma aşaması gönderilmemelidir.

## Bu liste nasıl kapanacak?

Bir mağazaya ait güvenilir HTML geldiğinde:

1. Normal fiyat ve sepet fiyatı ayrı alanlarda doğrulanır.
2. Kampanya koşulları sınıflandırılır.
3. Gerekirse mağazaya özel seçici eklenir.
4. HTML kişisel verilerden arındırılarak kalıcı test örneğine dönüştürülür.
5. Motor testi eklenir ve tam test paketi yeniden çalıştırılır.
6. Kesin kanıt sağlanırsa mağaza bu listeden çıkarılır.

## Referans

Bu liste, `TUM_MAGAZALAR_SEPET_FIYATI_UYGULAMA_VE_DOGRULAMA_RAPORU_2026-07-18.md` raporundaki 27 mağaza matrisi ve 18 Temmuz 2026 tarihli canlı/yerel doğrulama sonuçlarından türetilmiştir.
