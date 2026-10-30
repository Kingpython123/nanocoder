from decimal import Decimal

from ledgerlite import Converter, Invoice, StaticRates
from ledgerlite.report import render_report, report_rows, report_total


def make(number, amount, currency="EUR"):
    inv = Invoice(number, currency=currency)
    inv.add_line("X", 1, amount, "books")
    return inv


def rates():
    return StaticRates({("EUR", "USD"): "1.10", ("EUR", "GBP"): "0.85"})


def test_total_per_currency():
    conv = Converter(rates())
    invoices = [make(f"U{i}", "0.05", "USD") for i in range(3)]
    assert report_total(invoices, conv, "EUR") == Decimal("0.14")


def test_mixed_currencies_total():
    conv = Converter(rates())
    invoices = [make("E1", "1.00"), make("U1", "0.05", "USD"), make("U2", "0.05", "USD"), make("G1", "0.01", "GBP"), make("G2", "0.01", "GBP")]
    # EUR 1.00 + USD 0.10 -> 0.09 + GBP 0.02 -> 0.02
    assert report_total(invoices, conv, "EUR") == Decimal("1.11")


def test_render_total_line():
    conv = Converter(rates())
    text = render_report([make(f"U{i}", "0.05", "USD") for i in range(3)], conv, "EUR")
    assert text.splitlines()[-1].split() == ["TOTAL", "0.14", "EUR"]


def test_rows_still_converted_individually():
    conv = Converter(rates())
    rows = report_rows([make(f"U{i}", "0.05", "USD") for i in range(3)], conv, "EUR")
    assert [r[2] for r in rows] == [Decimal("0.05")] * 3


def test_single_currency_total():
    conv = Converter(rates())
    assert report_total([make("A", "10.00"), make("B", "5.55")], conv, "EUR") == Decimal("15.55")
