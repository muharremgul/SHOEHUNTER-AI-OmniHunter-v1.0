from repositories.product_repository import ProductRepository


class ProductService:
    @staticmethod
    def add_product_from_search_text(text: str, gender=None, category="Ayakkabı"):
        return ProductRepository.create_from_name(
            product_name=text,
            gender=gender,
            category=category,
        )
