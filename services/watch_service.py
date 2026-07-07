from datetime import datetime
from core.database import db
from models import Product, WatchList, ProductListing, Alert

class WatchService:
    @staticmethod
    def normalize_size(size_str: str) -> str:
        """Kullanıcının girdiği bedeni, siteden gelen bedenle eşleşebilecek standarda getirir."""
        if not size_str:
            return "-"
        return size_str.replace(",", ".").strip().upper()

    @staticmethod
    def evaluate_product(product_id: int):
        """Ürünün aktif mağaza linklerini ve aktif fiyat kurallarını karşılaştırır."""
        product = Product.query.get(product_id)
        if not product:
            return []

        active_rules = WatchList.query.filter_by(product_id=product_id, enabled=True).all()
        if not active_rules:
            return []

        active_listings = ProductListing.query.filter_by(product_id=product_id, active=True).all()
        if not active_listings:
            return []

        alerts_created = []

        for rule in active_rules:
            for listing in active_listings:
                current_price = listing.last_price

                # Fiyat henüz çekilmemişse veya kural fiyatından yüksekse atla
                if current_price is None or rule.target_price is None or current_price > rule.target_price:
                    continue

                # ==========================================
                # YENİ: ZEKİ BEDEN VE STOK KONTROLÜ!
                # ==========================================
                is_stock_valid = False
                matched_size = ""

                # Eğer kuralda özel bir beden belirtilmişse (örn: "42.5")
                if rule.size and rule.size != "-":
                    rule_size_norm = WatchService.normalize_size(rule.size)

                    # Listing'den çektiğimiz JSON beden listesinde ara
                    if listing.sizes:
                        for s in listing.sizes:
                            site_size_norm = WatchService.normalize_size(s.get("name", ""))
                            # Hem beden eşleşmeli HEM DE stokta olmalı!
                            if rule_size_norm == site_size_norm:
                                if s.get("in_stock") == True:
                                    is_stock_valid = True
                                    matched_size = s.get("name")
                                break # Bedeni bulduk (stokta olsa da olmasa da), aramayı bitir
                else:
                    # Kuralda beden belirtilmemişse (Herhangi bir beden olur)
                    # En az 1 tane stokta olan beden varsa geçerli say
                    if listing.sizes:
                        if any(s.get("in_stock") == True for s in listing.sizes):
                            is_stock_valid = True
                            matched_size = "Herhangi Bir Beden"
                    else:
                        # Eğer site beden desteklemiyorsa (eski tip site) fiyatı kabul et
                        is_stock_valid = True
                        matched_size = "Beden Bilgisi Yok"

                # Eğer stok geçerli değilse alarm ÜRETME!
                if not is_stock_valid:
                    continue

                # Aynı uyarıyı defalarca atmamak için (Cooldown kontrolü - 24 Saat)
                existing_alert = Alert.query.filter_by(
                    watch_rule_id=rule.id,
                    listing_id=listing.id
                ).order_by(Alert.created_at.desc()).first()

                if existing_alert:
                    hours_since_last = (datetime.now() - existing_alert.created_at).total_seconds() / 3600
                    if hours_since_last < 24:
                        continue

                # Kural da tutuyor, STOK da var! Alarmı bas!
                alert = Alert(
                    product_id=product.id,
                    watch_rule_id=rule.id,
                    listing_id=listing.id,
                    price=current_price,
                    target_price=rule.target_price,
                    title=f"STOKTA! {product.display_name} Hedef Fiyata Düştü",
                    message=f"Beden: {matched_size} | {product.display_name}, {listing.store.name} mağazasında hedef fiyata ulaştı. Güncel fiyat: {current_price:.2f} TL. Hedef: {rule.target_price:.2f} TL.",
                )
                db.session.add(alert)
                alerts_created.append(alert)

        return alerts_created
