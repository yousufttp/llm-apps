import pytest
import httpx

from app.services import resilience


class FakeProvider:
    def __init__(self, fail_count=0):
        self.fail_count = fail_count
        self.calls = 0

    async def stream_chat(self, model, messages):
        self.calls += 1

        if self.calls <= self.fail_count:
            raise httpx.ConnectError("Simulated connection failure")

        yield {"type": "content", "content": "Hello"}

        yield {
            "type": "usage",
            "prompt_tokens": 10,
            "completion_tokens": 5
        }


class FakeRouter:
    def __init__(self, local, cloud):
        self.local = local
        self.cloud = cloud

    def resolve(self, alias):
        if alias == "local":
            return self.local, "llama3.2"

        if alias == "openai":
            return self.cloud, "gpt-4.1-mini"

        raise ValueError("Unknown model")


@pytest.mark.asyncio
async def test_retry_then_success(monkeypatch):

    monkeypatch.setattr(resilience, "RETRY_DELAY", 0)

    local = FakeProvider(fail_count=1)
    cloud = FakeProvider()

    router = FakeRouter(local, cloud)

    events = [
        event async for event in resilience.stream_with_resilience(
            router=router,
            model_alias="local",
            messages=[{"role": "user", "content": "Hello"}],
            allow_cloud_fallback=False
        )
    ]

    assert local.calls == 2
    assert cloud.calls == 0
    assert any(e["type"] == "content" for e in events)


@pytest.mark.asyncio
async def test_fallback_to_openai(monkeypatch):

    monkeypatch.setattr(resilience, "RETRY_DELAY", 0)

    local = FakeProvider(fail_count=10)
    cloud = FakeProvider()

    router = FakeRouter(local, cloud)

    events = [
        event async for event in resilience.stream_with_resilience(
            router=router,
            model_alias="local",
            messages=[{"role": "user", "content": "Hello"}],
            allow_cloud_fallback=True
        )
    ]

    assert local.calls == 2
    assert cloud.calls == 1

    route = next(e for e in events if e["type"] == "route")

    assert route["fallback"] is True
    assert route["model"] == "gpt-4.1-mini"