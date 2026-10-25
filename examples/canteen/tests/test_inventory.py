from inventory import Inventory


def test_in_stock():
    assert Inventory({"SAMOSA": 3}).in_stock("SAMOSA", 3)


def test_unknown_item_not_in_stock():
    assert not Inventory({}).in_stock("SAMOSA")


def test_reserve_takes_stock():
    inv = Inventory({"SAMOSA": 3})
    assert inv.reserve("SAMOSA", 2)
    assert inv.stock["SAMOSA"] == 1


def test_reserve_fails_without_change():
    inv = Inventory({"SAMOSA": 1})
    assert not inv.reserve("SAMOSA", 2)
    assert inv.stock["SAMOSA"] == 1


def test_low_stock_sorted():
    assert Inventory({"THALI": 2, "CHAI": 50, "LASSI": 1}).low_stock() == ["LASSI", "THALI"]
