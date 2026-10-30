from datetime import datetime

import pytest

from flowkit.cron import CronError, CronSpec


def test_range_with_step():
    spec = CronSpec("10-30/10 * * * *")
    assert spec.minutes == frozenset({10, 20, 30})
    assert spec.matches(datetime(2024, 6, 3, 8, 20))
    assert not spec.matches(datetime(2024, 6, 3, 8, 15))


def test_hour_range_step():
    assert CronSpec("0 0-23/6 * * *").hours == frozenset({0, 6, 12, 18})


def test_weekday_range_step():
    assert CronSpec("0 0 * * 1-5/2").weekdays == frozenset({1, 3, 5})


def test_list_of_ranges_with_steps():
    assert CronSpec("1-3,10-20/5 * * * *").minutes == frozenset({1, 2, 3, 10, 15, 20})


def test_range_step_out_of_bounds():
    with pytest.raises(CronError):
        CronSpec("50-70/5 * * * *")
    with pytest.raises(CronError):
        CronSpec("10-30/0 * * * *")


def test_step_on_single_value_rejected():
    with pytest.raises(CronError):
        CronSpec("5/15 * * * *")


def test_star_step_still_works():
    assert CronSpec("*/20 * * * *").minutes == frozenset({0, 20, 40})
    assert CronSpec("0 */12 * * *").hours == frozenset({0, 12})
