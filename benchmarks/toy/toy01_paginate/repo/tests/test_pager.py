import pytest
from pager import get_page, page_count


def test_exact_multiple():
    assert page_count(10, 5) == 2


def test_first_page():
    assert get_page(list(range(11)), 1, 5) == [0, 1, 2, 3, 4]


def test_empty():
    assert page_count(0, 5) == 0
    assert get_page([], 1, 5) == []


def test_last_partial_page():
    assert page_count(11, 5) == 3
    assert get_page(list(range(11)), 3, 5) == [10]


def test_out_of_range():
    with pytest.raises(ValueError):
        get_page(list(range(11)), 4, 5)
