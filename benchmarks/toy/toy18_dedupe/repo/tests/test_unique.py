from seqtools import dedupe


def test_keeps_order():
    assert dedupe([3, 1, 3, 2, 1]) == [3, 1, 2]


def test_strings_order():
    assert dedupe(["b", "a", "b"]) == ["b", "a"]


def test_key_first_occurrence():
    people = [{"id": 1, "n": "a"}, {"id": 2, "n": "b"}, {"id": 1, "n": "c"}]
    assert dedupe(people, key=lambda p: p["id"]) == [{"id": 1, "n": "a"}, {"id": 2, "n": "b"}]


def test_key_case_insensitive():
    assert dedupe(["A", "a", "B"], key=str.lower) == ["A", "B"]
