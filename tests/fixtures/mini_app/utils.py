"""Utility formatting functions for mini_app."""


def format_currency(amount: float) -> str:
    """Format float into USD currency representation."""
    return f"${amount:.2f}"
