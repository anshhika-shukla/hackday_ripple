"""The canteen menu: item code -> name, price in paise, veg or not."""

MENU = {
    "CHAI": {"name": "Masala chai", "price": 1500, "veg": True},
    "SAMOSA": {"name": "Samosa", "price": 2000, "veg": True},
    "THALI": {"name": "Veg thali", "price": 9000, "veg": True},
    "PANEER": {"name": "Paneer roll", "price": 7000, "veg": True},
    "CHICKEN": {"name": "Chicken roll", "price": 8500, "veg": False},
    "LASSI": {"name": "Sweet lassi", "price": 3000, "veg": True},
}


def get_item(code: str) -> dict:
    """Look up a menu item; raises KeyError for unknown codes."""
    if code not in MENU:
        raise KeyError(f"unknown item {code!r}")
    return MENU[code]


def price_of(code: str) -> int:
    return get_item(code)["price"]


def veg_items() -> list[str]:
    return [code for code, item in MENU.items() if item["veg"]]
