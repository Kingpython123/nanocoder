"""Plain-text receivables report in a single base currency."""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from .currency import Converter
from .invoice import Invoice
from .money import ZERO, format_money


def report_rows(
    invoices: Iterable[Invoice], converter: Converter, base_currency: str = "EUR"
) -> list[tuple[str, Decimal, Decimal]]:
    """(number, amount in invoice currency, amount in base currency), sorted by number."""
    rows = []
    for inv in sorted(invoices, key=lambda i: i.number):
        base_amount = converter.convert(inv.total, base_currency, inv.currency)
        rows.append((inv.number, inv.total, base_amount))
    return rows


def render_report(invoices: Iterable[Invoice], converter: Converter, base_currency: str = "EUR") -> str:
    invoices = list(invoices)
    rows = report_rows(invoices, converter, base_currency)
    currency_of = {inv.number: inv.currency for inv in invoices}
    lines = [f"{'Invoice':<10} {'Amount':>18} {'In ' + base_currency:>18}"]
    grand = ZERO
    for number, amount, base_amount in rows:
        grand += base_amount
        lines.append(
            f"{number:<10} {format_money(amount, currency_of[number]):>18} {format_money(base_amount, base_currency):>18}"
        )
    lines.append(f"{'TOTAL':<10} {'':>18} {format_money(grand, base_currency):>18}")
    return "\n".join(lines)
