from decimal import Decimal

import pytest

from ledgerlite.currency import Converter, StaticRates


def make():
    rates = StaticRates({("EUR", "USD"): "1.10", ("EUR", "GBP"): "0.85"})
    return rates, Converter(rates)


def test_convert_direct_pair():
    _, conv = make()
    assert conv.convert(Decimal("100"), "EUR", "USD") == Decimal("110.00")


def test_convert_inverse_pair():
    _, conv = make()
    assert conv.convert(Decimal("110"), "usd", "eur") == Decimal("100.00")


def test_same_currency():
    _, conv = make()
    assert conv.convert(Decimal("42.42"), "GBP", "GBP") == Decimal("42.42")


def test_rate_is_cached():
    rates, conv = make()
    for _ in range(3):
        conv.convert(Decimal("1"), "EUR", "USD")
    assert rates.calls == 1


def test_unknown_pair():
    _, conv = make()
    with pytest.raises(KeyError):
        conv.convert(1, "JPY", "CHF")
