def normalize_text(value):
    """Normalize optional text fields to a stripped string."""
    return (value or '').strip()


def full_name(first_name, last_name):
    return f'{first_name or ""} {last_name or ""}'.strip()
