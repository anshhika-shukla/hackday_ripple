import pytest

from menu import get_item, price_of, veg_items


def test_get_item():
    assert get_item("CHAI")["name"] == "Masala chai"


def test_get_item_unknown():
    with pytest.raises(KeyError):
        get_item("PIZZA")


def test_price_of():
    assert price_of("THALI") == 9000


def test_veg_items_exclude_chicken():
    assert "CHICKEN" not in veg_items()


def test_veg_items_count():
    assert len(veg_items()) == 5
