def top_n(scores: dict[str, int], n: int) -> list[tuple[str, int]]:
    """The `n` best (name, score) pairs, highest score first; ties broken by name."""
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    return ranked[:n]
