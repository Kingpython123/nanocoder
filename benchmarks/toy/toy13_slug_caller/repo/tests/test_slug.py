from textutils import slugify


def test_default_sep():
    assert slugify("Hello, World!") == "hello-world"


def test_custom_sep():
    assert slugify("a b", sep=".") == "a.b"
