import pytest

from flowkit import Pipeline, Step


def chain():
    calls = []

    def step(name, *deps):
        def fn(results):
            calls.append(name)
            return sum(results[d] for d in deps) + 1

        return Step(name, fn, deps)

    steps = [
        step("fetch"),
        step("load", "fetch"),
        step("report", "load"),
        step("audit", "fetch"),
        step("cleanup"),
    ]
    return Pipeline(steps, sleep=lambda s: None), calls


def test_only_runs_transitive_deps():
    p, calls = chain()
    assert p.run(only=["report"]) == {"fetch": 1, "load": 2, "report": 3}
    assert calls == ["fetch", "load", "report"]


def test_only_multiple_targets_shared_deps():
    p, calls = chain()
    results = p.run(only=["cleanup", "report"])
    assert set(results) == {"fetch", "load", "report", "cleanup"}
    assert calls.count("fetch") == 1


def test_only_with_diamond():
    order = []
    mk = lambda n, *d: Step(n, lambda r, n=n: order.append(n), d)  # noqa: E731
    p = Pipeline([mk("a"), mk("b", "a"), mk("c", "a"), mk("d", "b", "c"), mk("e", "d")])
    p.run(only=["d"])
    assert order == ["a", "b", "c", "d"]


def test_only_unknown_name():
    p, _ = chain()
    with pytest.raises(ValueError):
        p.run(only=["nope"])


def test_only_direct_deps_order():
    p, calls = chain()
    p.run(only=["load"])
    assert calls == ["fetch", "load"]


def test_run_all_unchanged():
    p, calls = chain()
    assert len(p.run()) == 5
