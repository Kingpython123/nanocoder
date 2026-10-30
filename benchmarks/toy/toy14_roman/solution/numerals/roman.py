"""Roman numerals.

Standard (subtractive) notation is used: 4 is IV, 9 is IX, 40 is XL, 90 is XC,
400 is CD and 900 is CM. Valid input range is 1..3999; anything else raises ValueError.
"""

_SYMBOLS = [
    (1000, "M"),
    (900, "CM"),
    (500, "D"),
    (400, "CD"),
    (100, "C"),
    (90, "XC"),
    (50, "L"),
    (40, "XL"),
    (10, "X"),
    (9, "IX"),
    (5, "V"),
    (4, "IV"),
    (1, "I"),
]


def to_roman(n: int) -> str:
    if not 1 <= n <= 3999:
        raise ValueError("out of range")
    out = []
    for value, symbol in _SYMBOLS:
        while n >= value:
            out.append(symbol)
            n -= value
    return "".join(out)
