try:
    from mini_app.cart import Cart
    from mini_app.checkout import process_order
except ImportError:
    from cart import Cart
    from checkout import process_order


def test_checkout_process():
    cart = Cart()
    cart.add_item("item_1", 100.0, 1)
    receipt = process_order(cart, discount=0.1)
    assert receipt["status"] == "confirmed"
    assert receipt["items_count"] == 1
    assert receipt["formatted_total"] == "$99.00"
