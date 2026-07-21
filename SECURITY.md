# Güvenlik

## Desteklenen sürüm

Güvenlik düzeltmeleri yalnızca en son `VERSION.txt` sürümünde tutulur.

## Bildirim

Bir güvenlik sorunu bulursanız ayrıntıları herkese açık issue içinde paylaşmayın. Depo sahibine GitHub üzerinden özel güvenlik bildirimi gönderin. Bildirime etkilenen rota, yeniden üretme adımları ve olası etkiyi ekleyin; gerçek token, parola veya kişisel veri eklemeyin.

## Kurulum ilkeleri

- `backend/.env` ve `.shoehunter.key` Git'e eklenmemelidir.
- Yönetici parolası en az 12 karakter, büyük/küçük harf ve rakam içermelidir.
- İnternet üzerinden yayınlamada `COOKIE_SECURE=true` ve HTTPS zorunludur.
- `CORS_ORIGINS` yalnızca gerçek arayüz adreslerini içermelidir.
- Telegram ve AI anahtarları düzenli aralıklarla yenilenmelidir.
- Yedekler şifrelenmiş bir diskte saklanmalı ve geri yükleme denemesi yapılmalıdır.

## Tarama sınırları

Uygulama yalnızca izin verilen mağaza alan adlarında, düşük hızda ve kamusal ürün sayfalarında çalışır. CAPTCHA çözme, erişim kontrolü atlatma, cihaz kimliği sahteleme veya özel oturum taklidi proje kapsamı dışındadır.
