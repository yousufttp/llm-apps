
from collections.abc import AsyncIterator
from typing import Any

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
)


# Configure OpenTelemetry for our Gateway.
trace_provider = TracerProvider(
    resource=Resource.create({
        "service.name": "llm-gateway",
        "service.version": "0.9.0",
    })
)

# Export completed spans to the terminal.
trace_provider.add_span_processor(
    BatchSpanProcessor(ConsoleSpanExporter())
)

trace.set_tracer_provider(trace_provider)

tracer = trace.get_tracer("llm-gateway")


async def traced_stream(
    events: AsyncIterator[dict[str, Any]],
    request_id: str,
    requested_model: str
) -> AsyncIterator[dict[str, Any]]:
    """
    Trace a complete LLM streaming operation.

    Captures:
      - Request ID
      - Requested model alias
      - Actual provider and model
      - Fallback selection
      - Input and output token usage
      - Errors
      - Stream duration
    """

    with tracer.start_as_current_span(
        "llm.chat",
        attributes={
            "gateway.request_id": request_id,
            "gateway.requested_model": requested_model,
        }
    ) as span:

        try:
            async for event in events:

                event_type = event.get("type")

                if event_type == "route":
                    span.set_attribute(
                        "gateway.actual_provider",
                        event["provider"]
                    )
                    span.set_attribute(
                        "gateway.actual_model",
                        event["model"]
                    )
                    span.set_attribute(
                        "gateway.fallback",
                        event["fallback"]
                    )

                elif event_type == "usage":
                    span.set_attribute(
                        "gateway.input_tokens",
                        event["prompt_tokens"]
                    )
                    span.set_attribute(
                        "gateway.output_tokens",
                        event["completion_tokens"]
                    )

                yield event

            span.set_status(Status(StatusCode.OK))

        except Exception as exc:

            span.record_exception(exc)

            span.set_status(
                Status(
                    StatusCode.ERROR,
                    type(exc).__name__
                )
            )

            raise


def shutdown_tracing():
    """Flush and close the tracing exporter."""
    trace_provider.shutdown()
