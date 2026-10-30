import pytest
from money import convert
from money.rates import get_rate


def test_forward():
    assert convert(10, "USD", "CNY") == 72.0


def test_reverse_rate():
    assert get_rate("CNY", "USD") == pytest.approx(1 / 7.2)
    assert convert(100, "CNY", "USD") == 13.89


def test_keeps_cents():
    assert convert(10, "USD", "EUR") == 9.2


def test_unknown():
    with pytest.raises(KeyError):
        get_rate("USD", "JPY")
