"""End-of-day reports for the canteen manager."""

from money import format_rupees


def daily_sales(orders: list[dict]) -> int:
    return sum(order["total"] for order in orders)


def top_items(orders: list[dict], n: int = 3) -> list[str]:
    counts: dict[str, int] = {}
    for order in orders:
        for code, qty in order["lines"].items():
            counts[code] = counts.get(code, 0) + qty
    return [code for code, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:n]]


def summary_line(orders: list[dict]) -> str:
    return f"{len(orders)} orders, {format_rupees(daily_sales(orders))} in sales"
