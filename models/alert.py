from core.database import db


class Alert(db.Model):
    __tablename__ = "alerts"

    id = db.Column(db.Integer, primary_key=True)

    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    listing_id = db.Column(db.Integer, db.ForeignKey("product_listings.id"), nullable=True)
    watch_rule_id = db.Column(db.Integer, db.ForeignKey("watchlist.id"), nullable=True)

    level = db.Column(db.String(20), default="INFO")
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)

    price = db.Column(db.Float)
    target_price = db.Column(db.Float)
    size = db.Column(db.String(20))

    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    product = db.relationship("Product")
    listing = db.relationship("ProductListing")
    watch_rule = db.relationship("WatchList")

    def __repr__(self):
        return f"<Alert {self.title}>"
