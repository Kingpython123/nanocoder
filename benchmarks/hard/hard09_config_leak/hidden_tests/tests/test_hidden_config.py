import copy

from flowkit import Pipeline
from flowkit.config import DEFAULTS, deep_merge, load_config

SNAPSHOT = copy.deepcopy(DEFAULTS)


def test_defaults_not_mutated():
    load_config({"retry": {"max_retries": 5}})
    load_config({"logging": {"handlers": {"console": {"enabled": False}}}})
    assert DEFAULTS == SNAPSHOT


def test_pipelines_isolated():
    p1 = Pipeline([], config={"retry": {"max_retries": 5}})
    p2 = Pipeline([])
    assert p1.config["retry"]["max_retries"] == 5
    assert p2.config["retry"]["max_retries"] == 3
    p2.config["logging"]["handlers"]["console"]["format"] = "changed"
    assert Pipeline([]).config["logging"]["handlers"]["console"]["format"] == "%(message)s"


def test_three_level_merge():
    cfg = load_config({"logging": {"handlers": {"console": {"enabled": False}}}})
    assert cfg["logging"]["handlers"]["console"] == {"enabled": False, "format": "%(message)s"}
    assert cfg["logging"]["level"] == "INFO"


def test_override_not_mutated():
    override = {"retry": {"max_retries": 5}}
    cfg = load_config(override)
    cfg["retry"]["max_retries"] = 9
    assert override == {"retry": {"max_retries": 5}}


def test_merge_new_and_replaced_keys():
    assert deep_merge({"a": 1}, {"b": {"c": 2}}) == {"a": 1, "b": {"c": 2}}
    assert deep_merge({"a": {"x": 1}}, {"a": 5}) == {"a": 5}
