import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.providers.base import BaseLLMProvider


class OllamaProvider(BaseLLMProvider):
    """
    Ollama implementation of the common LLM provider interface.
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:11434"
    ):
        self.base_url = base_url

    async def stream_chat(
        self,
        model: str,
        messages: list[dict[str, str]]
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Call Ollama and yield normalized streaming events.
        """

        payload = {
            "model": model,
            "messages": messages,
            "stream": True
        }

        async with httpx.AsyncClient(timeout=120.0) as client:

            async with client.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json=payload
            ) as response:

                response.raise_for_status()

                async for line in response.aiter_lines():

                    if not line:
                        continue

                    data = json.loads(line)

                    if data.get("error"):
                        raise RuntimeError(
                            "Ollama generation failed"
                        )

                    content = data.get(
                        "message", {}
                    ).get("content", "")

                    if content:
                        yield {
                            "type": "content",
                            "content": content
                        }

                    if data.get("done"):
                        yield {
                            "type": "usage",
                            "prompt_tokens": data.get(
                                "prompt_eval_count", 0
                            ),
                            "completion_tokens": data.get(
                                "eval_count", 0
                            )
                        }
                        break