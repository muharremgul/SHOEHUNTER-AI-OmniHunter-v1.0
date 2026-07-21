from core.database import db
from models.alert import Alert
from models.product import Product
from models.product_listing import ProductListing
from models.watchlist import WatchList


class WatchService:
    @staticmethod
    def normalize_size(size: str) -> str:
        return str(size).strip().replace(",", ".")

    @staticmethod
    def price_matches(listing: ProductListing, rule: WatchList) -> bool:
        if rule.target_price is None:
            return False

        if listing.last_price is None:
            return False

        return listing.last_price <= rule.target_price

    @staticmethod
    def duplicate_alert_exists(rule: WatchList, listing: ProductListing) -> bool:
        return Alert.query.filter_by(
            watch_rule_id=rule.id,
            listing_id=listing.id,
            is_read=False,
        ).first() is not None

    @staticmethod
    def evaluate_product(product_id: int):
        product = Product.query.get(product_id)
        if not product:
            return []

        rules = WatchList.query.filter_by(product_id=product.id, enabled=True).all()
        listings = ProductListing.query.filter_by(product_id=product.id, active=True).all()

        created_alerts = []

        for rule in rules:
            for listing in listings:
                if not WatchService.price_matches(listing, rule):
                    continue

                if WatchService.duplicate_alert_exists(rule, listing):
                    continue

                price_text = f"{listing.last_price:.2f} TL"
                target_text = f"{rule.target_price:.2f} TL"

                title = f"{product.display_name} hedef fiyata düştü"
                message = (
                    f"{product.display_name} {listing.store.name} mağazasında hedef fiyata ulaştı. "
                    f"Güncel fiyat: {price_text}. Hedef: {target_text}. "
                    f"Not: Bu sürüm stoktan bağımsız fiyat uyarısı üretir."
                )

                alert = Alert(
                    product_id=product.id,
                    listing_id=listing.id,
                    watch_rule_id=rule.id,
                    level="SUCCESS",
                    title=title,
                    message=message,
                    price=listing.last_price,
                    target_price=rule.target_price,
                    size=rule.size,
                    is_read=False,
                )

                db.session.add(alert)
                created_alerts.append(alert)

        return created_alerts
