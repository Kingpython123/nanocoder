from authkit import validate_password


def test_good_password():
    assert validate_password("Secret123!") == []


def test_missing_digit():
    assert validate_password("Secretttt!") == ["must contain a digit"]


def test_too_short():
    assert "must be at least 8 characters" in validate_password("S1a")


def test_missing_upper():
    assert validate_password("secret123") == ["must contain an uppercase letter"]
