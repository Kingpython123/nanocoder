from decimal import Decimal

from ledgerlite.currency import Converter, StaticRates


def make():
    rates = StaticRates({("EUR", "USD"): "1.10", ("EUR", "GBP"): "0.85"})
    return rates, Converter(rates)


def test_same_source_different_targets():
    _, conv = make()
    assert conv.convert(Decimal("100"), "EUR", "USD") == Decimal("110.00")
    assert conv.convert(Decimal("100"), "EUR", "GBP") == Decimal("85.00")
    assert conv.convert(Decimal("100"), "EUR", "USD") == Decimal("110.00")


def test_one_provider_call_per_pair():
    rates, conv = make()
    for _ in range(2):
        conv.convert(1, "EUR", "USD")
        conv.convert(1, "EUR", "GBP")
    conv.convert(1, "USD", "EUR")
    assert rates.calls == 3


def test_clear_refetches():
    rates, conv = make()
    conv.convert(1, "EUR", "USD")
    conv.clear()
    conv.convert(1, "EUR", "USD")
    assert rates.calls == 2


def test_case_insensitive_cache():
    rates, conv = make()
    conv.convert(1, "eur", "usd")
    conv.convert(1, "EUR", "USD")
    assert rates.calls == 1
