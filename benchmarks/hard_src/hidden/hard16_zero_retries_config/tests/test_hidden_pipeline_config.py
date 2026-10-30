import pytest

from flowkit import Pipeline, Step


def always_fail(calls):
    def fn(results):
        calls.append(1)
        raise RuntimeError("nope")

    return fn


def test_zero_retries_from_config():
    calls, sleeps = [], []
    p = Pipeline([Step("x", always_fail(calls))], config={"retry": {"max_retries": 0}}, sleep=sleeps.append)
    with pytest.raises(RuntimeError):
        p.run()
    assert calls == [1]
    assert sleeps == []


def test_zero_base_delay_from_config():
    attempts, sleeps = [], []

    def flaky(results):
        attempts.append(1)
        if len(attempts) < 3:
            raise RuntimeError("boom")
        return "ok"

    p = Pipeline([Step("x", flaky)], config={"retry": {"base_delay": 0}}, sleep=sleeps.append)
    assert p.run() == {"x": "ok"}
    assert sleeps == [0, 0]


def test_five_retries_from_config():
    calls = []
    p = Pipeline([Step("x", always_fail(calls))], config={"retry": {"max_retries": 5}}, sleep=lambda s: None)
    with pytest.raises(RuntimeError):
        p.run()
    assert len(calls) == 6


def test_defaults_without_config():
    calls, sleeps = [], []
    p = Pipeline([Step("x", always_fail(calls))], sleep=sleeps.append)
    with pytest.raises(RuntimeError):
        p.run()
    assert len(calls) == 4
    assert sleeps == [0.1, 0.2, 0.4]
