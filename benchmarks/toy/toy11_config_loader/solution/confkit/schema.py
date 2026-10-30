SCHEMA = {
    "NAME": str,
    "DEBUG": bool,
    "PORT": int,
}

_TRUE = {"true", "yes", "1"}
_FALSE = {"false", "no", "0"}


def coerce(typ, value: str):
    """Convert a raw string to `typ`."""
    if typ is bool:
        v = value.strip().lower()
        if v in _TRUE:
            return True
        if v in _FALSE:
            return False
        raise ValueError(f"not a boolean: {value!r}")
    return typ(value)
