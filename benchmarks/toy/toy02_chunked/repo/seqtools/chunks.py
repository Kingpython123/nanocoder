def chunked(seq, size):
    """Split `seq` into consecutive lists of length `size` (the last one may be shorter)."""
    if size < 1:
        raise ValueError("size must be >= 1")
    return [list(seq[i : i + size]) for i in range(0, len(seq) - size + 1, size)]


def windows(seq, size):
    """All overlapping windows of length `size`."""
    return [list(seq[i : i + size]) for i in range(0, len(seq) - size + 1)]
