from typing import Any

from pydantic import BaseModel, Field


class Device(BaseModel):
    name: str
    number: str


class Bill(BaseModel):
    amount: float
    due_date: str
    status: str


class Customer(BaseModel):
    mobile_number: str
    first_name: str
    last_name: str
    address: str
    devices: list[Device]
    plan: str
    promotions: list[str]
    last_bill: Bill
    current_bill: Bill


CUSTOMERS = [
    Customer(
        mobile_number="2125550101", first_name="Ava", last_name="Patel",
        address="125 Madison Avenue, New York, NY 10016",
        devices=[Device(name="iPhone 15 Pro", number="1234567890"), Device(name="iPad Air", number="2125550102")],
        plan="Unlimited Premium 5G", promotions=["20% off device protection", "Free international texting"],
        last_bill=Bill(amount=94.37, due_date="2026-08-15", status="Paid"),
        current_bill=Bill(amount=89.99, due_date="2026-10-15", status="Due"),
    ),
    Customer(
        mobile_number="3125550102", first_name="Marcus", last_name="Johnson",
        address="440 North Wells Street, Chicago, IL 60654",
        devices=[Device(name="Samsung Galaxy S24", number="3125550102")],
        plan="Unlimited Essentials", promotions=["$10 loyalty credit through December"],
        last_bill=Bill(amount=68.42, due_date="2026-08-20", status="Paid"),
        current_bill=Bill(amount=72.50, due_date="2026-10-20", status="Due"),
    ),
    Customer(
        mobile_number="4155550103", first_name="Sofia", last_name="Garcia",
        address="88 Market Street, San Francisco, CA 94105",
        devices=[Device(name="Google Pixel 9", number="4155550103"), Device(name="Apple Watch Series 10", number="4155550104")],
        plan="Family Unlimited Plus", promotions=["Free Apple TV+ for 6 months", "50% off the third line"],
        last_bill=Bill(amount=121.08, due_date="2026-08-25", status="Paid"),
        current_bill=Bill(amount=119.50, due_date="2026-10-25", status="Due"),
    ),
]


def normalize_mobile_number(value: str) -> str:
    digits = "".join(character for character in value if character.isdigit())
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits


def validate_mobile_number(value: str) -> str:
    normalized = normalize_mobile_number(value)
    if len(normalized) != 10:
        raise ValueError("Enter a valid 10-digit US mobile number.")
    return normalized


def find_customer(mobile_number: str) -> Customer | None:
    normalized = normalize_mobile_number(mobile_number)
    return next((customer for customer in CUSTOMERS if customer.mobile_number == normalized), None)


def lookup_customer(mobile_number: str, first_name: str = "", last_name: str = "") -> dict[str, Any]:
    customer = find_customer(mobile_number)
    if customer and first_name.strip() and customer.first_name.casefold() != first_name.strip().casefold():
        customer = None
    if customer and last_name.strip() and customer.last_name.casefold() != last_name.strip().casefold():
        customer = None
    if customer is None:
        return {"found": False, "mobile_number": normalize_mobile_number(mobile_number), "message": "No customer matched the supplied search criteria."}
    customer_data = customer.model_dump()
    return {
        "found": True,
        "mobile_number": customer.mobile_number,
        "first_name": customer.first_name,
        "last_name": customer.last_name,
        "customer": customer_data,
    }
