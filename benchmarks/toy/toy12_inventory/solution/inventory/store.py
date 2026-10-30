from .models import InsufficientStock, Item


class Store:
    def __init__(self):
        self.items: dict[str, Item] = {}

    def add(self, sku: str, price: float, qty: int) -> None:
        if sku in self.items:
            self.items[sku].qty += qty
        else:
            self.items[sku] = Item(sku, price, qty)

    def remove(self, sku: str, qty: int) -> None:
        item = self.items[sku]
        if qty > item.qty:
            raise InsufficientStock(f"{sku}: have {item.qty}, need {qty}")
        item.qty -= qty
