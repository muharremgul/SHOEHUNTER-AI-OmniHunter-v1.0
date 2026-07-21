from core.database import db


class WatchList(db.Model):
    __tablename__ = "watchlist"

    id = db.Column(db.Integer, primary_key=True)

    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)

    size = db.Column(db.String(20), nullable=False)
    target_price = db.Column(db.Float)
    enabled = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, server_default=db.func.now())

    product = db.relationship("Product", back_populates="watch_items")

    def __repr__(self):
        return f"<WatchList product={self.product_id} size={self.size}>"
