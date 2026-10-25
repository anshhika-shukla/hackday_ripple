"""Money helpers. Amounts are integers in paise (100 paise = 1 rupee)."""


def format_rupees(paise: int) -> str:
    """1234567 -> '₹12,345.67'."""
    rupees, rest = divmod(abs(paise), 100)
    sign = "-" if paise < 0 else ""
    return f"{sign}₹{rupees:,}.{rest:02d}"


def round_to_rupee(paise: int) -> int:
    """Round to the nearest whole rupee (half up), as the till does."""
    return (paise + 50) // 100 * 100


def percent_of(paise: int, percent: int) -> int:
    """percent% of an amount, rounded down to the paisa."""
    return paise * percent // 100
