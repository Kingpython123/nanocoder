from flowkit.template import render


def test_pipe_inside_single_quotes():
    assert render("{{ status | default('n/a | unknown') }}", {}) == "n/a | unknown"


def test_pipe_inside_double_quotes():
    assert render('{{ s | default("a|b") | upper }}', {}) == "A|B"


def test_closing_braces_inside_quotes():
    assert render("[{{ x | default('}}') }}]", {}) == "[}}]"


def test_escaped_quote_in_arg():
    assert render("{{ x | default('it\\'s | ok') }}", {}) == "it's | ok"


def test_chain_and_multiple_expressions():
    assert render("{{a|trim|upper}}-{{ b | lower }}", {"a": " x ", "b": "Y"}) == "X-y"


def test_adjacent_expressions_and_plain_text():
    assert render("{{a}}{{b}}", {"a": 1, "b": 2}) == "12"
    assert render("no templates here", {}) == "no templates here"
