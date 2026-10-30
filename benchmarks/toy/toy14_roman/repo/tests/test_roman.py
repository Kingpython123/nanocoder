import pytest
from numerals import to_roman


def test_simple():
    assert to_roman(3) == "III"
    assert to_roman(2000) == "MM"


@pytest.mark.parametrize("n,expected", [(4, "IV"), (9, "IX"), (14, "XIV"), (40, "XL"), (90, "XC"), (400, "CD"), (1994, "MCMXCIV"), (3999, "MMMCMXCIX")])
def test_subtractive(n, expected):
    assert to_roman(n) == expected


def test_range():
    with pytest.raises(ValueError):
        to_roman(0)
