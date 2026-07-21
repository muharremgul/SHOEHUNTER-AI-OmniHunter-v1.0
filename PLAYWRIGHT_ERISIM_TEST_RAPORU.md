# Playwright Erişim Testi Raporu

**Tarih:** 20 Temmuz 2026  
**Kapsam:** Decathlon Türkiye ve Adidas Türkiye arama sayfaları  
**Yöntem:** Standart Playwright/Chromium, tek deneme, eş zamanlı çalıştırma

## Sonuç özeti

| Mağaza | Test adresi | Erişim sonucu | HTML boyutu | Ayrıştırılan ürün | Değerlendirme |
|---|---|---:|---:|---:|---|
| Decathlon | `https://www.decathlon.com.tr/search?Ntt=kalenji` | Değişken | 652.719 bayta kadar | 0 | İlk standart tarayıcı denemelerinde sayfa oluştu; sonraki kontrolde `HTTP 403` alındı. Erişim kararlı değil. |
| Adidas | `https://www.adidas.com.tr/tr/search?q=ultraboost` | Engellendi | 0 bayt | 0 | Ana belge `HTTP 403` döndürdü; yeniden deneme veya koruma aşma uygulanmadı. |

## Uygulanan tanılama

- `backend/browser_access_diagnostic.py` eklendi.
- Araç Decathlon ve Adidas motorlarını standart Playwright ile test ediyor.
- Sonucu `accessible`, `blocked` veya `error` olarak sınıflandırıyor.
- HTTP `401`, `403`, `429` ve CAPTCHA/erişim meydan okuması durumlarını engel olarak raporluyor.
- Erişilebilen sayfada HTML boyutunu ve ayrıştırılan ürün sayısını bildiriyor.
- Tanılama her mağaza için yalnızca bir tarayıcı isteği yapıyor.

## Bilinçli olarak uygulanmayan maddeler

Aşağıdaki yöntemler kullanılmadı:

- `playwright-stealth`
- `--disable-blink-features=AutomationControlled`
- Tarayıcı parmak izi veya otomasyon kimliği gizleme
- Proxy/kimlik rotasyonu
- CAPTCHA çözme veya erişim korumasını atlatma

Bu nedenle `requirements.txt` ve çekirdek `browser_runtime.py` dosyalarına stealth bağımlılığı eklenmedi.

## Doğrulama

Tanılama aracı için üç otomatik kontrol eklendi:

1. Açık sayfanın stealth olmadan erişilebilir raporlanması.
2. `HTTP 403` yanıtının tek denemeden sonra engel olarak raporlanması.
3. HTTP 200 içinde gelen CAPTCHA/erişim sayfasının ürün sayfası sayılmaması.

## Teknik çıkarım

Decathlon'un kaydedilmiş gerçek ürün HTML'sinde `__DKT` gömülü verisi bulundu ve motor bu yapıyı okuyacak şekilde güncellendi. Verilen `mc=8758966` modelinde fiyat 2.890 TL, `S` ve `M` stokta, `2XL` stok dışı olarak doğrulandı. Eski ayrıştırıcının önerilen başka ürünlerden topladığı ilgisiz bedenler artık mevcut modele eklenmiyor.

Motor, Decathlon için standart Playwright havuzunu kullanacak şekilde ayarlandı. Sayfa normal tarayıcıya açılırsa `__DKT` verisi ayrıştırılır; HTTP 403 veya CAPTCHA gelirse istek engelli olarak sonlandırılır.

Adidas için bu testte kullanılabilir sayfa verisi elde edilemedi. Resmî/izinli veri kaynağı, kaydedilmiş HTML veya kullanıcı tarafından sağlanan sayfa içeriği olmadan motorun canlı veri çıkarması doğrulanamaz.
