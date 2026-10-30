import pytest

from flowkit import Pipeline, Step
from flowkit.config import load_config


def test_nested_int():
    cfg = load_config(environ={"FLOWKIT_RETRY__MAX_RETRIES": "5"})
    assert cfg["retry"]["max_retries"] == 5
    assert cfg["retry"]["base_delay"] == 0.1


def test_types_parsed():
    cfg = load_config(
        environ={
            "FLOWKIT_RETRY__BASE_DELAY": "0.5",
            "FLOWKIT_LOGGING__LEVEL": '"DEBUG"',
            "FLOWKIT_LOGGING__HANDLERS": '{"file": {"path": "x.log"}}',
        }
    )
    assert cfg["retry"]["base_delay"] == 0.5
    assert cfg["logging"]["level"] == "DEBUG"
    assert cfg["logging"]["handlers"]["file"] == {"path": "x.log"}
    assert cfg["logging"]["handlers"]["console"]["enabled"] is True


def test_three_levels_bool():
    cfg = load_config(environ={"FLOWKIT_LOGGING__HANDLERS__CONSOLE__ENABLED": "false"})
    assert cfg["logging"]["handlers"]["console"] == {"enabled": False, "format": "%(message)s"}


def test_pipeline_uses_env_retries():
    calls = []

    def fail(results):
        calls.append(1)
        raise RuntimeError

    p = Pipeline([Step("x", fail)], sleep=lambda s: None, environ={"FLOWKIT_RETRY__MAX_RETRIES": "1"})
    with pytest.raises(RuntimeError):
        p.run()
    assert len(calls) == 2


def test_explicit_config_beats_env():
    cfg = load_config({"name": "explicit"}, environ={"FLOWKIT_NAME": "env"})
    assert cfg["name"] == "explicit"


def test_non_json_string_kept():
    assert load_config(environ={"FLOWKIT_NAME": "nightly build"})["name"] == "nightly build"


def test_unrelated_vars_ignored():
    cfg = load_config(environ={"PATH": "/bin", "FLOWKITNAME": "x"})
    assert cfg["name"] == "pipeline"
