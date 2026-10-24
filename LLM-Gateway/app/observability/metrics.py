from prometheus_client import Counter, Histogram


REQUEST_COUNT = Counter(
    "llm_gateway_requests_total",
    "LLM requests by provider and outcome",
    ["provider", "model", "status"]
)

TOKEN_COUNT = Counter(
    "llm_gateway_tokens_total",
    "Reported tokens consumed",
    ["provider", "model", "token_type"]
)

REQUEST_DURATION = Histogram(
    "llm_gateway_duration_seconds",
    "LLM request duration in seconds",
    ["provider", "model"],
    buckets=(0.1, 0.5, 1, 2, 5, 10, 30, 60, 120)
)


def record_metrics(
    provider: str | None,
    model: str | None,
    status: str,
    duration_seconds: float,
    prompt_tokens: int | None,
    completion_tokens: int | None
):
    provider = provider or "unknown"
    model = model or "unknown"

    REQUEST_COUNT.labels(
        provider=provider,
        model=model,
        status=status
    ).inc()

    REQUEST_DURATION.labels(
        provider=provider,
        model=model
    ).observe(duration_seconds)

    if prompt_tokens is not None:
        TOKEN_COUNT.labels(
            provider=provider,
            model=model,
            token_type="input"
        ).inc(prompt_tokens)

    if completion_tokens is not None:
        TOKEN_COUNT.labels(
            provider=provider,
            model=model,
            token_type="output"
        ).inc(completion_tokens)