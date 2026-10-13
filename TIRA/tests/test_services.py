from services.order_service import check_order_status


def test_unknown_order_is_unknown():
    assert check_order_status("INC9999")["order_status"] == "unknown"
