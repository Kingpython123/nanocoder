import pytest

from flowkit.graph import CycleError, topo_order


def test_chain():
    assert topo_order({"c": ["b"], "b": ["a"], "a": []}) == ["a", "b", "c"]


def test_diamond_is_deterministic():
    deps = {"d": ["b", "c"], "c": ["a"], "b": ["a"], "a": []}
    assert topo_order(deps) == ["a", "b", "c", "d"]


def test_duplicates_ignored():
    assert topo_order({"b": ["a", "a"], "a": []}) == ["a", "b"]


def test_unknown_dependency():
    with pytest.raises(ValueError, match="unknown step 'x'"):
        topo_order({"a": ["x"]})


def test_two_node_cycle():
    with pytest.raises(CycleError) as exc:
        topo_order({"a": ["b"], "b": ["a"], "c": []})
    assert exc.value.cycle == ["a", "b", "a"]
    assert str(exc.value) == "dependency cycle: a -> b -> a"
