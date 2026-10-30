from seqtools import chunked, windows


def test_even():
    assert chunked([1, 2, 3, 4], 2) == [[1, 2], [3, 4]]


def test_remainder_kept():
    assert chunked([1, 2, 3, 4, 5, 6, 7], 3) == [[1, 2, 3], [4, 5, 6], [7]]


def test_shorter_than_size():
    assert chunked([1, 2], 5) == [[1, 2]]


def test_windows():
    assert windows([1, 2, 3], 2) == [[1, 2], [2, 3]]
