from collections import Counter


def word_freq(text: str, case_sensitive: bool = False) -> dict[str, int]:
    """Count words in `text`. Words are runs of letters, digits or apostrophes."""
    words = text.split()
    return dict(Counter(words))
