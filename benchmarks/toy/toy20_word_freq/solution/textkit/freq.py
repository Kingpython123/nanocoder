import re
from collections import Counter

_WORD = re.compile(r"[A-Za-z0-9']+")


def word_freq(text: str, case_sensitive: bool = False) -> dict[str, int]:
    """Count words in `text`. Words are runs of letters, digits or apostrophes."""
    if not case_sensitive:
        text = text.lower()
    return dict(Counter(_WORD.findall(text)))
