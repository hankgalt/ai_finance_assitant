"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

from ai_finance_assistant.api.errors import register_error_handlers
from ai_finance_assistant.api.middleware import RequestCorrelationMiddleware
from ai_finance_assistant.api.routes.health import router as health_router
from ai_finance_assistant.api.routes.v1 import router as v1_router
from ai_finance_assistant.api.services import ApplicationServices
from ai_finance_assistant.core.config import Settings, get_settings
from ai_finance_assistant.core.logging import configure_logging
from ai_finance_assistant.observability.factory import telemetry_runtime_from_settings

_httpx_instrumented = False


def create_app(settings: Settings | None = None) -> FastAPI:
    global _httpx_instrumented
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)
    telemetry = telemetry_runtime_from_settings(resolved_settings)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        services = ApplicationServices(resolved_settings, telemetry=telemetry)
        application.state.services = services
        try:
            yield
        finally:
            services.close()

    app = FastAPI(
        title=resolved_settings.app_name,
        version=resolved_settings.app_version,
        description=(
            "M5 private-demo API with authoritative versioned REST, replayable SSE, durable "
            "SQLite resources and checkpoints, deterministic finance modules, provider cache, "
            "and the six-agent LangGraph workflow."
        ),
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.state.telemetry_runtime = telemetry
    register_error_handlers(app)
    app.add_middleware(RequestCorrelationMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=[
            "Content-Type",
            "X-Request-ID",
            "Idempotency-Key",
            "Last-Event-ID",
            "traceparent",
            "tracestate",
        ],
    )
    app.include_router(health_router, prefix="/api")
    app.include_router(v1_router, prefix="/api")
    if telemetry.tracer_provider is not None and telemetry.meter_provider is not None:
        FastAPIInstrumentor.instrument_app(
            app,
            tracer_provider=telemetry.tracer_provider,
            meter_provider=telemetry.meter_provider,
            excluded_urls=".*/api/health.*",
        )
        if not _httpx_instrumented:
            HTTPXClientInstrumentor().instrument(tracer_provider=telemetry.tracer_provider)
            _httpx_instrumented = True
    return app


app = create_app()
