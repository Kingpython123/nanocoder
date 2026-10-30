def _parse(v: str):
    core, _, pre = v.partition("-")
    major, minor, patch = (int(x) for x in core.split("."))
    return (major, minor, patch), pre


def compare(a: str, b: str) -> int:
    """Compare two versions MAJOR.MINOR.PATCH[-PRERELEASE].

    Returns -1 if a < b, 0 if equal, 1 if a > b.
    - MAJOR, MINOR and PATCH are compared numerically, in that order.
    - If those are equal, a version WITH a pre-release tag is lower than the same version without one
      (1.0.0-alpha < 1.0.0).
    - Two pre-release tags are compared as plain strings (alpha < beta < rc).
    """
    (ca, pa), (cb, pb) = _parse(a), _parse(b)
    if ca != cb:
        return -1 if ca < cb else 1
    if pa == pb:
        return 0
    if not pa:
        return 1
    if not pb:
        return -1
    return -1 if pa < pb else 1
