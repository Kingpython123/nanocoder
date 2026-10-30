from versions import compare


def test_equal():
    assert compare("1.2.3", "1.2.3") == 0


def test_simple_order():
    assert compare("1.2.3", "1.2.4") == -1
    assert compare("2.0.0", "1.9.9") == 1


def test_numeric_not_lexical():
    assert compare("1.10.0", "1.9.0") == 1
    assert compare("1.2.10", "1.2.9") == 1


def test_prerelease_lower():
    assert compare("1.0.0-alpha", "1.0.0") == -1
    assert compare("1.0.0", "1.0.0-rc") == 1


def test_prerelease_order():
    assert compare("1.0.0-alpha", "1.0.0-beta") == -1
