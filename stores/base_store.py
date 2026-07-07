from abc import ABC, abstractmethod


class BaseStore(ABC):
    name = "BaseStore"

    @abstractmethod
    def search(self, query: str):
        raise NotImplementedError

    @abstractmethod
    def get_product_data(self, url: str):
        raise NotImplementedError
