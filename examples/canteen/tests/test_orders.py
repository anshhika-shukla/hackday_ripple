from cart import Cart
from orders import place_order, receipt


def lunch_cart():
    cart = Cart()
    cart.add("THALI")
    cart.add("CHAI", 2)
    return cart  # subtotal ₹120.00


def test_order_total():
    order = place_order(lunch_cart())
    assert order["gst"] == 600
    assert order["total"] == 12600


def test_student_order_total():
    order = place_order(lunch_cart(), is_student=True)
    assert order["discount"] == 1200
    assert order["total"] == 11300


def test_points_redeemed():
    order = place_order(lunch_cart(), points=10)
    assert order["redeemed"] == 1000
    assert order["total"] == 11600


def test_points_earned():
    assert place_order(lunch_cart())["points_earned"] == 6


def test_receipt():
    assert receipt(place_order(lunch_cart())) == "Subtotal ₹120.00\nGST ₹6.00\nTotal ₹126.00"


def test_receipt_shows_student_discount():
    assert "Student discount -₹12.00" in receipt(place_order(lunch_cart(), is_student=True))
