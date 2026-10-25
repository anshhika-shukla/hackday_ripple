import pytest

from cart import Cart


def test_add_same_item_twice():
    cart = Cart()
    cart.add("CHAI")
    cart.add("CHAI")
    assert cart.lines == {"CHAI": 2}


def test_count():
    cart = Cart()
    cart.add("CHAI", 2)
    cart.add("SAMOSA")
    assert cart.count() == 3


def test_subtotal():
    cart = Cart()
    cart.add("THALI")
    cart.add("CHAI", 2)
    assert cart.subtotal() == 12000


def test_remove():
    cart = Cart()
    cart.add("LASSI")
    cart.remove("LASSI")
    assert cart.count() == 0


def test_add_unknown_item_leaves_cart_unchanged():
    cart = Cart()
    with pytest.raises(KeyError):
        cart.add("PIZZA")
    assert cart.lines == {}


def test_add_zero_quantity_rejected():
    with pytest.raises(ValueError):
        Cart().add("CHAI", 0)
