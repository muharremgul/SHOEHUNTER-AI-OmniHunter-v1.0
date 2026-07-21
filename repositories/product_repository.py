from core.database import db
from models.product import Product


class ProductRepository:
    @staticmethod
    def split_product_name(product_name: str):
        parts = product_name.strip().split(maxsplit=1)

        if not parts:
            return "Bilinmeyen", "Model"

        brand = parts[0]
        model = parts[1] if len(parts) > 1 else "Model"
        return brand, model

    @staticmethod
    def create_from_name(product_name: str, gender=None, category="Ayakkabı"):
        brand, model = ProductRepository.split_product_name(product_name)

        product = Product(
            brand=brand,
            model=model,
            gender=gender,
            category=category,
        )
        db.session.add(product)
        db.session.commit()
        return product

    @staticmethod
    def count():
        return Product.query.count()
