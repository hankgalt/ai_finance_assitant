"""Health builders with read-only M1 Qdrant compatibility checks."""

from ai_finance_assistant.contracts.health import (
    CheckStatus,
    DependencyCheck,
    HealthStatus,
    HealthSummary,
    Liveness,
    Readiness,
)
from ai_finance_assistant.core.config import Settings
from ai_finance_assistant.knowledge.models import CollectionCompatibility, LogicalKnowledgeBase
from ai_finance_assistant.knowledge.qdrant_store import QdrantKnowledgeStore


def build_liveness(settings: Settings) -> Liveness:
    return Liveness(
        service=settings.app_name,
        version=settings.app_version,
    )


def build_readiness(settings: Settings) -> Readiness:
    shared_expected = {
        "payload_schema_version": settings.expected_payload_schema_version,
        "dense_model_id": settings.expected_dense_model_id,
        "dense_model_revision": settings.expected_dense_model_revision,
        "dense_artifact_sha256": settings.expected_dense_artifact_sha256,
        "dense_dimensions": settings.expected_dense_dimensions,
        "sparse_model_id": settings.expected_sparse_model_id,
        "sparse_model_revision": settings.expected_sparse_model_revision,
        "sparse_artifact_sha256": settings.expected_sparse_artifact_sha256,
        "chunking_policy_version": settings.expected_chunking_policy_version,
    }
    targets = (
        (
            "qdrant.finance_education",
            settings.finance_collection_alias,
            LogicalKnowledgeBase.FINANCE,
        ),
        (
            "qdrant.tax_education",
            settings.tax_collection_alias,
            LogicalKnowledgeBase.TAX,
        ),
    )
    if settings.qdrant_url is None:
        checks = tuple(
            DependencyCheck(
                name=name,
                status=CheckStatus.NOT_CONFIGURED,
                detail="Qdrant URL is not configured.",
                expected={**shared_expected, "active_alias": alias},
            )
            for name, alias, _ in targets
        )
        return Readiness(status=HealthStatus.NOT_READY, checks=checks)

    try:
        store = QdrantKnowledgeStore(settings.qdrant_url)
        checks_list: list[DependencyCheck] = []
        for name, alias, logical_kb in targets:
            compatible, detail = store.validate_active(
                alias,
                CollectionCompatibility(
                    schema_version=settings.expected_payload_schema_version,
                    logical_kb=logical_kb,
                    dense_model_id=settings.expected_dense_model_id,
                    dense_model_revision=settings.expected_dense_model_revision,
                    dense_artifact_sha256=settings.expected_dense_artifact_sha256,
                    dense_dimensions=settings.expected_dense_dimensions,
                    sparse_model_id=settings.expected_sparse_model_id,
                    sparse_model_revision=settings.expected_sparse_model_revision,
                    sparse_artifact_sha256=settings.expected_sparse_artifact_sha256,
                    chunking_policy_version=settings.expected_chunking_policy_version,
                ),
            )
            checks_list.append(
                DependencyCheck(
                    name=name,
                    status=CheckStatus.READY if compatible else CheckStatus.FAILED,
                    detail=detail,
                    expected={**shared_expected, "active_alias": alias},
                )
            )
        checks = tuple(checks_list)
    except Exception:  # Qdrant client exceptions vary by transport and failure phase.
        checks = tuple(
            DependencyCheck(
                name=name,
                status=CheckStatus.FAILED,
                detail="Qdrant is unavailable or its response could not be validated.",
                expected={**shared_expected, "active_alias": alias},
            )
            for name, alias, _ in targets
        )
    status = (
        HealthStatus.OK
        if all(check.status == CheckStatus.READY for check in checks)
        else HealthStatus.NOT_READY
    )
    return Readiness(status=status, checks=checks)


def build_health_summary(settings: Settings) -> HealthSummary:
    liveness = build_liveness(settings)
    readiness = build_readiness(settings)
    return HealthSummary(
        status=HealthStatus.OK if readiness.status == HealthStatus.OK else HealthStatus.DEGRADED,
        mode=settings.mode,
        liveness=liveness,
        readiness=readiness,
    )
