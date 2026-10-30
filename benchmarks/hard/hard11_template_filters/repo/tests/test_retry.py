import pytest

from flowkit.retry import backoff_delays, retry


class Flaky:
    def __init__(self, failures, exc=RuntimeError):
        self.failures = failures
        self.exc = exc
        self.calls = 0

    def __call__(self):
        self.calls += 1
        if self.calls <= self.failures:
            raise self.exc(f"fail {self.calls}")
        return "ok"


def test_backoff_delays():
    assert backoff_delays(3) == [0.1, 0.2, 0.4]
    assert backoff_delays(5, base_delay=0.5, max_delay=2.0) == [0.5, 1.0, 2.0, 2.0, 2.0]


def test_success_first_try():
    sleeps = []
    fn = Flaky(0)
    assert retry(fn, sleep=sleeps.append) == "ok"
    assert fn.calls == 1
    assert sleeps == []


def test_success_after_one_failure():
    sleeps = []
    fn = Flaky(1)
    assert retry(fn, max_retries=3, sleep=sleeps.append) == "ok"
    assert fn.calls == 2
    assert sleeps == [0.1]


def test_non_retryable_error_propagates():
    sleeps = []
    fn = Flaky(5, exc=ValueError)
    with pytest.raises(ValueError):
        retry(fn, retry_on=(KeyError,), sleep=sleeps.append)
    assert fn.calls == 1
    assert sleeps == []
