import pytest

from customer_data import find_customer, lookup_customer, validate_mobile_number


@pytest.mark.parametrize("number, name", [("2125550101", "Ava"), ("312-555-0102", "Marcus"), ("+1 (415) 555-0103", "Sofia")])
def test_three_customers(number, name):
    customer = find_customer(number)
    assert customer is not None
    assert customer.first_name == name


def test_unknown_customer():
    result = lookup_customer("6465550199")
    assert result["found"] is False


def test_validation():
    assert validate_mobile_number("+1 (212) 555-0101") == "2125550101"
    with pytest.raises(ValueError):
        validate_mobile_number("123")


def test_structured_result():
    result = lookup_customer("2125550101")
    customer = result["customer"]
    assert {"first_name", "last_name", "address", "devices", "plan", "promotions", "last_bill", "current_bill"} <= customer.keys()
    assert customer["devices"]
