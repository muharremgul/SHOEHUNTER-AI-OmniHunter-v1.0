from core.database import db


class PriceHistory(db.Model):
    __tablename__ = "price_history"

    id = db.Column(db.Integer, primary_key=True)

    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=False)

    size = db.Column(db.String(20))
    price = db.Column(db.Float, nullable=False)
    old_price = db.Column(db.Float)
    in_stock = db.Column(db.Boolean, default=True)

    checked_at = db.Column(db.DateTime, server_default=db.func.now())

    product = db.relationship("Product", back_populates="prices")
    store = db.relationship("Store", back_populates="prices")

    def __repr__(self):
        return f"<PriceHistory product={self.product_id} price={self.price}>"
