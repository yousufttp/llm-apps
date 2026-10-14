import json
import logging
import os
import time
import uuid

from contextlib import asynccontextmanager

import redis.asyncio as redis
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.schemas import ChatRequest
from app.routing.router import ModelRouter, MODEL_REGISTRY
from app.services.resilience import stream_with_resilience
from app.services.usage import (
    init_database,
    save_usage,
    get_usage,
    estimate_cost
)
from app.security.auth import verify_api_key
from app.security.rate_limit import enforce_rate_limit


load_dotenv()
logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)
router = ModelRouter()


@asynccontextmanager
async def lifespan(app: FastAPI):

    # Initialize SQLite before accepting requests
    await init_database()
    logger.info("SQLite database initialized")

    # Initialize Redis
    app.state.redis = redis.from_url(
        os.getenv(
            "REDIS_URL",
            "redis://127.0.0.1:6379/0"
        ),
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2
    )

    try:
        await app.state.redis.ping()
        logger.info("Redis connected")

        yield

    finally:
        await app.state.redis.aclose()


app = FastAPI(
    title="My LLM Gateway",
    version="0.7.0",
    lifespan=lifespan
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get(
    "/v1/models",
    dependencies=[Depends(verify_api_key)]
)
async def list_models():
    return {"models": list(MODEL_REGISTRY.keys())}


# Protected usage endpoint.
# For now, our one dev key can see every record.
@app.get(
    "/v1/usage",
    dependencies=[Depends(verify_api_key)]
)
async def list_usage(
    limit: int = Query(default=20, ge=1, le=100)
):
    return {"records": await get_usage(limit)}


@app.post(
    "/v1/chat/completions",
    dependencies=[Depends(enforce_rate_limit)]
)
async def chat(request: ChatRequest):

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

    messages = [
        message.model_dump()
        for message in request.messages
    ]

    request_id = str(uuid.uuid4())
    started = time.perf_counter()

    async def event_stream():

        actual_provider = None
        actual_model = None
        prompt_tokens = None
        completion_tokens = None
        status = "failed"

        try:
            async for event in stream_with_resilience(
                router=router,
                model_alias=request.model,
                messages=messages,
                allow_cloud_fallback=request.allow_cloud_fallback
            ):

                event_type = event["type"]

                if event_type == "route":
                    actual_provider = event["provider"]
                    actual_model = event["model"]

                    output = {
                        "request_id": request_id,
                        "provider": actual_provider,
                        "model": actual_model,
                        "fallback": event["fallback"]
                    }

                elif event_type == "content":
                    output = {
                        "content": event["content"]
                    }

                elif event_type == "usage":
                    prompt_tokens = event["prompt_tokens"]
                    completion_tokens = event["completion_tokens"]

                    output = {
                        "usage": {
                            "prompt_tokens": prompt_tokens,
                            "completion_tokens": completion_tokens
                        }
                    }

                else:
                    continue

                yield f"data: {json.dumps(output)}\n\n"

            status = "success"
            yield "data: [DONE]\n\n"

        except Exception:
            logger.exception(
                "Gateway request failed: %s",
                request_id
            )

            yield (
                "event: error\n"
                'data: {"error":"LLM request failed"}\n\n'
            )

        finally:
            latency_ms = int(
                (time.perf_counter() - started) * 1000
            )

            cost = estimate_cost(
                actual_provider,
                actual_model,
                prompt_tokens,
                completion_tokens
            )

            record = {
                "request_id": request_id,
                "requested_model": request.model,
                "actual_provider": actual_provider,
                "actual_model": actual_model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "estimated_cost_usd": cost,
                "latency_ms": latency_ms,
                "status": status
            }

            try:
                await save_usage(record)
                logger.info(
                    "Usage saved: request=%s status=%s",
                    request_id,
                    status
                )

            except Exception:
                logger.exception(
                    "Failed to save usage: %s",
                    request_id
                )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )