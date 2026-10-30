def parse_line(line: str) -> list[str]:
    """Split one CSV line into fields.

    Rules:
    - Fields are separated by commas.
    - A field may be wrapped in double quotes; inside quotes, commas are literal.
    - Inside a quoted field, two consecutive double quotes ("") stand for one literal quote.
    - The surrounding quotes are not part of the value.
    - An empty line yields a single empty field: [""].
    """
    fields, cur, i, in_quotes = [], [], 0, False
    while i < len(line):
        ch = line[i]
        if in_quotes:
            if ch == '"':
                if i + 1 < len(line) and line[i + 1] == '"':
                    cur.append('"')
                    i += 1
                else:
                    in_quotes = False
            else:
                cur.append(ch)
        elif ch == '"':
            in_quotes = True
        elif ch == ",":
            fields.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
        i += 1
    fields.append("".join(cur))
    return fields
