"""A customer's cart."""

from pricing import line_total


class Cart:
    def __init__(self):
        self.lines: dict[str, int] = {}

    def add(self, code: str, qty: int = 1) -> None:
        line_total(code, qty)  # validates the item code and quantity
        self.lines[code] = self.lines.get(code, 0) + qty

    def remove(self, code: str) -> None:
        self.lines.pop(code, None)

    def count(self) -> int:
        return sum(self.lines.values())

    def subtotal(self) -> int:
        return sum(line_total(code, qty) for code, qty in self.lines.items())
