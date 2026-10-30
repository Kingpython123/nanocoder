"""VAT rules (see README)."""

from __future__ import annotations

from decimal import Decimal

from .money import ZERO, round_money, to_decimal

EXEMPT_CATEGORIES = frozenset({"food", "books"})
REGION_RATES = {
    "DE": Decimal("0.19"),
    "FR": Decimal("0.20"),
    "NL": Decimal("0.21"),
}


def normalize_category(category: str | None) -> str:
    return (category or "").strip().lower()


def is_exempt(category: str | None) -> bool:
    category = normalize_category(category)
    return any(exempt in category for exempt in EXEMPT_CATEGORIES)


def tax_rate(region: str) -> Decimal:
    try:
        return REGION_RATES[region.strip().upper()]
    except KeyError:
        raise ValueError(f"unknown tax region {region!r}") from None


def line_tax(line_total: object, category: str | None, region: str) -> Decimal:
    if is_exempt(category):
        return ZERO
    return round_money(to_decimal(line_total) * tax_rate(region))
