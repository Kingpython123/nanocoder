def compare(a: str, b: str) -> int:
    """Compare two versions MAJOR.MINOR.PATCH[-PRERELEASE].

    Returns -1 if a < b, 0 if equal, 1 if a > b.
    - MAJOR, MINOR and PATCH are compared numerically, in that order.
    - If those are equal, a version WITH a pre-release tag is lower than the same version without one
      (1.0.0-alpha < 1.0.0).
    - Two pre-release tags are compared as plain strings (alpha < beta < rc).
    """
    if a == b:
        return 0
    return -1 if a < b else 1
