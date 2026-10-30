"""Discounts / coupons. The rules are documented in docs/DISCOUNTS.md."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from .money import round_money, to_decimal

KINDS = ("percent", "fixed")


@dataclass(frozen=True)
class Discount:
    kind: str  # "percent" or "fixed"
    value: Decimal
    code: str = ""

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"unknown discount kind {self.kind!r}")
        value = to_decimal(self.value)
        object.__setattr__(self, "value", value)
        if value < 0:
            raise ValueError("discount value must not be negative")
        if self.kind == "percent" and value > 100:
            raise ValueError("percentage discount must be between 0 and 100")

    @classmethod
    def percent(cls, value: object, code: str = "") -> "Discount":
        return cls("percent", to_decimal(value), code)

    @classmethod
    def fixed(cls, value: object, code: str = "") -> "Discount":
        return cls("fixed", to_decimal(value), code)


def apply_discounts(amount: object, discounts: Iterable[Discount]) -> Decimal:
    """Apply discounts to `amount`."""
    result = to_decimal(amount)
    discounts = list(discounts)
    percents = [d for d in discounts if d.kind == "percent"]
    fixed = [d for d in discounts if d.kind == "fixed"]
    total_percent = sum((d.value for d in percents), Decimal(0))
    result -= result * total_percent / 100
    for d in fixed:
        result -= d.value
    return round_money(max(result, Decimal(0)))
