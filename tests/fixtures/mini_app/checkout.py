"""Order checkout processor for mini_app."""

try:
    from mini_app.cart import Cart
    from mini_app.pricing import get_final_price
    from mini_app.utils import format_currency
except ImportError:
    from cart import Cart
    from pricing import get_final_price
    from utils import format_currency


def process_order(cart: Cart, discount: float = 0.0) -> dict:
    """Process cart items and return final order receipt."""
    total = cart.get_total(discount=0.0)
    final = get_final_price(total, discount=discount)
    formatted = format_currency(final)
    return {
        "items_count": len(cart.items),
        "total": final,
        "formatted_total": formatted,
        "status": "confirmed",
    }
