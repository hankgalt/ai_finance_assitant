"""Configuration-owned construction of vendor-neutral observability."""

from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider

from ai_finance_assistant.core.config import Settings
from ai_finance_assistant.observability.memory import InMemoryObservability
from ai_finance_assistant.observability.opentelemetry import OpenTelemetryObservability
from ai_finance_assistant.observability.ports import NoOpObservability, Observability
from ai_finance_assistant.observability.safe import SafeObservability


def observability_from_settings(settings: Settings) -> Observability:
    if settings.observability_mode == "disabled":
        return NoOpObservability()
    if settings.observability_mode == "in_memory":
        return SafeObservability(InMemoryObservability())
    resource = Resource.create(
        {
            "service.name": "ai-finance-assistant",
            "service.version": settings.app_version,
        }
    )
    tracer_provider = TracerProvider(resource=resource)
    meter_provider = MeterProvider(resource=resource)
    return SafeObservability(
        OpenTelemetryObservability(
            tracer=tracer_provider.get_tracer("ai_finance_assistant.workflow"),
            meter=meter_provider.get_meter("ai_finance_assistant.workflow"),
        )
    )
