from datetime import datetime

import pytest

from flowkit.cron import CronError, CronSpec


def test_every_15_minutes():
    spec = CronSpec("*/15 * * * *")
    assert spec.minutes == frozenset({0, 15, 30, 45})


def test_weekday_range_and_list():
    spec = CronSpec("0 9,17 * * 1-5")
    assert spec.hours == frozenset({9, 17})
    assert spec.matches(datetime(2024, 6, 3, 9, 0))  # Monday
    assert not spec.matches(datetime(2024, 6, 2, 9, 0))  # Sunday


def test_sunday_as_7():
    spec = CronSpec("0 0 * * 7")
    assert spec.matches(datetime(2024, 6, 2, 0, 0))


def test_next_after():
    spec = CronSpec("30 6 * * *")
    assert spec.next_after(datetime(2024, 6, 1, 7, 0)) == datetime(2024, 6, 2, 6, 30)


@pytest.mark.parametrize("expr", ["* * * *", "61 * * * *", "* 24 * * *", "a * * * *", "*/0 * * * *"])
def test_invalid(expr):
    with pytest.raises(CronError):
        CronSpec(expr)
