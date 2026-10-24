try:
    from mini_app.cart import Cart
except ImportError:
    from cart import Cart


def test_cart_add_item():
    cart = Cart()
    success = cart.add_item("item_1", 25.0, 1)
    assert success is True
    assert len(cart.items) == 1


def test_cart_total():
    cart = Cart()
    cart.add_item("item_1", 50.0, 2)
    assert cart.get_total(discount=0.0) == 100.0
    assert cart.get_total(discount=0.2) == 80.0
