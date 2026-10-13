import json
import logging

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from app.schemas import ChatRequest
from app.routing.router import ModelRouter, MODEL_REGISTRY
from app.services.resilience import stream_with_resilience


app = FastAPI(
    title="My LLM Gateway",
    version="0.5.0"
)

router = ModelRouter()
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/v1/models")
async def list_models():
    return {
        "models": list(MODEL_REGISTRY.keys())
    }


@app.post("/v1/chat/completions")
async def chat(request: ChatRequest):

    # Validate primary model selection before streaming.
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

    async def event_stream():

        try:
            async for event in stream_with_resilience(
                router=router,
                model_alias=request.model,
                messages=messages,
                allow_cloud_fallback=request.allow_cloud_fallback
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

                yield f"data: {json.dumps(output)}\n\n"

            yield "data: [DONE]\n\n"

        except Exception:
            logger.exception(
                "Gateway request failed"
            )

            yield (
                "event: error\n"
                'data: {"error":"LLM request failed"}\n\n'
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )