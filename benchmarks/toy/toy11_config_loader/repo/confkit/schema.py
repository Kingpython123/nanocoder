SCHEMA = {
    "NAME": str,
    "DEBUG": bool,
    "PORT": int,
}


def coerce(typ, value: str):
    """Convert a raw string to `typ`."""
    return typ(value)
