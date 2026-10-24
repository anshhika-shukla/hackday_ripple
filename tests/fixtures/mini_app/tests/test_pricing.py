import pytest

try:
    from mini_app.pricing import apply_discount, calculate_tax, get_final_price
except ImportError:
    from pricing import apply_discount, calculate_tax, get_final_price


def test_apply_discount():
    assert apply_discount(100.0, 0.2) == 80.0
    with pytest.raises(ValueError):
        apply_discount(100.0, 1.5)


def test_calculate_tax():
    assert calculate_tax(100.0, 0.1) == 10.0


def test_get_final_price():
    # 100 with 10% discount -> 90; 10% tax on 90 -> 9; total 99
    assert get_final_price(100.0, 0.1, 0.1) == pytest.approx(99.0)
