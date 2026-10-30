import pytest

from flowkit import Pipeline, Step
from flowkit.graph import CycleError, topo_order


def test_self_loop_is_cycle():
    with pytest.raises(CycleError) as exc:
        topo_order({"a": ["a"], "b": []})
    assert exc.value.cycle == ["a", "a"]
    assert str(exc.value) == "dependency cycle: a -> a"


def test_pipeline_rejects_self_dependency():
    ran = []
    p = Pipeline([Step("build", lambda r: ran.append(1), ("build",))], sleep=lambda s: None)
    with pytest.raises(CycleError):
        p.run()
    assert ran == []


def test_three_cycle_reported():
    with pytest.raises(CycleError) as exc:
        topo_order({"a": ["c"], "b": ["a"], "c": ["b"], "d": []})
    assert exc.value.cycle == ["a", "c", "b", "a"]


def test_valid_graph_unchanged():
    assert topo_order({"b": ["a"], "a": [], "c": ["a", "b"]}) == ["a", "b", "c"]
