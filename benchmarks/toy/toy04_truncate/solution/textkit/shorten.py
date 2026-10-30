def truncate(text: str, width: int, suffix: str = "...") -> str:
    """Shorten `text` to at most `width` characters, including `suffix`.

    Text that already fits is returned unchanged.
    """
    if len(text) > width:
        return text[: max(0, width - len(suffix))] + suffix
    return text
