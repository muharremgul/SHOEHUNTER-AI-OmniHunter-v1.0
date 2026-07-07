from flask import Flask, render_template, request, redirect, url_for, flash
from config import Config
from core.database import db

# Modeller create_all çalışmadan önce import edilmeli.
from models import Product, Store, WatchList, PriceHistory, ProductListing, Alert
from repositories.product_repository import ProductRepository
from repositories.store_repository import StoreRepository
from stores.intersport import IntersportStore
from services.watch_service import WatchService
from services.settings_service import SettingsService
from services.telegram_service import TelegramService
from services.batch_check_service import BatchCheckService
from services.scheduler_service import SchedulerService

def create_app():
    app = Flask(
        __name__,
        template_folder="web/templates",
        static_folder="web/static",
        static_url_path="/static",
    )
    app.config.from_object(Config)

    db.init_app(app)

    with app.app_context():
        db.create_all()
        StoreRepository.seed_default_stores()

    SchedulerService.start(app)

    @app.route("/")
    def dashboard():
        settings = SettingsService.load()
        telegram_enabled = settings.get("telegram", {}).get("enabled", False)

        stats = {
            "product_count": Product.query.count(),
            "store_count": Store.query.count(),
            "watch_count": WatchList.query.count(),
            "price_count": PriceHistory.query.count(),
            "listing_count": ProductListing.query.count(),
            "alert_count": Alert.query.count(),
            "unread_alert_count": Alert.query.filter_by(is_read=False).count(),
            "telegram_status": "Aktif" if telegram_enabled else "Kapalı",
            "last_check": "-",
            "version": "v0.4.5",
        }
        latest_products = Product.query.order_by(Product.created_at.desc()).limit(5).all()
        latest_listings = ProductListing.query.order_by(ProductListing.created_at.desc()).limit(5).all()
        latest_alerts = Alert.query.order_by(Alert.created_at.desc()).limit(5).all()

        return render_template(
            "dashboards/dashboard.html",
            stats=stats,
            latest_products=latest_products,
            latest_listings=latest_listings,
            latest_alerts=latest_alerts,
        )

    @app.route("/products")
    def products():
        all_products = Product.query.order_by(Product.created_at.desc()).all()
        return render_template("products/index.html", products=all_products)

    @app.route("/products/new", methods=["GET", "POST"])
    def product_new():
        if request.method == "POST":
            product_name = request.form.get("product_name", "").strip()
            gender = request.form.get("gender", "").strip()
            category = request.form.get("category", "").strip()

            if not product_name:
                flash("Ürün adı boş olamaz. Bot bile boşluğu takip edemez, şimdilik.", "danger")
                return redirect(url_for("product_new"))

            product = ProductRepository.create_from_name(
                product_name=product_name,
                gender=gender or None,
                category=category or "Ayakkabı",
            )
            flash(f"{product.display_name} takip sistemine eklendi.", "success")
            return redirect(url_for("product_detail", product_id=product.id))

        return render_template("products/new.html")

    @app.route("/products/<int:product_id>")
    def product_detail(product_id):
        product = Product.query.get_or_404(product_id)
        listings = ProductListing.query.filter_by(product_id=product.id).order_by(ProductListing.created_at.desc()).all()
        price_history = PriceHistory.query.filter_by(product_id=product.id).order_by(PriceHistory.checked_at.desc()).limit(20).all()
        watch_rules = WatchList.query.filter_by(product_id=product.id).order_by(WatchList.created_at.desc()).all()
        alerts = Alert.query.filter_by(product_id=product.id).order_by(Alert.created_at.desc()).limit(10).all()

        return render_template(
            "products/detail.html",
            product=product,
            listings=listings,
            price_history=price_history,
            watch_rules=watch_rules,
            alerts=alerts,
        )

    @app.route("/products/<int:product_id>/delete", methods=["POST"])
    def product_delete(product_id):
        product = Product.query.get_or_404(product_id)
        name = product.display_name
        db.session.delete(product)
        db.session.commit()
        flash(f"{name} silindi.", "warning")
        return redirect(url_for("products"))

    @app.route("/products/<int:product_id>/listings/new", methods=["GET", "POST"])
    def listing_new(product_id):
        product = Product.query.get_or_404(product_id)
        stores = Store.query.filter_by(enabled=True).order_by(Store.name.asc()).all()

        if request.method == "POST":
            store_id = request.form.get("store_id")
            url = request.form.get("url", "").strip()

            if not store_id or not url:
                flash("Mağaza ve URL zorunlu.", "danger")
                return redirect(url_for("listing_new", product_id=product.id))

            listing = ProductListing(
                product_id=product.id,
                store_id=int(store_id),
                url=url,
                active=True,
            )
            db.session.add(listing)
            db.session.commit()

            flash("Mağaza linki ürüne eklendi.", "success")
            return redirect(url_for("product_detail", product_id=product.id))

        return render_template("products/listing_new.html", product=product, stores=stores)

    @app.route("/listings/<int:listing_id>/delete", methods=["POST"])
    def listing_delete(listing_id):
        listing = ProductListing.query.get_or_404(listing_id)
        product_id = listing.product_id
        db.session.delete(listing)
        db.session.commit()
        flash("Mağaza linki silindi.", "warning")
        return redirect(url_for("product_detail", product_id=product_id))

    @app.route("/products/<int:product_id>/watch-rules/new", methods=["POST"])
    def watch_rule_new(product_id):
        product = Product.query.get_or_404(product_id)

        size = request.form.get("size", "").strip()
        target_price_raw = request.form.get("target_price", "").strip()

        if not target_price_raw:
            flash("Bu sürümde takip fiyat odaklı. Hedef fiyat zorunlu.", "danger")
            return redirect(url_for("product_detail", product_id=product.id))

        try:
            target_price = float(target_price_raw.replace(".", "").replace(",", "."))
        except ValueError:
            flash("Hedef fiyat sayı olmalı.", "danger")
            return redirect(url_for("product_detail", product_id=product.id))

        rule = WatchList(
            product_id=product.id,
            size=WatchService.normalize_size(size) if size else "-",
            target_price=target_price,
            enabled=True,
        )
        db.session.add(rule)
        db.session.commit()

        flash(f"{product.display_name} için {target_price:.2f} TL fiyat takibi eklendi.", "success")
        return redirect(url_for("product_detail", product_id=product.id))

    @app.route("/watch-rules/<int:rule_id>/delete", methods=["POST"])
    def watch_rule_delete(rule_id):
        rule = WatchList.query.get_or_404(rule_id)
        product_id = rule.product_id
        db.session.delete(rule)
        db.session.commit()
        flash("Takip kuralı silindi.", "warning")
        return redirect(url_for("product_detail", product_id=product_id))

    @app.route("/products/<int:product_id>/evaluate", methods=["POST"])
    def product_evaluate(product_id):
        product = Product.query.get_or_404(product_id)
        alerts = WatchService.evaluate_product(product.id)
        db.session.commit()

        telegram_result = TelegramService.send_alerts(alerts)

        if alerts:
            if telegram_result.get("sent"):
                flash(f"{len(alerts)} yeni fiyat uyarısı üretildi ve Telegram'a gönderildi.", "success")
            elif telegram_result.get("skipped"):
                flash(f"{len(alerts)} yeni fiyat uyarısı üretildi. Telegram kapalı olduğu için gönderilmedi.", "warning")
            else:
                flash(f"{len(alerts)} yeni fiyat uyarısı üretildi ama Telegram gönderimi başarısız: {telegram_result.get('error')}", "warning")
        else:
            flash("Şimdilik yeni fiyat uyarısı yok.", "secondary")

        return redirect(url_for("product_detail", product_id=product.id))

    @app.route("/listings/<int:listing_id>/check", methods=["POST"])
    def listing_check(listing_id):
        listing = ProductListing.query.get_or_404(listing_id)
        
        result = BatchCheckService.check_listing(listing)
        
        if result.get("status") == "checked":
            flash(f"Yeni Zeki Motor Başarılı! Fiyat: {result.get('price')} TL. Bedenler güncellendi.", "success")
        else:
            flash(f"Hata: {result.get('message')}", "danger")
            
        return redirect(url_for('product_detail', product_id=listing.product_id))

    # ==========================================
    # KAYIP MENÜ SAYFALARI GERİ EKLENDİ!
    # ==========================================
    @app.route("/stores")
    def stores():
        all_stores = Store.query.order_by(Store.name.asc()).all()
        return render_template("stores/index.html", stores=all_stores)

    @app.route("/alerts")
    def alerts():
        all_alerts = Alert.query.order_by(Alert.created_at.desc()).all()
        return render_template("alerts/index.html", alerts=all_alerts)

    @app.route('/alerts/<int:alert_id>/delete', methods=['POST'])
    def delete_alert(alert_id):
        alert = Alert.query.get_or_404(alert_id)
        db.session.delete(alert)
        db.session.commit()
        return redirect(url_for('alerts'))

    @app.route('/alerts/delete_all', methods=['POST'])
    def delete_all_alerts():
        Alert.query.delete()
        db.session.commit()
        return redirect(url_for('alerts'))

    @app.route("/checks")
    def checks():
        stats = BatchCheckService.get_stats()
        return render_template("checks/index.html", stats=stats, results=None)

    @app.route("/checks/run", methods=["POST"])
    def checks_run():
        results = BatchCheckService.run_all_active_checks()
        stats = BatchCheckService.get_stats()
        return render_template("checks/index.html", stats=stats, results=results)

    @app.route("/ai-search")
    def ai_search():
        return render_template("ai/search.html")

    @app.route("/settings")
    def settings():
        settings_data = SettingsService.load()
        telegram_settings = settings_data.get("telegram", {})
        scheduler_settings = settings_data.get("scheduler", {})
        masked_token = SettingsService.mask_token(telegram_settings.get("bot_token"))
        scheduler_status = SchedulerService.status()
        
        return render_template(
            "settings/settings.html",
            telegram_settings=telegram_settings,
            scheduler_settings=scheduler_settings,
            masked_token=masked_token,
            scheduler_status=scheduler_status
        )

    @app.route("/settings/telegram/save", methods=["POST"])
    def settings_telegram_save():
        enabled = request.form.get("enabled") == "on"
        bot_token = request.form.get("bot_token", "").strip()
        chat_id = request.form.get("chat_id", "").strip()
        SettingsService.update_telegram(enabled, bot_token, chat_id)
        flash("Telegram ayarları kaydedildi.", "success")
        return redirect(url_for("settings"))

    @app.route("/settings/telegram/test", methods=["POST"])
    def settings_telegram_test():
        result = TelegramService.send_test_message()
        if result.get("sent"):
            flash("Test mesajı başarıyla gönderildi!", "success")
        else:
            flash(f"Test mesajı başarısız: {result.get('error', result.get('reason'))}", "danger")
        return redirect(url_for("settings"))

    @app.route("/settings/scheduler/save", methods=["POST"])
    def settings_scheduler_save():
        enabled = request.form.get("enabled") == "on"
        interval_minutes = int(request.form.get("interval_minutes", 1))
        SettingsService.update_scheduler(enabled, interval_minutes)
        flash("Otomatik kontrol ayarları kaydedildi.", "success")
        return redirect(url_for("settings"))


    @app.route('/watch-rules/<int:rule_id>/test', methods=['POST'])
    def watch_rule_test(rule_id):
        try:
            from models import WatchList, ProductListing
        except ImportError:
            from models.watchlist import WatchList
            from models.product_listing import ProductListing
            
        from services.telegram_service import TelegramService
        from flask import flash, redirect, url_for

        rule = WatchList.query.get_or_404(rule_id)
        product = rule.product
        
        listings = ProductListing.query.filter_by(product_id=product.id, active=True).all()
        best_price = float('inf')
        best_listing = None
        
        # Beden karşılaştırmasında virgül/nokta çakışmasını önleyen zeka
        def norm_sz(sz):
            return str(sz).replace(",", ".").strip()
        
        for listing in listings:
            if listing.last_price is None: continue
            
            has_stock = False
            if rule.size and rule.size != "-":
                if hasattr(listing, 'sizes') and listing.sizes:
                    for s in listing.sizes:
                        if (norm_sz(s.get("name")) == norm_sz(rule.size) or norm_sz(s.get("size")) == norm_sz(rule.size)) and s.get("in_stock"):
                            has_stock = True
                            break
            else:
                has_stock = True # Beden belirtilmemişse sadece fiyata bakılır
                
            if has_stock and listing.last_price < best_price:
                best_price = listing.last_price
                best_listing = listing
                
        if not listings:
            flash("Ürüne ait aktif bir mağaza linki yok. Önce 'Şimdi Kontrol Et' yapın.", "warning")
        elif not best_listing:
            if rule.size and rule.size != "-":
                flash(f"Kural Testi: {rule.size} numara hiçbir mağazada stokta bulunamadı!", "warning")
            else:
                flash("Kural Testi: Ürün hiçbir mağazada stokta yok!", "warning")
        elif best_price <= rule.target_price:
            message = (
                f"🧪 <b>KURAL TESTİ BAŞARILI!</b>\n\n"
                f"<b>Ürün:</b> {product.display_name}\n"
                f"<b>Beden:</b> {rule.size if rule.size and rule.size != '-' else 'Fark Etmez'}\n"
                f"<b>Mağaza:</b> {best_listing.store.name}\n"
                f"<b>Fiyat:</b> {best_price} TL (Hedefiniz: {rule.target_price} TL)\n\n"
                f"🛒 <a href='{best_listing.url}'>Hemen Satın Al</a>"
            )
            res = TelegramService.send_message(message)
            if res.get("sent"):
                flash(f"Kural Testi Başarılı! {best_price} TL fiyatla eşleşti. Telegram'a test mesajı atıldı.", "success")
            else:
                flash(f"Kural eşleşti ancak Telegram hatası: {res.get('error')}", "danger")
        else:
            flash(f"Kural Testi: Stok var ancak fiyat hedeften yüksek! Güncel: {best_price} TL, Sizin Hedefiniz: {rule.target_price} TL", "info")
            
        try:
            return redirect(url_for('products.product_detail', product_id=product.id))
        except:
            return redirect(url_for('product_detail', product_id=product.id))

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
