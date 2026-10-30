"""Invoices and line items."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from .discounts import Discount, apply_discounts
from .money import ZERO, round_money, to_decimal
from .tax import line_tax


@dataclass
class LineItem:
    sku: str
    quantity: int
    unit_price: Decimal
    category: str = "general"
    description: str = ""

    def __post_init__(self) -> None:
        self.unit_price = to_decimal(self.unit_price)
        if self.quantity < 0:
            raise ValueError("quantity must not be negative")

    @property
    def total(self) -> Decimal:
        return round_money(self.unit_price * self.quantity)


@dataclass
class Invoice:
    number: str
    region: str = "DE"
    currency: str = "EUR"
    lines: list[LineItem] = field(default_factory=list)
    discounts: list[Discount] = field(default_factory=list)
    issued: date | None = None
    due: date | None = None
    paid: bool = False

    def add_line(
        self, sku: str, quantity: int, unit_price: object, category: str = "general", description: str = ""
    ) -> LineItem:
        line = LineItem(sku, quantity, to_decimal(unit_price), category, description)
        self.lines.append(line)
        return line

    @property
    def subtotal(self) -> Decimal:
        return sum((line.total for line in self.lines), ZERO)

    @property
    def tax(self) -> Decimal:
        return sum((line_tax(line.total, line.category, self.region) for line in self.lines), ZERO)

    @property
    def gross(self) -> Decimal:
        return self.subtotal + self.tax

    @property
    def total(self) -> Decimal:
        """Amount due: gross minus discounts."""
        return apply_discounts(self.gross, self.discounts)
