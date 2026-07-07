from core.database import db
from models.store import Store


class StoreRepository:
    DEFAULT_STORES = [
        ("Intersport", "https://www.intersport.com.tr"),
        ("Decathlon", "https://www.decathlon.com.tr"),
        ("Adidas Türkiye", "https://www.adidas.com.tr"),
        ("Asics Türkiye", "https://www.asics.com.tr"),
        ("New Balance Türkiye", "https://www.newbalance.com.tr"),
        ("Boyner", "https://www.boyner.com.tr"),
        ("Sportive", "https://www.sportive.com.tr"),
        ("Sneaks Up", "https://www.sneaksup.com"),
        ("Korayspor", "https://www.korayspor.com"),
    ]

    @staticmethod
    def seed_default_stores():
        for name, url in StoreRepository.DEFAULT_STORES:
            exists = Store.query.filter_by(name=name).first()
            if not exists:
                db.session.add(Store(name=name, url=url, enabled=True))

        db.session.commit()

    @staticmethod
    def count():
        return Store.query.count()
