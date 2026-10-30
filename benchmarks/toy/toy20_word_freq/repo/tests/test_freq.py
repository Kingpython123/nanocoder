from textkit import word_freq


def test_default_case_insensitive():
    assert word_freq("The cat and the hat") == {"the": 2, "cat": 1, "and": 1, "hat": 1}


def test_punctuation():
    assert word_freq("Hi, hi!") == {"hi": 2}


def test_case_sensitive_flag():
    assert word_freq("Go go GO", case_sensitive=True) == {"Go": 1, "go": 1, "GO": 1}


def test_apostrophe():
    assert word_freq("don't don't", case_sensitive=True) == {"don't": 2}
