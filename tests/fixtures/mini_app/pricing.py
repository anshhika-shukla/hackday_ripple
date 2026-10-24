"""Pricing calculation module for mini_app."""


def apply_discount(price: float, discount: float) -> float:
    """Apply percentage discount to price."""
    if discount < 0 or discount > 1:
        raise ValueError("Discount must be between 0 and 1")
    return price * (1.0 - discount)


def calculate_tax(price: float, tax_rate: float = 0.1) -> float:
    """Calculate tax for price."""
    return price * tax_rate


def get_final_price(price: float, discount: float = 0.0, tax_rate: float = 0.1) -> float:
    """Calculate final price after discount and tax."""
    discounted = apply_discount(price, discount)
    tax = calculate_tax(discounted, tax_rate)
    return discounted + tax
