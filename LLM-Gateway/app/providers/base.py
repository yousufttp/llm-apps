from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any


class BaseLLMProvider(ABC):
    """
    Common interface for all LLM providers.

    Every provider (Ollama, OpenAI, Claude, etc.)
    must implement the stream_chat() method.

    The provider must return normalized events
    so that the gateway can handle all providers
    using the same logic.
    """

    @abstractmethod
    def stream_chat(
        self,
        model: str,
        messages: list[dict[str, str]]
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Stream responses from an LLM provider.

        Parameters:
            model:
                Actual model name, such as
                'llama3.2' or 'gpt-4.1-mini'.

            messages:
                Conversation messages containing
                roles and content.

        Yields:
            Normalized event dictionaries.

        Content event:
            {
                "type": "content",
                "content": "Hello"
            }

        Usage event:
            {
                "type": "usage",
                "prompt_tokens": 10,
                "completion_tokens": 20
            }

        Implementations should use async def
        with yield to produce these events.
        """
        ...