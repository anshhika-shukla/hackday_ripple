import pytest

from pricing import gst, line_total, student_discount


def test_line_total():
    assert line_total("SAMOSA", 3) == 6000


def test_line_total_rejects_zero_quantity():
    with pytest.raises(ValueError):
        line_total("SAMOSA", 0)


def test_line_total_unknown_item():
    with pytest.raises(KeyError):
        line_total("PIZZA", 1)


def test_student_discount():
    assert student_discount(10000, True) == 1000


def test_no_discount_for_non_students():
    assert student_discount(10000, False) == 0


def test_gst():
    assert gst(10000) == 500


def test_gst_on_zero():
    assert gst(0) == 0
