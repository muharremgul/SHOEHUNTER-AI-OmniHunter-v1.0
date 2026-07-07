from datetime import datetime
from core.database import db
from models import ProductListing, PriceHistory, Alert
from services.watch_service import WatchService
from services.telegram_service import TelegramService
from stores.intersport import IntersportStore
import json

class BatchCheckService:
    @staticmethod
    def get_stats():
        active_listing_count = ProductListing.query.filter_by(active=True).count()
        checked_listing_count = ProductListing.query.filter(ProductListing.last_checked_at.isnot(None)).count()
        unchecked_listing_count = ProductListing.query.filter(ProductListing.last_checked_at.is_(None)).count()
        unread_alert_count = Alert.query.filter_by(is_read=False).count()

        return {
            "active_listing_count": active_listing_count,
            "checked_listing_count": checked_listing_count,
            "unchecked_listing_count": unchecked_listing_count,
            "unread_alert_count": unread_alert_count,
        }

    @staticmethod
    def run_all_active_checks():
        listings = ProductListing.query.filter_by(active=True).order_by(ProductListing.created_at.asc()).all()

        results = {
            "started_at": datetime.now(),
            "finished_at": None,
            "checked": 0,
            "skipped": 0,
            "errors": 0,
            "alerts_created": 0,
            "alerts_sent": 0,
            "items": [],
        }

        for listing in listings:
            item_result = BatchCheckService.check_listing(listing)
            results["items"].append(item_result)

            if item_result["status"] == "checked":
                results["checked"] += 1
                results["alerts_created"] += item_result.get("alerts_created", 0)
                results["alerts_sent"] += item_result.get("alerts_sent", 0)
            elif item_result["status"] == "error":
                results["errors"] += 1
            else:
                results["skipped"] += 1

        results["finished_at"] = datetime.now()
        return results

    @staticmethod
    def check_listing(listing):
        product_name = listing.product.display_name if listing.product else "Ürün"
        store_name = listing.store.name if listing.store else "Mağaza"

        result = {
            "listing_id": listing.id,
            "product_name": product_name,
            "store_name": store_name,
            "status": "pending",
            "price": None,
            "alerts_created": 0,
            "alerts_sent": 0,
            "message": "",
        }
        
        try:
            if not listing.store:
                result["status"] = "skipped"
                return result

            store_lower = store_name.lower()
            if "intersport" in store_lower:
                scraper = IntersportStore()
            elif "decathlon" in store_lower:
                from stores.decathlon import DecathlonStore
                scraper = DecathlonStore()
            elif "adidas" in store_lower:
                from stores.adidas import AdidasStore
                scraper = AdidasStore()
            else:
                result["status"] = "skipped"
                return result

            data = scraper.get_product_data(listing.url)

            if not data or data.get("current_price") is None:
                result["status"] = "error"
                result["message"] = "Fiyat veya beden verisi çekilemedi."
                return result

            # Bedenleri veritabanına sorunsuz kaydetme bölümü
            if hasattr(listing, 'update_from_scrape'):
                listing.update_from_scrape(data)
            else:
                listing.last_price = data.get("current_price")
                if "sizes" in data:
                    try:
                        listing.sizes = data["sizes"]
                    except:
                        pass
            
            listing.last_checked_at = datetime.now()

            price = PriceHistory(
                product_id=listing.product_id,
                store_id=listing.store_id,
                size=None,
                price=data["current_price"],
                old_price=data.get("old_price"),
                in_stock=data.get("stock_count", 0) > 0,
            )
            db.session.add(price)
            db.session.commit()

            alerts = WatchService.evaluate_product(listing.product_id)
            db.session.commit()
            telegram_result = TelegramService.send_alerts(alerts)

            sent_count = telegram_result.get("count", len(alerts)) if telegram_result.get("sent") else 0

            result["status"] = "checked"
            result["price"] = listing.last_price
            result["alerts_created"] = len(alerts)
            result["alerts_sent"] = sent_count
            result["message"] = "Başarıyla güncellendi."

            return result

        except Exception as exc:
            db.session.rollback()
            result["status"] = "error"
            result["message"] = str(exc)
            return result
