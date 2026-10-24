try:
    from mini_app.inventory import check_stock, reserve_item
except ImportError:
    from inventory import check_stock, reserve_item


def test_check_stock():
    assert check_stock("item_1") >= 0
    assert check_stock("unknown_item") == 0


def test_reserve_item():
    initial = check_stock("item_2")
    if initial > 0:
        assert reserve_item("item_2", 1) is True
    assert reserve_item("item_3", 100) is False
