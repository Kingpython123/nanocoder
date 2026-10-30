import pytest

from flowkit.config import DEFAULTS, load_config


def test_defaults():
    cfg = load_config()
    assert cfg == DEFAULTS
    assert cfg["retry"]["max_retries"] == 3


def test_top_level_override():
    cfg = load_config({"name": "nightly"})
    assert cfg["name"] == "nightly"
    assert cfg["retry"] == DEFAULTS["retry"]
    assert DEFAULTS["name"] == "pipeline"


def test_unknown_key():
    with pytest.raises(KeyError):
        load_config({"retires": {}})


def test_env_top_level_string():
    cfg = load_config(environ={"FLOWKIT_NAME": "from-env", "HOME": "/root", "FLOWKITX": "1"})
    assert cfg["name"] == "from-env"
    assert cfg["retry"] == DEFAULTS["retry"]
