import re


def slugify(text: str, sep: str = "-") -> str:
    """Lowercase, keep only letters/digits, join words with `sep`."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    return sep.join(words)
