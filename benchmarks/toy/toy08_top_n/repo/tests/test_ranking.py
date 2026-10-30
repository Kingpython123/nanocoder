from board import top_n


def test_best_first():
    assert top_n({"ann": 90, "bob": 70, "cy": 85}, 2) == [("ann", 90), ("cy", 85)]


def test_ties_by_name():
    assert top_n({"zed": 50, "amy": 50, "kim": 60}, 3) == [("kim", 60), ("amy", 50), ("zed", 50)]


def test_n_larger_than_len():
    assert len(top_n({"a": 1}, 5)) == 1
