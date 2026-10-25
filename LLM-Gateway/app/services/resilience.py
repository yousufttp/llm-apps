
import asyncio
import logging

from collections.abc import AsyncIterator
from contextlib import aclosing
from typing import Any

import httpx

from openai import APIConnectionError, APIStatusError
from opentelemetry.trace import Status, StatusCode

from app.routing.router import ModelRouter
from app.observability.tracing import tracer


logger = logging.getLogger(__name__)

FIRST_EVENT_TIMEOUT = 30.0
RETRY_DELAY = 1.0
MAX_PRIMARY_ATTEMPTS = 2


def is_retryable(exc: Exception) -> bool:
    """Determine whether the error is temporary."""

    if isinstance(exc, APIStatusError):
        return (
            exc.status_code in (408, 409, 429)
            or exc.status_code >= 500
        )

    if isinstance(exc, APIConnectionError):
        return True

    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return code in (408, 409, 429) or code >= 500

    if isinstance(exc, httpx.RequestError):
        return True

    if isinstance(exc, TimeoutError):
        return True

    return False


async def stream_with_resilience(
    router: ModelRouter,
    model_alias: str,
    messages: list[dict[str, str]],
    allow_cloud_fallback: bool = False
) -> AsyncIterator[dict[str, Any]]:

    candidates = [(model_alias, MAX_PRIMARY_ATTEMPTS)]

    if (
        model_alias in ("local", "local-small", "llama3.2")
        and allow_cloud_fallback
    ):
        candidates.append(("openai", 1))

    last_error = None

    with tracer.start_as_current_span("gateway.route") as span:
        span.set_attribute("gateway.requested_model", model_alias)
        span.set_attribute(
            "gateway.cloud_fallback_allowed",
            allow_cloud_fallback
        )

    for alias, max_attempts in candidates:

        try:
            provider, actual_model = router.resolve(alias)

        except (ValueError, RuntimeError):
            if last_error is not None:
                raise last_error
            raise

        for attempt in range(1, max_attempts + 1):

            emitted = False

            with tracer.start_as_current_span(
                "provider.attempt",
                attributes={
                    "gateway.provider": type(provider).__name__,
                    "gateway.model": actual_model,
                    "gateway.attempt": attempt,
                    "gateway.fallback": alias != model_alias,
                },
            ) as span:

                try:
                    stream = provider.stream_chat(
                        model=actual_model,
                        messages=messages,
                    )

                    async with aclosing(stream):

                        first_event = await asyncio.wait_for(
                            anext(stream),
                            timeout=FIRST_EVENT_TIMEOUT,
                        )

                        emitted = True

                        span.add_event("first_event_received")

                        yield {
                            "type": "route",
                            "provider": type(provider).__name__,
                            "model": actual_model,
                            "fallback": alias != model_alias,
                        }

                        yield first_event

                        async for event in stream:
                            yield event

                    span.set_status(Status(StatusCode.OK))

                    return

                except Exception as exc:

                    last_error = exc

                    span.record_exception(exc)
                    span.set_status(
                        Status(StatusCode.ERROR, type(exc).__name__)
                    )

                    # Never retry after streaming began.
                    if emitted:
                        raise

                    if not is_retryable(exc):
                        raise

                    logger.warning(
                        "Provider %s failed, attempt %s/%s: %s",
                        alias,
                        attempt,
                        max_attempts,
                        type(exc).__name__,
                    )

            # Outside provider span, but inside retry policy.
            if attempt < max_attempts:

                delay = RETRY_DELAY * (2 ** (attempt - 1))

                with tracer.start_as_current_span(
                    "retry.backoff",
                    attributes={
                        "gateway.provider_alias": alias,
                        "gateway.delay_seconds": delay,
                    },
                ):
                    await asyncio.sleep(delay)

    if last_error is not None:
        raise last_error
