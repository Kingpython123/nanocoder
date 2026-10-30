from flowkit import EventBus, Pipeline, Step


def test_runs_in_dependency_order():
    calls = []

    def make(name, value):
        def fn(results):
            calls.append(name)
            return value + sum(results.values())

        return fn

    steps = [
        Step("report", make("report", 100), ("load",)),
        Step("load", make("load", 1), ("fetch",)),
        Step("fetch", make("fetch", 10)),
    ]
    results = Pipeline(steps, sleep=lambda s: None).run()
    assert calls == ["fetch", "load", "report"]
    assert results == {"fetch": 10, "load": 11, "report": 121}


def test_retries_with_default_config():
    attempts, sleeps = [], []

    def flaky(results):
        attempts.append(1)
        if len(attempts) < 3:
            raise RuntimeError("boom")
        return "done"

    results = Pipeline([Step("x", flaky)], sleep=sleeps.append).run()
    assert results == {"x": "done"}
    assert sleeps == [0.1, 0.2]


def test_emits_events():
    bus, events = EventBus(), []
    bus.subscribe("step.started", lambda n: events.append(("start", n)))
    bus.subscribe("step.finished", lambda n: events.append(("end", n)))
    Pipeline([Step("a", lambda r: 1)], bus=bus).run()
    assert events == [("start", "a"), ("end", "a")]


def test_config_name():
    assert Pipeline([], config={"name": "nightly"}).config["name"] == "nightly"


def test_run_only_without_dependencies():
    import pytest

    steps = [Step("a", lambda r: 1), Step("b", lambda r: 2)]
    p = Pipeline(steps)
    assert p.run(only=["b"]) == {"b": 2}
    with pytest.raises(ValueError):
        p.run(only=["zzz"])
