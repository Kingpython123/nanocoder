import pytest

from flowkit.retry import retry


class Flaky:
    def __init__(self, failures):
        self.failures = failures
        self.calls = 0

    def __call__(self):
        self.calls += 1
        if self.calls <= self.failures:
            raise RuntimeError(f"fail {self.calls}")
        return "ok"


def test_total_calls():
    fn = Flaky(100)
    with pytest.raises(RuntimeError, match="fail 4"):
        retry(fn, max_retries=3, sleep=lambda s: None)
    assert fn.calls == 4


def test_sleeps_between_attempts_only():
    sleeps = []
    with pytest.raises(RuntimeError):
        retry(Flaky(100), max_retries=3, sleep=sleeps.append)
    assert sleeps == [0.1, 0.2, 0.4]


def test_zero_retries():
    sleeps = []
    fn = Flaky(100)
    with pytest.raises(RuntimeError, match="fail 1"):
        retry(fn, max_retries=0, sleep=sleeps.append)
    assert fn.calls == 1
    assert sleeps == []


def test_succeeds_on_last_attempt():
    sleeps = []
    fn = Flaky(3)
    assert retry(fn, max_retries=3, sleep=sleeps.append) == "ok"
    assert fn.calls == 4
    assert sleeps == [0.1, 0.2, 0.4]


def test_max_delay_cap():
    sleeps = []
    assert retry(Flaky(2), max_retries=5, base_delay=1.0, max_delay=1.5, sleep=sleeps.append) == "ok"
    assert sleeps == [1.0, 1.5]
