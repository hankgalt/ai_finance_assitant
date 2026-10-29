"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ai_finance_assistant.api.middleware import RequestCorrelationMiddleware
from ai_finance_assistant.api.routes.health import router as health_router
from ai_finance_assistant.core.config import Settings, get_settings
from ai_finance_assistant.core.logging import configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)

    app = FastAPI(
        title=resolved_settings.app_name,
        version=resolved_settings.app_version,
        description=(
            "M4 foundation with offline knowledge ingestion, deterministic finance modules, "
            "provider adapters, and an internal six-agent LangGraph workflow. Workflow REST, "
            "SSE, and durable application persistence are not implemented until M5."
        ),
    )
    app.state.settings = resolved_settings
    app.add_middleware(RequestCorrelationMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["Content-Type", "X-Request-ID"],
    )
    app.include_router(health_router, prefix="/api")
    return app


app = create_app()
