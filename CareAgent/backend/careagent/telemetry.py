import json
import logging
from opentelemetry import metrics, trace

tracer = trace.get_tracer("careagent")
meter = metrics.get_meter("careagent")
runs = meter.create_counter("careagent.runs")
escalations = meter.create_counter("careagent.escalations")
tokens = meter.create_counter("careagent.model.tokens")
latency = meter.create_histogram("careagent.run.duration", unit="s")


class JsonFormatter(logging.Formatter):
    def format(self, record):
        ctx = trace.get_current_span().get_span_context()
        return json.dumps(
            {
                "level": record.levelname,
                "event": record.getMessage(),
                "trace_id": format(ctx.trace_id, "032x"),
                "logger": record.name,
            }
        )


def configure(app, engine, config):
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("careagent")
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    # Provider SDK debug logs may contain prompts. Do not enable them in normal operation.
    logging.getLogger("LiteLLM").setLevel(logging.CRITICAL)
    if not config.telemetry_enabled:
        return
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    resource = Resource.create({"service.name": "careagent-api"})
    endpoint = config.otel_exporter_otlp_endpoint.rstrip("/")
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint + "/v1/traces")))
    trace.set_tracer_provider(provider)
    metrics.set_meter_provider(
        MeterProvider(
            resource=resource,
            metric_readers=[
                PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=endpoint + "/v1/metrics"))
            ],
        )
    )
    FastAPIInstrumentor.instrument_app(app, excluded_urls="health/live,health/ready")
