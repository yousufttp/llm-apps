import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import aclosing
from typing import Any

import httpx
from openai import APIConnectionError, APIStatusError

from app.routing.router import ModelRouter


logger = logging.getLogger(__name__)

FIRST_EVENT_TIMEOUT = 30.0
RETRY_DELAY = 1.0

# One initial attempt + one retry
MAX_PRIMARY_ATTEMPTS = 2


def is_retryable(exc: Exception) -> bool:
    """
    Retry temporary infrastructure errors only.
    """

    if isinstance(exc, APIStatusError):
        return exc.status_code in (408, 409, 429) or (
            exc.status_code >= 500
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

    # Primary provider
    candidates = [
        (model_alias, MAX_PRIMARY_ATTEMPTS)
    ]

    # Cloud fallback only for local models
    # and only when explicitly permitted.
    if (
        model_alias in ("local", "local-small", "llama3.2")
        and allow_cloud_fallback
    ):
        candidates.append(("openai", 1))

    last_error = None

    for alias, max_attempts in candidates:

        try:
            provider, actual_model = router.resolve(alias)
        except (ValueError, RuntimeError):
            # An unavailable fallback should not hide the
            # original provider failure.
            if last_error is not None:
                raise last_error
            raise

        for attempt in range(1, max_attempts + 1):
            emitted = False

            try:
                logger.info(
                    "LLM attempt: alias=%s provider=%s model=%s attempt=%s",
                    alias,
                    type(provider).__name__,
                    actual_model,
                    attempt
                )
                stream = provider.stream_chat(
                    model=actual_model,
                    messages=messages
                )

                # Ensure provider resources are closed even
                # if the first event fails or times out.
                async with aclosing(stream):

                    # Obtain the first event before yielding
                    # anything to the client.
                    first_event = await asyncio.wait_for(
                        anext(stream),
                        timeout=FIRST_EVENT_TIMEOUT
                    )

                    emitted = True

                    yield {
                        "type": "route",
                        "provider": type(provider).__name__,
                        "model": actual_model,
                        "fallback": alias != model_alias
                    }

                    yield first_event

                    # Continue streaming normally.
                    async for event in stream:
                        yield event

                return

            except Exception as exc:
                last_error = exc

                # No retry or fallback after an event
                # has been emitted to the client.
                if emitted:
                    raise

                if not is_retryable(exc):
                    raise

                logger.warning(
                    "Provider %s failed before streaming, "
                    "attempt %s/%s: %s",
                    alias,
                    attempt,
                    max_attempts,
                    type(exc).__name__
                )

                if attempt < max_attempts:
                    await asyncio.sleep(
                        RETRY_DELAY * (2 ** (attempt - 1))
                    )

    if last_error is not None:
        raise last_error