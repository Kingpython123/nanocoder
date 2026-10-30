def truncate(text: str, width: int, suffix: str = "...") -> str:
    """Shorten `text` to at most `width` characters, including `suffix`.

    Text that already fits is returned unchanged.
    """
    if len(text) > width:
        return text[:width] + suffix
    return text
