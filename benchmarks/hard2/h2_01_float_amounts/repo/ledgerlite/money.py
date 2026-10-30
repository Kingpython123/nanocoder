"""Money helpers. All amounts are Decimal."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def to_decimal(value: object) -> Decimal:
    """Convert int / str / float / Decimal to Decimal. Raises ValueError on garbage."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise ValueError(f"not a valid amount: {value!r}")
    if isinstance(value, float):
        return Decimal(value)
    try:
        return Decimal(str(value).strip())
    except InvalidOperation:
        raise ValueError(f"not a valid amount: {value!r}") from None


def round_money(value: object) -> Decimal:
    """Round to cents."""
    return to_decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def format_money(value: object, currency: str = "EUR") -> str:
    """'1,234.50 EUR' style formatting; negative amounts get a leading minus."""
    amount = round_money(value)
    sign = "-" if amount < 0 else ""
    return f"{sign}{abs(amount):,.2f} {currency}"
