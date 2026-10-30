# Base rates: 1 unit of the first currency = rate units of the second
_RATES = {
    ("USD", "CNY"): 7.2,
    ("USD", "EUR"): 0.92,
}


def get_rate(src: str, dst: str) -> float:
    """How many `dst` units one `src` unit is worth."""
    if src == dst:
        return 1.0
    if (src, dst) in _RATES:
        return _RATES[(src, dst)]
    if (dst, src) in _RATES:
        return _RATES[(dst, src)]
    raise KeyError(f"no rate for {src}->{dst}")
