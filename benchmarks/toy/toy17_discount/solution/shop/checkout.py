from .pricing import apply_discount


def cart_total(lines: list[tuple[float, int]], percent: float = 0) -> float:
    """Total for (unit_price, quantity) lines with an order-wide percentage discount."""
    subtotal = sum(price * qty for price, qty in lines)
    return apply_discount(subtotal, percent)
