import os
from dataclasses import dataclass

from dotenv import load_dotenv

from app.providers.base import BaseLLMProvider
from app.providers.ollama import OllamaProvider
from app.providers.openai import OpenAIProvider


load_dotenv()


@dataclass(frozen=True)
class ModelConfig:
    provider: str
    model: str


MODEL_REGISTRY = {
    "llama3.2": ModelConfig(
        provider="ollama",
        model="llama3.2"
    ),
    "local": ModelConfig(
        provider="ollama",
        model="llama3.2"
    ),
    "local-small": ModelConfig(
        provider="ollama",
        model="qwen2.5:0.5b"
    ),
    "openai": ModelConfig(
        provider="openai",
        model="gpt-4.1-mini"
    )
}


class ModelRouter:

    def __init__(self):
        self.providers: dict[str, BaseLLMProvider] = {
            "ollama": OllamaProvider()
        }

        # Keep local Ollama working without a cloud API key.
        if os.getenv("OPENAI_API_KEY"):
            self.providers["openai"] = OpenAIProvider()

    def resolve(
        self,
        model_alias: str
    ) -> tuple[BaseLLMProvider, str]:

        config = MODEL_REGISTRY.get(model_alias)

        if config is None:
            raise ValueError(
                f"Unsupported model alias: {model_alias}"
            )

        provider = self.providers.get(config.provider)

        if provider is None:
            raise RuntimeError(
                f"Provider not configured: {config.provider}"
            )

        return provider, config.model
