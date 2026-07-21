import json
from datetime import datetime

from core.database import db


class ProductListing(db.Model):
    __tablename__ = "product_listings"

    id = db.Column(db.Integer, primary_key=True)

    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=False)

    url = db.Column(db.String(1000), nullable=False)
    active = db.Column(db.Boolean, default=True)
    last_title = db.Column(db.String(300))
    last_price = db.Column(db.Float)
    last_old_price = db.Column(db.Float)
    last_sizes_json = db.Column(db.Text)
    last_stock_count = db.Column(db.Integer, default=0)
    last_checked_at = db.Column(db.DateTime)

    created_at = db.Column(db.DateTime, server_default=db.func.now())

    product = db.relationship("Product", back_populates="listings")
    store = db.relationship("Store", back_populates="listings")

    @property
    def sizes(self):
        if not self.last_sizes_json:
            return []

        try:
            return json.loads(self.last_sizes_json)
        except json.JSONDecodeError:
            return []

    def update_from_scrape(self, result):
        self.last_title = result.get("title")
        self.last_price = result.get("current_price")
        self.last_old_price = result.get("old_price")
        self.last_stock_count = result.get("stock_count", 0)
        self.last_sizes_json = json.dumps(result.get("sizes", []), ensure_ascii=False)
        self.last_checked_at = datetime.utcnow()

    def __repr__(self):
        return f"<ProductListing product={self.product_id} store={self.store_id}>"
