from reports import daily_sales, summary_line, top_items

ORDERS = [
    {"lines": {"CHAI": 2, "SAMOSA": 1}, "total": 5000},
    {"lines": {"CHAI": 1, "THALI": 1}, "total": 10500},
]


def test_daily_sales():
    assert daily_sales(ORDERS) == 15500


def test_daily_sales_empty():
    assert daily_sales([]) == 0


def test_top_items():
    assert top_items(ORDERS, n=2) == ["CHAI", "SAMOSA"]


def test_summary_line():
    assert summary_line(ORDERS) == "2 orders, ₹155.00 in sales"


def test_summary_line_empty():
    assert summary_line([]) == "0 orders, ₹0.00 in sales"
