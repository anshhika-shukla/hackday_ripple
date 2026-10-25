"""Placing an order: discount, GST, loyalty points and the receipt."""

from loyalty import points_for, redeem_value
from money import format_rupees, round_to_rupee
from pricing import gst, student_discount


def place_order(cart, is_student: bool = False, points: int = 0) -> dict:
    subtotal = cart.subtotal()
    discount = student_discount(subtotal, is_student)
    after_discount = subtotal - discount
    tax = gst(after_discount)
    redeemed = redeem_value(points, after_discount + tax)
    total = round_to_rupee(after_discount + tax - redeemed)
    return {
        "lines": dict(cart.lines),
        "subtotal": subtotal,
        "discount": discount,
        "gst": tax,
        "redeemed": redeemed,
        "total": total,
        "points_earned": points_for(total),
    }


def receipt(order: dict) -> str:
    rows = [f"Subtotal {format_rupees(order['subtotal'])}"]
    if order["discount"]:
        rows.append(f"Student discount -{format_rupees(order['discount'])}")
    rows.append(f"GST {format_rupees(order['gst'])}")
    if order["redeemed"]:
        rows.append(f"Points -{format_rupees(order['redeemed'])}")
    rows.append(f"Total {format_rupees(order['total'])}")
    return "\n".join(rows)
