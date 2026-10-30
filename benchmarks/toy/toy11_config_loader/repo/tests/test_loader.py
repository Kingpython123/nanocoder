import pytest
from confkit import load_config
from confkit.schema import coerce

SAMPLE = "# service settings\nNAME = demo\nDEBUG=false\n\nPORT=8080\n"


def test_simple():
    assert load_config("NAME=x\nPORT=1") == {"NAME": "x", "PORT": 1}


def test_comments_and_blanks():
    cfg = load_config(SAMPLE)
    assert cfg["NAME"] == "demo"
    assert cfg["PORT"] == 8080


@pytest.mark.parametrize("raw,expected", [("false", False), ("True", True), ("no", False), ("1", True), ("0", False)])
def test_bool(raw, expected):
    assert coerce(bool, raw) is expected


def test_bool_from_file():
    assert load_config(SAMPLE)["DEBUG"] is False
