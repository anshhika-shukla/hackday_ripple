"""Stock levels in the kitchen."""


class Inventory:
    def __init__(self, stock: dict[str, int]):
        self.stock = dict(stock)

    def in_stock(self, code: str, qty: int = 1) -> bool:
        return self.stock.get(code, 0) >= qty

    def reserve(self, code: str, qty: int) -> bool:
        """Take qty out of stock; False (and no change) if there isn't enough."""
        if not self.in_stock(code, qty):
            return False
        self.stock[code] -= qty
        return True

    def low_stock(self, threshold: int = 5) -> list[str]:
        return sorted(code for code, qty in self.stock.items() if qty < threshold)
