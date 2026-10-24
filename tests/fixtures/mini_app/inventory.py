"""Inventory management module for mini_app."""

_STOCK = {"item_1": 10, "item_2": 5, "item_3": 0}


def check_stock(item_id: str) -> int:
    """Return available quantity for item."""
    return _STOCK.get(item_id, 0)


def reserve_item(item_id: str, quantity: int = 1) -> bool:
    """Reserve inventory for an item."""
    available = check_stock(item_id)
    if available >= quantity:
        _STOCK[item_id] -= quantity
        return True
    return False
