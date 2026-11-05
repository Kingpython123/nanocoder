"""CI 修复的演示仓库：一个小的发票模块，里面有一个 bug。"""

from decimal import ROUND_HALF_UP, Decimal


def line_total(unit_price: str, quantity: int, discount_percent: int = 0) -> Decimal:
    """一行的金额，折扣后按分四舍五入。折扣必须在 0 到 100 之间，否则抛 ValueError。"""
    if not 0 <= discount_percent <= 100:
        raise ValueError(f"discount out of range: {discount_percent}")
    gross = Decimal(unit_price) * quantity
    discounted = gross * (100 - discount_percent) / 100
    return discounted.quantize(Decimal("0.01"))


def invoice_total(lines: list[tuple[str, int, int]]) -> Decimal:
    return sum((line_total(*line) for line in lines), Decimal("0.00"))


__all__ = ["ROUND_HALF_UP", "invoice_total", "line_total"]
