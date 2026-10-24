import uuid
import json
import logging
from datetime import datetime, timezone

from fastapi import Request


logger = logging.getLogger("gateway.observability")


def log_event(event: str, **fields):
    """Write a structured JSON log entry."""

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **fields
    }

    logger.info(json.dumps(record))


async def request_id_middleware(
    request: Request,
    call_next
):
    # Generate a unique ID for every incoming request.
    request_id = str(uuid.uuid4())

    # Make it accessible to FastAPI endpoints.
    request.state.request_id = request_id

    log_event(
        "request_received",
        request_id=request_id,
        method=request.method,
        path=request.url.path
    )

    try:
        response = await call_next(request)

    except Exception:
        logger.exception(
            "Unhandled gateway error: request_id=%s",
            request_id
        )
        raise

    response.headers["X-Request-ID"] = request_id

    log_event(
        "response_started",
        request_id=request_id,
        status_code=response.status_code
    )

    return response