"""M0 health builders. Qdrant compatibility checks begin in M1."""

from ai_finance_assistant.contracts.health import (
    CheckStatus,
    DependencyCheck,
    HealthStatus,
    HealthSummary,
    Liveness,
    Readiness,
)
from ai_finance_assistant.core.config import Settings


def build_liveness(settings: Settings) -> Liveness:
    return Liveness(
        service=settings.app_name,
        version=settings.app_version,
    )


def build_readiness(settings: Settings) -> Readiness:
    qdrant_status = (
        CheckStatus.NOT_IMPLEMENTED if settings.qdrant_url else CheckStatus.NOT_CONFIGURED
    )
    qdrant_detail = (
        "M1 collection compatibility validation is not implemented."
        if settings.qdrant_url
        else "Qdrant is intentionally unconfigured in the M0 local foundation."
    )
    shared_expected = {
        "payload_schema_version": settings.expected_payload_schema_version,
        "dense_model_id": settings.expected_dense_model_id,
        "sparse_model_id": settings.expected_sparse_model_id,
    }
    checks = (
        DependencyCheck(
            name="qdrant.finance_education",
            status=qdrant_status,
            detail=qdrant_detail,
            expected={
                **shared_expected,
                "active_alias": settings.finance_collection_alias,
            },
        ),
        DependencyCheck(
            name="qdrant.tax_education",
            status=qdrant_status,
            detail=qdrant_detail,
            expected={
                **shared_expected,
                "active_alias": settings.tax_collection_alias,
            },
        ),
    )
    return Readiness(status=HealthStatus.NOT_READY, checks=checks)


def build_health_summary(settings: Settings) -> HealthSummary:
    liveness = build_liveness(settings)
    readiness = build_readiness(settings)
    return HealthSummary(
        status=HealthStatus.DEGRADED,
        mode=settings.mode,
        liveness=liveness,
        readiness=readiness,
    )
