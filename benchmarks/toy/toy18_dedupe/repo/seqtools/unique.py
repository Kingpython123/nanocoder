def dedupe(items, key=None):
    """Remove duplicates, keeping the first occurrence of each item.

    If `key` is given, two items are duplicates when key(item) is equal.
    """
    if key is None:
        return sorted(set(items))
    seen = set()
    out = []
    for item in items:
        k = key(item)
        if k not in seen:
            seen.add(k)
            out.append(item)
    return out
