from .rates import get_rate


def convert(amount: float, src: str, dst: str) -> float:
    """Convert `amount` from `src` to `dst`, rounded to cents."""
    return float(int(amount * get_rate(src, dst)))
