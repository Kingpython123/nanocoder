from csvlite import parse_line


def test_plain():
    assert parse_line("a,b,c") == ["a", "b", "c"]


def test_empty_fields():
    assert parse_line("a,,c") == ["a", "", "c"]
    assert parse_line("") == [""]


def test_quoted_comma():
    assert parse_line('a,"b,c",d') == ["a", "b,c", "d"]


def test_escaped_quote():
    assert parse_line('"say ""hi""",x') == ['say "hi"', "x"]


def test_quoted_empty():
    assert parse_line('"",z') == ["", "z"]
