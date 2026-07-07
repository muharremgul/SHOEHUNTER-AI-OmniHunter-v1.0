from core.database import db


class Store(db.Model):
    __tablename__ = "stores"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    url = db.Column(db.String(300))
    enabled = db.Column(db.Boolean, default=True)

    prices = db.relationship(
        "PriceHistory",
        back_populates="store",
        cascade="all, delete-orphan",
    )
    listings = db.relationship(
        "ProductListing",
        back_populates="store",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Store {self.name}>"
