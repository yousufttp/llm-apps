import pytest

from mcp_server import lookup_customer_by_mobile


def test_mcp_tool_shape():
    result = lookup_customer_by_mobile("3125550102")
    assert result["found"] is True
    assert result["customer"]["last_name"] == "Johnson"
