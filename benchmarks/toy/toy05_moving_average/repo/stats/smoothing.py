def moving_average(values: list[float], window: int) -> list[float]:
    """Simple moving average over every full window."""
    if window < 1:
        raise ValueError("window must be >= 1")
    return [sum(values[i : i + window]) / window for i in range(len(values) - window)]
