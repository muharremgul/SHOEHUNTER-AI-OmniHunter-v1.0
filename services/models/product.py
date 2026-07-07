from core.database import db


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    brand = db.Column(db.String(50), nullable=False)
    model = db.Column(db.String(120), nullable=False)
    gender = db.Column(db.String(20))
    category = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    watch_items = db.relationship(
        "WatchList",
        back_populates="product",
        cascade="all, delete-orphan",
    )
    prices = db.relationship(
        "PriceHistory",
        back_populates="product",
        cascade="all, delete-orphan",
    )
    listings = db.relationship(
        "ProductListing",
        back_populates="product",
        cascade="all, delete-orphan",
    )

    @property
    def display_name(self):
        return f"{self.brand} {self.model}".strip()

    def __repr__(self):
        return f"<Product {self.display_name}>"
