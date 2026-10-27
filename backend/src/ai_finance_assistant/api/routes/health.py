"""Liveness and honest M0 readiness endpoints."""

from fastapi import APIRouter, Request, Response, status

from ai_finance_assistant.contracts.health import HealthStatus, HealthSummary, Liveness, Readiness
from ai_finance_assistant.core.config import Settings
from ai_finance_assistant.core.health import build_health_summary, build_liveness, build_readiness

router = APIRouter(tags=["health"])


def _settings(request: Request) -> Settings:
    return request.app.state.settings  # type: ignore[no-any-return]


@router.get("/health", response_model=HealthSummary)
def health(request: Request) -> HealthSummary:
    return build_health_summary(_settings(request))


@router.get("/health/live", response_model=Liveness)
def live(request: Request) -> Liveness:
    return build_liveness(_settings(request))


@router.get(
    "/health/ready",
    response_model=Readiness,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": Readiness}},
)
def ready(request: Request, response: Response) -> Readiness:
    readiness = build_readiness(_settings(request))
    if readiness.status != HealthStatus.OK:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return readiness
