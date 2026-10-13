import os
import secrets

from dotenv import load_dotenv
from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader


# Load environment variables
load_dotenv()


# Define the header expected from clients
api_key_header = APIKeyHeader(
    name="X-API-Key",
    auto_error=False
)


async def verify_api_key(
    api_key: str | None = Security(api_key_header)
):
    """
    Authenticate incoming gateway requests
    using the X-API-Key header.
    """

    expected_key = os.getenv("GATEWAY_API_KEY")

    if not expected_key:
        raise HTTPException(
            status_code=503,
            detail="Gateway authentication is not configured"
        )

    if not api_key or not secrets.compare_digest(
        api_key,
        expected_key
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid gateway API key"
        )

    return True