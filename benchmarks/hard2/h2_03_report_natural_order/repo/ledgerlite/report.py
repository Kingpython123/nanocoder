"""Plain-text receivables report in a single base currency (rules: README, "Reports")."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Iterable

from .currency import Converter
from .invoice import Invoice
from .money import ZERO, format_money


def report_rows(
    invoices: Iterable[Invoice], converter: Converter, base_currency: str = "EUR"
) -> list[tuple[str, Decimal, Decimal]]:
    """(number, amount in invoice currency, amount in base currency) per invoice."""
    rows = []
    for inv in sorted(invoices, key=lambda i: i.number):
        base_amount = converter.convert(inv.total, inv.currency, base_currency)
        rows.append((inv.number, inv.total, base_amount))
    return rows


def report_total(invoices: Iterable[Invoice], converter: Converter, base_currency: str = "EUR") -> Decimal:
    sums: defaultdict[str, Decimal] = defaultdict(lambda: ZERO)
    for inv in invoices:
        sums[inv.currency.upper()] += inv.total
    return sum((converter.convert(amount, cur, base_currency) for cur, amount in sorted(sums.items())), ZERO)


def render_report(invoices: Iterable[Invoice], converter: Converter, base_currency: str = "EUR") -> str:
    invoices = list(invoices)
    rows = report_rows(invoices, converter, base_currency)
    currency_of = {inv.number: inv.currency for inv in invoices}
    lines = [f"{'Invoice':<10} {'Amount':>18} {'In ' + base_currency:>18}"]
    for number, amount, base_amount in rows:
        lines.append(
            f"{number:<10} {format_money(amount, currency_of[number]):>18} {format_money(base_amount, base_currency):>18}"
        )
    total = report_total(invoices, converter, base_currency)
    lines.append(f"{'TOTAL':<10} {'':>18} {format_money(total, base_currency):>18}")
    return "\n".join(lines)
