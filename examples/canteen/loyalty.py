"""Loyalty points: earn 1 point per ₹20 spent, each point is worth ₹1 when redeemed."""

PAISE_PER_POINT_EARNED = 2000
PAISE_PER_POINT_REDEEMED = 100


def points_for(amount: int) -> int:
    return amount // PAISE_PER_POINT_EARNED


def redeem_value(points: int, bill: int) -> int:
    """Value of redeemed points, never more than the bill."""
    if points < 0:
        raise ValueError("points cannot be negative")
    return min(points * PAISE_PER_POINT_REDEEMED, bill)
