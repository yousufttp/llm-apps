
import json
import logging
import os
import time

from contextlib import asynccontextmanager

import redis.asyncio as redis
from dotenv import load_dotenv
from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Request,
)
from fastapi.responses import Response, StreamingResponse
from prometheus_client import (
    generate_latest,
    CONTENT_TYPE_LATEST,
)

from app.schemas import ChatRequest
from app.routing.router import ModelRouter, MODEL_REGISTRY
from app.services.resilience import stream_with_resilience
from app.services.usage import (
    init_database,
    save_usage,
    get_usage,
    estimate_cost,
)

from app.security.auth import verify_api_key
from app.security.rate_limit import enforce_rate_limit

from app.observability.request_id import (
    request_id_middleware,
    log_event,
)
from app.observability.metrics import record_metrics
from app.observability.tracing import (
    traced_stream,
    shutdown_tracing,
)


# ------------------------------------------
# Configuration
# ------------------------------------------

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = ModelRouter()


# ------------------------------------------
# Startup and shutdown
# ------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):

    await init_database()
    logger.info("SQLite initialized")

    app.state.redis = redis.from_url(
        os.getenv(
            "REDIS_URL",
            "redis://127.0.0.1:6379/0"
        ),
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )

    try:
        await app.state.redis.ping()
        logger.info("Redis connected")

        yield

    finally:
        await app.state.redis.aclose()
        shutdown_tracing()
        logger.info("Gateway shutdown complete")


# ------------------------------------------
# FastAPI initialization
# ------------------------------------------

app = FastAPI(
    title="My LLM Gateway",
    version="0.9.0",
    lifespan=lifespan,
)

app.middleware("http")(request_id_middleware)


# ------------------------------------------
# Health endpoint
# ------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok"}


# ------------------------------------------
# Available models
# ------------------------------------------

@app.get(
    "/v1/models",
    dependencies=[Depends(verify_api_key)]
)
async def list_models():
    return {
        "models": list(MODEL_REGISTRY.keys())
    }


# ------------------------------------------
# SQLite usage endpoint
# ------------------------------------------

@app.get(
    "/v1/usage",
    dependencies=[Depends(verify_api_key)]
)
async def list_usage(
    limit: int = Query(default=20, ge=1, le=100)
):
    return {
        "records": await get_usage(limit)
    }


# ------------------------------------------
# Prometheus metrics endpoint
# ------------------------------------------

@app.get(
    "/metrics",
    dependencies=[Depends(verify_api_key)]
)
async def metrics():

    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


# ------------------------------------------
# Chat Completions endpoint
# ------------------------------------------

@app.post(
    "/v1/chat/completions",
    dependencies=[Depends(enforce_rate_limit)]
)
async def chat(
    request: ChatRequest,
    http_request: Request,
):

    # Validate the requested model.
    try:
        router.resolve(request.model)

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        ) from exc

    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc)
        ) from exc

    # Convert Pydantic messages to dictionaries.
    messages = [
        message.model_dump()
        for message in request.messages
    ]

    # Use the same ID in logs, SQLite and tracing.
    request_id = http_request.state.request_id

    started = time.perf_counter()

    # --------------------------------------
    # Streaming response generator
    # --------------------------------------

    async def event_stream():

        actual_provider = None
        actual_model = None

        prompt_tokens = None
        completion_tokens = None

        status = "failed"

        try:
            # Resilience handles routing, retry,
            # timeout and permitted fallback.
            #
            # traced_stream adds OpenTelemetry
            # tracing around the streaming operation.

            async for event in traced_stream(
                stream_with_resilience(
                    router=router,
                    model_alias=request.model,
                    messages=messages,
                    allow_cloud_fallback=(
                        request.allow_cloud_fallback
                    ),
                ),
                request_id=request_id,
                requested_model=request.model,
            ):

                event_type = event["type"]

                # ------------------------------
                # Provider selection
                # ------------------------------

                if event_type == "route":

                    actual_provider = event["provider"]
                    actual_model = event["model"]

                    log_event(
                        "provider_selected",
                        request_id=request_id,
                        provider=actual_provider,
                        model=actual_model,
                        fallback=event["fallback"],
                    )

                    output = {
                        "request_id": request_id,
                        "provider": actual_provider,
                        "model": actual_model,
                        "fallback": event["fallback"],
                    }

                # ------------------------------
                # Streaming content
                # ------------------------------

                elif event_type == "content":

                    output = {
                        "content": event["content"]
                    }

                # ------------------------------
                # Token usage
                # ------------------------------

                elif event_type == "usage":

                    prompt_tokens = event["prompt_tokens"]
                    completion_tokens = event["completion_tokens"]

                    output = {
                        "usage": {
                            "prompt_tokens": prompt_tokens,
                            "completion_tokens": completion_tokens,
                        }
                    }

                else:
                    continue

                # Convert normalized event to SSE.
                yield f"data: {json.dumps(output)}\n\n"

            # Entire provider stream completed.
            status = "success"

            yield "data: [DONE]\n\n"

        except Exception:
            logger.exception(
                "Gateway request failed: %s",
                request_id,
            )

            yield (
                "event: error\n"
                'data: {"error":"LLM request failed"}\n\n'
            )

        finally:

            duration_seconds = (
                time.perf_counter() - started
            )

            latency_ms = int(
                duration_seconds * 1000
            )

            # ------------------------------
            # Prometheus metrics
            # ------------------------------

            record_metrics(
                provider=actual_provider,
                model=actual_model,
                status=status,
                duration_seconds=duration_seconds,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )

            # ------------------------------
            # Calculate estimated cost
            # ------------------------------

            cost = estimate_cost(
                actual_provider,
                actual_model,
                prompt_tokens,
                completion_tokens,
            )

            # ------------------------------
            # Build SQLite record
            # ------------------------------

            record = {
                "request_id": request_id,
                "requested_model": request.model,
                "actual_provider": actual_provider,
                "actual_model": actual_model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "estimated_cost_usd": cost,
                "latency_ms": latency_ms,
                "status": status,
            }

            # ------------------------------
            # Structured completion log
            # ------------------------------

            log_event(
                "request_completed",
                request_id=request_id,
                provider=actual_provider,
                model=actual_model,
                status=status,
                latency_ms=latency_ms,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )

            # ------------------------------
            # Persist usage in SQLite
            # ------------------------------

            try:
                await save_usage(record)

                logger.info(
                    "Usage saved: request=%s",
                    request_id,
                )

            except Exception:
                logger.exception(
                    "Usage persistence failed: %s",
                    request_id,
                )

    # --------------------------------------
    # Return SSE response
    # --------------------------------------

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
