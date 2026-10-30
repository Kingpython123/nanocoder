from decimal import Decimal

from ledgerlite.tax import is_exempt, line_tax


def test_similar_categories_are_taxed():
    for category in ("e-books", "seafood", "audiobooks", "foodstuff", "books-used"):
        assert not is_exempt(category), category
        assert line_tax(Decimal("100.00"), category, "DE") == Decimal("19.00")


def test_case_and_whitespace_still_exempt():
    assert is_exempt(" Food ")
    assert is_exempt("BOOKS")
    assert line_tax(Decimal("50.00"), "\tbooks\n", "FR") == Decimal("0.00")


def test_empty_category_taxed():
    assert not is_exempt("")
    assert not is_exempt("   ")
