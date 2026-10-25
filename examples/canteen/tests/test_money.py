from money import format_rupees, percent_of, round_to_rupee


def test_format_rupees_thousands():
    assert format_rupees(1234567) == "₹12,345.67"


def test_format_rupees_zero_and_paise():
    assert format_rupees(0) == "₹0.00"
    assert format_rupees(5) == "₹0.05"


def test_format_rupees_negative():
    assert format_rupees(-250) == "-₹2.50"


def test_round_to_rupee():
    assert round_to_rupee(1250) == 1300
    assert round_to_rupee(1249) == 1200
    assert round_to_rupee(1300) == 1300


def test_percent_of_rounds_down():
    assert percent_of(1000, 5) == 50
    assert percent_of(999, 10) == 99
