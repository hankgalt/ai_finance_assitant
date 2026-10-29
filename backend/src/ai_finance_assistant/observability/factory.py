"""Configuration-owned construction of vendor-neutral observability."""

from dataclasses import dataclass

from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from ai_finance_assistant.core.config import Settings
from ai_finance_assistant.observability.memory import InMemoryObservability
from ai_finance_assistant.observability.opentelemetry import OpenTelemetryObservability
from ai_finance_assistant.observability.ports import NoOpObservability, Observability
from ai_finance_assistant.observability.safe import SafeObservability


@dataclass(frozen=True)
class TelemetryRuntime:
    observability: Observability
    tracer_provider: TracerProvider | None = None
    meter_provider: MeterProvider | None = None

    def shutdown(self) -> None:
        if self.tracer_provider is not None:
            self.tracer_provider.shutdown()
        if self.meter_provider is not None:
            self.meter_provider.shutdown()


def telemetry_runtime_from_settings(settings: Settings) -> TelemetryRuntime:
    if settings.observability_mode == "disabled":
        return TelemetryRuntime(observability=NoOpObservability())
    if settings.observability_mode == "in_memory":
        return TelemetryRuntime(observability=SafeObservability(InMemoryObservability()))
    resource = Resource.create(
        {
            "service.name": "ai-finance-assistant",
            "service.version": settings.app_version,
        }
    )
    tracer_provider = TracerProvider(resource=resource)
    metric_readers = []
    if settings.otel_export_enabled:
        endpoint = settings.otel_exporter_otlp_endpoint.rstrip("/")
        tracer_provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces"))
        )
        metric_readers.append(
            PeriodicExportingMetricReader(
                OTLPMetricExporter(endpoint=f"{endpoint}/v1/metrics"),
                export_interval_millis=settings.otel_metric_export_interval_millis,
            )
        )
    meter_provider = MeterProvider(resource=resource, metric_readers=metric_readers)
    return TelemetryRuntime(
        observability=SafeObservability(
            OpenTelemetryObservability(
                tracer=tracer_provider.get_tracer("ai_finance_assistant.workflow"),
                meter=meter_provider.get_meter("ai_finance_assistant.workflow"),
            )
        ),
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
    )


def observability_from_settings(settings: Settings) -> Observability:
    return telemetry_runtime_from_settings(settings).observability
