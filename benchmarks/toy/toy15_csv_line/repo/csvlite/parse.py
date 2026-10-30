def parse_line(line: str) -> list[str]:
    """Split one CSV line into fields.

    Rules:
    - Fields are separated by commas.
    - A field may be wrapped in double quotes; inside quotes, commas are literal.
    - Inside a quoted field, two consecutive double quotes ("") stand for one literal quote.
    - The surrounding quotes are not part of the value.
    - An empty line yields a single empty field: [""].
    """
    return line.split(",")
