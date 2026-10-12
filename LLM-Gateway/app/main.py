from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from app.schemas import ChatRequest
from app.providers.ollama import generate_chat_stream


app = FastAPI(
    title="My LLM Gateway",
    version="0.2.0"
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/v1/chat/completions")
async def chat(request: ChatRequest):

    if request.model != "llama3.2":
        raise HTTPException(
            status_code=400,
            detail="Unsupported model"
        )

    messages = [
        message.model_dump()
        for message in request.messages
    ]

    return StreamingResponse(
        generate_chat_stream(
            model=request.model,
            messages=messages
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )