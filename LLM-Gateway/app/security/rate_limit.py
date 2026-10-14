import hashlib
import os

from fastapi import Depends, HTTPException, Request, Security
from redis.exceptions import RedisError

from app.security.auth import (
    api_key_header,
    verify_api_key
)


# Atomic Redis script for fixed-window rate limiting
RATE_LIMIT_SCRIPT = """
local count = redis.call('INCR', KEYS[1])

if count == 1 then
    redis.call('EXPIRE', KEYS[1], tonumber(ARGV[1]))
end

local ttl = redis.call('TTL', KEYS[1])

return {count, ttl}
"""


async def enforce_rate_limit(
    request: Request,
    api_key: str | None = Security(api_key_header),
    _authenticated: bool = Depends(verify_api_key)
):
    """
    Limit requests per gateway API key.

    Default: 5 requests per 60 seconds.
    """

    limit = int(os.getenv("GATEWAY_RPM_LIMIT", "5"))

    if limit < 1:
        raise HTTPException(
            status_code=503,
            detail="Invalid gateway rate limit configuration"
        )

    client_id = hashlib.sha256(
        api_key.encode("utf-8")
    ).hexdigest()

    redis_key = f"gateway:rate:{client_id}"

    try:
        count, ttl = await request.app.state.redis.eval(
            RATE_LIMIT_SCRIPT,
            1,
            redis_key,
            60
        )

    except RedisError:
        raise HTTPException(
            status_code=503,
            detail="Rate limiter unavailable"
        )

    if count > limit:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={
                "Retry-After": str(max(int(ttl), 1))
            }
        )