from decimal import Decimal

from ledgerlite import Converter, Invoice, StaticRates
from ledgerlite.report import render_report, report_rows


def make(number, amount, currency="EUR"):
    inv = Invoice(number, region="DE", currency=currency)
    inv.add_line("X", 1, amount, "books")
    return inv


def test_foreign_invoice_converted_to_base():
    conv = Converter(StaticRates({("EUR", "USD"): "1.10"}))
    rows = report_rows([make("U-1", "110.00", "USD")], conv, "EUR")
    assert rows == [("U-1", Decimal("110.00"), Decimal("100.00"))]


def test_render_mixed_currencies():
    conv = Converter(StaticRates({("EUR", "USD"): "1.10"}))
    text = render_report([make("A", "10.00"), make("B", "110.00", "USD")], conv, "EUR")
    lines = text.splitlines()
    assert lines[2].split() == ["B", "110.00", "USD", "100.00", "EUR"]
    assert lines[-1].split() == ["TOTAL", "110.00", "EUR"]


def test_rate_fetched_once_per_pair():
    rates = StaticRates({("EUR", "USD"): "1.10"})
    conv = Converter(rates)
    report_rows([make("A", "1.00", "USD"), make("B", "2.00", "USD"), make("C", "3.00", "USD")], conv, "EUR")
    assert rates.calls == 1
