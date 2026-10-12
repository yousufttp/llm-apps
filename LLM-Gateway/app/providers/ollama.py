import json
import httpx

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"


async def generate_chat_stream(model: str, messages: list[dict]):

    payload = {
        "model": model,
        "messages": messages,
        "stream": True
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST",
            OLLAMA_URL,
            json=payload
        ) as response:

            response.raise_for_status()

            async for line in response.aiter_lines():
                if not line:
                    continue

                data = json.loads(line)

                if data.get("error"):
                    raise RuntimeError(data["error"])

                content = data.get("message", {}).get("content", "")

                if content:
                    yield (
                        f"data: {json.dumps({'content': content})}\n\n"
                    )

                if data.get("done"):
                    usage = {
                        "prompt_tokens": data.get("prompt_eval_count", 0),
                        "completion_tokens": data.get("eval_count", 0)
                    }

                    yield f"data: {json.dumps({'usage': usage})}\n\n"
                    yield "data: [DONE]\n\n"
                    break