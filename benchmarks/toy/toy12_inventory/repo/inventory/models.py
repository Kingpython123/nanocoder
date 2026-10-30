from dataclasses import dataclass


class InsufficientStock(Exception):
    pass


@dataclass
class Item:
    sku: str
    price: float
    qty: int = 0
