"""Receivables aging: how long unpaid invoices have been overdue."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Iterable

from .invoice import Invoice
from .money import ZERO

BUCKETS = ("current", "1-30", "31-60", "61-90", "90+")


def days_overdue(invoice: Invoice, today: date) -> int:
    if invoice.is_settled or invoice.due is None:
        return 0
    return max((today - invoice.due).days, 0)


def bucket_for(days: int) -> str:
    if days <= 0:
        return "current"
    if days <= 30:
        return "1-30"
    if days <= 60:
        return "31-60"
    if days <= 90:
        return "61-90"
    return "90+"


def aging_summary(invoices: Iterable[Invoice], today: date) -> dict[str, Decimal]:
    """Outstanding amount per aging bucket (settled invoices are left out)."""
    totals = {b: ZERO for b in BUCKETS}
    for inv in invoices:
        if inv.is_settled:
            continue
        totals[bucket_for(days_overdue(inv, today))] += inv.outstanding
    return totals


def overdue_list(invoices: Iterable[Invoice], today: date) -> list[tuple[str, int, str]]:
    """(invoice number, days overdue, bucket) for overdue invoices, most overdue first.

    Kept separate from aging_summary because the dunning export needs the raw days.
    """
    rows = []
    for inv in invoices:
        days = days_overdue(inv, today)
        if days == 0:
            continue
        if days <= 30:
            label = "1-30"
        elif days <= 60:
            label = "31-60"
        elif days <= 90:
            label = "61-90"
        else:
            label = "90+"
        rows.append((inv.number, days, label))
    rows.sort(key=lambda r: (-r[1], r[0]))
    return rows
