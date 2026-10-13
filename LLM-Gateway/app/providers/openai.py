from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI

from app.providers.base import BaseLLMProvider


class OpenAIProvider(BaseLLMProvider):

    def __init__(self):
        self.client = AsyncOpenAI(
            timeout=60.0,
            max_retries=0
        )

    async def stream_chat(
        self,
        model: str,
        messages: list[dict[str, str]]
    ) -> AsyncIterator[dict[str, Any]]:

        stream = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
            stream_options={
                "include_usage": True
            }
        )

        try:
            async for chunk in stream:

                for choice in chunk.choices:
                    content = choice.delta.content

                    if content:
                        yield {
                            "type": "content",
                            "content": content
                        }

                if chunk.usage is not None:
                    yield {
                        "type": "usage",
                        "prompt_tokens": chunk.usage.prompt_tokens,
                        "completion_tokens": chunk.usage.completion_tokens
                    }

        finally:
            await stream.close()