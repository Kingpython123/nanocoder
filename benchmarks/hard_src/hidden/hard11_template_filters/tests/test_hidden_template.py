import pytest

from flowkit.template import TemplateError, render


def test_default_then_upper():
    assert render("{{ name | default('anonymous') | upper }}", {}) == "ANONYMOUS"


def test_default_then_truncate():
    assert render("{{ x | default('unknown user') | truncate(7) }}", {}) == "unknown..."


def test_trim_then_truncate():
    assert render("{{ x | trim | truncate(3) }}", {"x": "  abcdef"}) == "abc..."


def test_lower_then_default():
    assert render("{{ x | lower | default('N/A') }}", {}) == "N/A"


def test_unknown_filter_in_chain():
    with pytest.raises(TemplateError):
        render("{{ x | upper | shout }}", {"x": "a"})


def test_multiple_expressions():
    assert render("{{a|upper}}-{{ b | lower }}", {"a": "x", "b": "Y"}) == "X-y"
