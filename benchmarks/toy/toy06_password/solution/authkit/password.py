def validate_password(pw: str) -> list[str]:
    """Return a list of problems; an empty list means the password is acceptable."""
    problems = []
    if len(pw) < 8:
        problems.append("must be at least 8 characters")
    if not any(c.isupper() for c in pw):
        problems.append("must contain an uppercase letter")
    if not any(c.isdigit() for c in pw):
        problems.append("must contain a digit")
    return problems
