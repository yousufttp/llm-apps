import pytest

from app.routing.router import ModelRouter


def test_local_model_routing():
    router = ModelRouter()

    provider, model = router.resolve("local")

    assert type(provider).__name__ == "OllamaProvider"
    assert model == "llama3.2"


def test_small_model_routing():
    router = ModelRouter()

    provider, model = router.resolve("local-small")

    assert type(provider).__name__ == "OllamaProvider"
    assert model == "qwen2.5:0.5b"


def test_unknown_model():
    router = ModelRouter()

    with pytest.raises(ValueError):
        router.resolve("unknown-model")