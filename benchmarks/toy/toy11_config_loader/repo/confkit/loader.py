from .schema import SCHEMA, coerce


def parse_lines(text: str) -> dict[str, str]:
    raw = {}
    for line in text.splitlines():
        key, value = line.split("=", 1)
        raw[key] = value
    return raw


def load_config(text: str) -> dict:
    raw = parse_lines(text)
    return {key: coerce(SCHEMA.get(key, str), value) for key, value in raw.items()}
