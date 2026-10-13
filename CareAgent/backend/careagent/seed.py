from .auth import hasher
from .db import session_factory
from .models import Account, User, Service, Invoice, Promotion, Device


def seed(factory=None):
    factory = factory or session_factory()
    with factory.begin() as db:
        if db.get(Account, "demo-alex"):
            return
        db.add_all(
            [
                Account(id="demo-alex", name="Alex Morgan", restricted=0),
                Account(id="demo-jordan", name="Jordan Lee", restricted=1),
            ]
        )
        db.flush()
        password = hasher.hash("CareDemo123!")
        db.add_all(
            [
                User(
                    id="user-alex",
                    email="alex@example.test",
                    password_hash=password,
                    role="customer",
                    account_id="demo-alex",
                ),
                User(
                    id="user-jordan",
                    email="jordan@example.test",
                    password_hash=password,
                    role="customer",
                    account_id="demo-jordan",
                ),
                User(
                    id="user-operator", email="operator@example.test", password_hash=password, role="operator"
                ),
            ]
        )
        rows = [
            ("mobile-main", "demo-alex", "mobile", "Personal mobile · 0101", "Unlimited Mobile", "active"),
            ("mobile-new", "demo-alex", "mobile", "New mobile · 0102", "Essential Mobile", "pending"),
            ("mobile-paused", "demo-alex", "mobile", "Travel mobile · 0103", "Essential Mobile", "suspended"),
            ("broadband-home", "demo-alex", "broadband", "Home broadband", "Fiber 500", "active"),
            ("broadband-new", "demo-alex", "broadband", "New broadband", "Fiber 100", "pending"),
            ("broadband-paused", "demo-alex", "broadband", "Seasonal broadband", "Fiber 100", "suspended"),
            (
                "mobile-restricted",
                "demo-jordan",
                "mobile",
                "Restricted mobile · 0201",
                "Essential Mobile",
                "suspended",
            ),
        ]
        db.add_all(
            [
                Service(id=i, account_id=a, kind=k, label=label, plan=p, status=s, version=1)
                for i, a, k, label, p, s in rows
            ]
        )
        db.add_all(
            [
                Invoice(
                    id="invoice-alex",
                    account_id="demo-alex",
                    total_cents=13500,
                    credit_cents=0,
                    breakdown="Unlimited Mobile $60; Fiber 500 $65; taxes and fees $10. Pending and suspended services have no charge in this demo.",
                ),
                Invoice(
                    id="invoice-jordan",
                    account_id="demo-jordan",
                    total_cents=4500,
                    credit_cents=0,
                    breakdown="Previous Essential Mobile cycle $40; taxes and fees $5.",
                ),
                Promotion(
                    code="MOBILE10",
                    service_kind="mobile",
                    description="Apply a $10 monthly mobile discount for 3 simulated billing cycles.",
                ),
                Promotion(
                    code="FIBER15",
                    service_kind="broadband",
                    description="Apply a $15 monthly broadband discount for 3 simulated billing cycles.",
                ),
            ]
        )
        db.flush()
        db.add_all(
            [
                Device(id="device-main", service_id="mobile-main", model="Demo Phone 13", eligible=1),
                Device(
                    id="device-new", service_id="mobile-new", model="Demo Phone 16 (financed)", eligible=0
                ),
            ]
        )


if __name__ == "__main__":
    seed()
