"""Prices, the student discount and GST."""

from menu import price_of
from money import percent_of

STUDENT_DISCOUNT_PERCENT = 10
GST_PERCENT = 5


def line_total(code: str, qty: int) -> int:
    if qty <= 0:
        raise ValueError("quantity must be positive")
    return price_of(code) * qty


def student_discount(subtotal: int, is_student: bool) -> int:
    """Discount amount (not the new total)."""
    return percent_of(subtotal, STUDENT_DISCOUNT_PERCENT) if is_student else 0


def gst(amount: int) -> int:
    return percent_of(amount, GST_PERCENT)
