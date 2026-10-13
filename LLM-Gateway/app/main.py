import json
import logging

import httpx
from openai import APIError

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from app.schemas import ChatRequest
from app.routing.router import ModelRouter, MODEL_REGISTRY


# Initialize FastAPI
app = FastAPI(
    title="My LLM Gateway",
    version="0.4.0"
)

# Initialize Model Router
router = ModelRouter()

# Initialize Logger
logger = logging.getLogger(__name__)


# -----------------------------------
# Health Check API
# -----------------------------------
@app.get("/health")
async def health():
    return {"status": "ok"}


# -----------------------------------
# List Available Models
# -----------------------------------
@app.get("/v1/models")
async def list_models():
    return {
        "models": list(MODEL_REGISTRY.keys())
    }


# -----------------------------------
# Chat Completions API
# -----------------------------------
@app.post("/v1/chat/completions")
async def chat(request: ChatRequest):

    # Step 1: Resolve provider and model
    try:
        provider, actual_model = router.resolve(
            request.model
        )

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

    # Step 2: Convert Pydantic messages to dictionaries
    messages = [
        message.model_dump()
        for message in request.messages
    ]

    # Step 3: Stream response from the selected provider
    async def event_stream():

        try:
            async for event in provider.stream_chat(
                model=actual_model,
                messages=messages
            ):

                if event["type"] == "content":
                    output = {
                        "content": event["content"]
                    }

                elif event["type"] == "usage":
                    output = {
                        "usage": {
                            "prompt_tokens": event["prompt_tokens"],
                            "completion_tokens": event["completion_tokens"]
                        }
                    }

                else:
                    continue

                # Convert normalized event into SSE
                yield f"data: {json.dumps(output)}\n\n"

            # Signal successful stream completion
            yield "data: [DONE]\n\n"

        except (
            httpx.HTTPError,
            APIError,
            json.JSONDecodeError,
            RuntimeError,
            KeyError,
            TypeError
        ):
            logger.exception(
                "LLM provider stream failed"
            )

            # Return SSE error event
            yield (
                "event: error\n"
                'data: {"error": "Provider request failed"}\n\n'
            )

    # Step 4: Return streaming HTTP response
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )