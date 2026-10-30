import pytest

from flowkit.template import TemplateError, render


def test_plain_variable():
    assert render("Hello {{ name }}!", {"name": "Ada"}) == "Hello Ada!"


def test_dotted_path():
    assert render("{{user.city}}", {"user": {"city": "Oslo"}}) == "Oslo"


def test_missing_renders_empty():
    assert render("[{{ nope }}]", {}) == "[]"


def test_single_filters():
    assert render("{{ x | upper }}", {"x": "abc"}) == "ABC"
    assert render("{{ x | trim }}", {"x": "  a  "}) == "a"
    assert render("{{ x | default('n/a') }}", {}) == "n/a"
    assert render("{{ x | truncate(3) }}", {"x": "abcdef"}) == "abc..."


def test_unknown_filter():
    with pytest.raises(TemplateError):
        render("{{ x | shout }}", {"x": "a"})
