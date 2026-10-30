from .schema import SCHEMA, coerce


def parse_lines(text: str) -> dict[str, str]:
    raw = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        raw[key.strip()] = value.strip()
    return raw


def load_config(text: str) -> dict:
    raw = parse_lines(text)
    return {key: coerce(SCHEMA.get(key, str), value) for key, value in raw.items()}
