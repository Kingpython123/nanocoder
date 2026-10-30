import pytest
from inventory.models import InsufficientStock
from inventory.report import total_value
from inventory.store import Store


def make():
    s = Store()
    s.add("A1", 2.5, 3)
    return s


def test_add_merges():
    s = make()
    s.add("A1", 2.5, 2)
    assert s.items["A1"].qty == 5


def test_remove_ok():
    s = make()
    s.remove("A1", 2)
    assert s.items["A1"].qty == 1


def test_remove_too_many():
    s = make()
    with pytest.raises(InsufficientStock):
        s.remove("A1", 5)
    assert s.items["A1"].qty == 3


def test_total_value():
    s = make()
    s.add("B2", 1.0, 4)
    assert total_value(s) == 11.5
