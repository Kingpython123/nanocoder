from .store import Store


def total_value(store: Store) -> float:
    """Total value of all stock on hand."""
    return round(sum(item.price * item.qty for item in store.items.values()), 2)
