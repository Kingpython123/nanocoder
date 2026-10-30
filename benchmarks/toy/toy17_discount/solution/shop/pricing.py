def apply_discount(price: float, percent: float) -> float:
    """Price after taking `percent` (0-100) percent off, rounded to cents."""
    return round(price * (1 - percent / 100), 2)
