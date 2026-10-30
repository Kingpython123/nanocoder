from datetime import date, timedelta
from decimal import Decimal

from ledgerlite import Invoice
from ledgerlite.aging import aging_summary, overdue_list

TODAY = date(2024, 6, 30)


def inv(number, days_overdue, amount="100.00"):
    i = Invoice(number, region="DE", due=TODAY - timedelta(days=days_overdue))
    if amount is not None:
        i.add_line("X", 1, amount, "food")
    return i


def test_partial_payment_in_summary():
    a = inv("A", 10)
    a.add_payment("40.00")
    assert aging_summary([a], TODAY)["1-30"] == Decimal("60.00")


def test_fully_paid_by_payments_excluded():
    a = inv("A", 45)
    a.add_payment("60.00")
    a.add_payment("40.00")
    assert overdue_list([a], TODAY) == []
    assert aging_summary([a], TODAY)["31-60"] == Decimal("0.00")


def test_overpaid_invoice_excluded():
    a = inv("A", 5)
    a.add_payment("150.00")
    assert overdue_list([a, inv("B", 5)], TODAY) == [("B", 5, "1-30")]
    assert aging_summary([a], TODAY)["1-30"] == Decimal("0.00")


def test_empty_invoice_not_overdue():
    assert overdue_list([inv("Z", 20, amount=None)], TODAY) == []


def test_paid_flag_still_excluded():
    a = inv("A", 10)
    a.paid = True
    assert overdue_list([a], TODAY) == []
    assert sum(aging_summary([a], TODAY).values()) == Decimal("0.00")


def test_unpaid_full_amount():
    assert aging_summary([inv("A", 70, "12.34")], TODAY)["61-90"] == Decimal("12.34")
