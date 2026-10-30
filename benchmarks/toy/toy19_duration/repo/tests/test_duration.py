import pytest
from timeparse import parse_duration


def test_hours_minutes():
    assert parse_duration("1h30m") == 5400


def test_seconds():
    assert parse_duration("90s") == 90
    assert parse_duration("1h30m15s") == 5415


def test_bare_number_is_minutes():
    assert parse_duration("45") == 2700


def test_garbage():
    with pytest.raises(ValueError):
        parse_duration("10x")
