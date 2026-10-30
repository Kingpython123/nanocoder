"""Plain-text receivables report in a single base currency (rules: README, "Reports")."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Iterable

from .currency import Converter
from .invoice import Invoice
from .money import ZERO, format_money


def _natural_key(number: str) -> tuple:
    parts = re.split(r"(\d+)", number.casefold())
    return ([int(p) if p.isdigit() else p for p in parts], number)


def report_rows(
    invoices: Iterable[Invoice], converter: Converter, base_currency: str = "EUR"
) -> list[tuple[str, Decimal, Decimal]]:
    """(number, amount in invoice currency, amount in base currency) per invoice."""
    rows = []
    for inv in sorted(invoices, key=lambda i: _natural_key(i.number)):
        base_amount = converter.convert(inv.total, inv.currency, base_currency)
        rows.append((inv.number, inv.total, base_amount))
    return rows


def report_total(invoices: Iterable[Invoice], converter: Converter, base_currency: str = "EUR") -> Decimal:
    return sum((converter.convert(inv.total, inv.currency, base_currency) for inv in invoices), ZERO)


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
