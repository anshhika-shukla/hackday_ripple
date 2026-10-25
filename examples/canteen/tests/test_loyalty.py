import pytest

from loyalty import points_for, redeem_value


def test_no_points_below_twenty_rupees():
    assert points_for(1999) == 0


def test_one_point_per_twenty_rupees():
    assert points_for(2000) == 1
    assert points_for(12600) == 6


def test_redeem_value():
    assert redeem_value(10, 5000) == 1000


def test_redeem_capped_at_bill():
    assert redeem_value(100, 5000) == 5000


def test_redeem_negative_points():
    with pytest.raises(ValueError):
        redeem_value(-1, 5000)
