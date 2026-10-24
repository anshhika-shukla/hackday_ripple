"""Shopping cart management for mini_app."""

try:
    from mini_app.inventory import reserve_item
    from mini_app.pricing import apply_discount
except ImportError:
    from inventory import reserve_item
    from pricing import apply_discount


class Cart:
    def __init__(self):
        self.items = []

    def add_item(self, item_id: str, price: float, quantity: int = 1) -> bool:
        if reserve_item(item_id, quantity):
            self.items.append({"item_id": item_id, "price": price, "qty": quantity})
            return True
        return False

    def get_total(self, discount: float = 0.0) -> float:
        subtotal = sum(item["price"] * item["qty"] for item in self.items)
        if discount > 0:
            return apply_discount(subtotal, discount)
        return subtotal
