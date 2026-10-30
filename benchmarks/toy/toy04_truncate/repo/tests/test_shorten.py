from textkit import truncate


def test_fits_unchanged():
    assert truncate("hello", 5) == "hello"


def test_respects_width():
    out = truncate("hello world", 8)
    assert out == "hello..."
    assert len(out) == 8


def test_custom_suffix():
    assert truncate("abcdefghij", 6, suffix="~") == "abcde~"
