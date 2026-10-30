import re

_UNITS = {"h": 3600, "m": 60, "s": 1}
_PART = re.compile(r"(\d+)([hms])")


def parse_duration(text: str) -> int:
    """Parse a duration like "1h30m" into seconds.

    For backwards compatibility, a bare number (no unit) means MINUTES: "45" -> 2700.
    """
    text = text.strip()
    if text.isdigit():
        return int(text) * 60
    pos, total = 0, 0
    for m in _PART.finditer(text):
        if m.start() != pos:
            raise ValueError(f"bad duration: {text!r}")
        total += int(m.group(1)) * _UNITS[m.group(2)]
        pos = m.end()
    if pos != len(text) or pos == 0:
        raise ValueError(f"bad duration: {text!r}")
    return total
