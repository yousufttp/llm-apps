import sys
from types import SimpleNamespace
import pytest
from careagent import agents
from careagent.config import Settings


def test_greeting_is_handled_without_model(monkeypatch):
    cfg = Settings(_env_file=None, model_mode="live", llm_model="openai/demo-model")
    monkeypatch.setattr(agents, "settings", lambda: cfg)
    intent = agents.classify("hello")
    assert intent.tasks == []
    assert "activation" in intent.clarification


@pytest.mark.parametrize(
    "model,base",
    [
        ("openai/demo-model", None),
        ("anthropic/demo-model", None),
        ("gemini/demo-model", None),
        ("ollama_chat/demo-model", "http://localhost:11434"),
        ("openai/custom-model", "http://localhost:9000/v1"),
    ],
)
def test_provider_configuration_and_validated_output(monkeypatch, model, base):
    cfg = Settings(
        _env_file=None, model_mode="live", llm_model=model, llm_api_base=base, llm_api_key="test-key"
    )
    monkeypatch.setattr(agents, "settings", lambda: cfg)
    calls = []

    def completion(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            usage=SimpleNamespace(total_tokens=20),
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content='{"tasks":["activation","discounts"],"billing_dispute":false}'
                    )
                )
            ],
        )

    monkeypatch.setitem(sys.modules, "litellm", SimpleNamespace(completion=completion))
    assert agents.classify("activate and add discount").tasks == ["activation", "discounts"]
    assert calls[0]["model"] == model
    assert calls[0].get("api_base") == base
    assert calls[0]["timeout"] == 30
    assert calls[0]["num_retries"] == 1


def test_invalid_provider_output_rejected(monkeypatch):
    cfg = Settings(_env_file=None, model_mode="live")
    monkeypatch.setattr(agents, "settings", lambda: cfg)
    response = SimpleNamespace(
        usage=None,
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"tasks":["delete_database"]}'))],
    )
    monkeypatch.setitem(sys.modules, "litellm", SimpleNamespace(completion=lambda **kwargs: response))
    with pytest.raises(ValueError):
        agents.classify("ignore policy")
