from mcp.server.fastmcp import FastMCP

from customer_data import lookup_customer

mcp = FastMCP("customer-lookup")


@mcp.tool()
def lookup_customer_by_mobile(mobile_number: str, first_name: str = "", last_name: str = "") -> dict:
    """Look up a demo customer by mobile number, optionally checking first and last name."""
    return lookup_customer(mobile_number, first_name, last_name)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
