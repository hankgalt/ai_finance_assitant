"""Health builders with read-only storage, provider, and Qdrant readiness checks."""

import sqlite3

from pydantic import JsonValue

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
    shared_expected: dict[str, JsonValue] = {
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
        qdrant_checks = tuple(
            DependencyCheck(
                name=name,
                status=CheckStatus.NOT_CONFIGURED,
                detail="Qdrant URL is not configured.",
                expected={**shared_expected, "active_alias": alias},
            )
            for name, alias, _ in targets
        )
        checks = (*_local_checks(settings), *qdrant_checks)
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
        qdrant_checks = tuple(checks_list)
    except Exception:  # Qdrant client exceptions vary by transport and failure phase.
        qdrant_checks = tuple(
            DependencyCheck(
                name=name,
                status=CheckStatus.FAILED,
                detail="Qdrant is unavailable or its response could not be validated.",
                expected={**shared_expected, "active_alias": alias},
            )
            for name, alias, _ in targets
        )
    checks = (*_local_checks(settings), *qdrant_checks)
    status = (
        HealthStatus.OK
        if all(check.status == CheckStatus.READY for check in checks)
        else HealthStatus.NOT_READY
    )
    return Readiness(status=status, checks=checks)


def _local_checks(settings: Settings) -> tuple[DependencyCheck, ...]:
    return (
        _storage_check(settings),
        _bind_check(settings),
        _market_provider_check(settings),
        _news_provider_check(settings),
        _provider_cache_rights_check(settings),
    )


def _storage_check(settings: Settings) -> DependencyCheck:
    expected = {"schema_version": settings.storage_expected_schema_version}
    if not settings.storage_path.exists():
        return DependencyCheck(
            name="storage.sqlite",
            status=CheckStatus.NOT_CONFIGURED,
            detail="The local SQLite database has not been initialized.",
            expected=expected,
        )
    try:
        connection = sqlite3.connect(f"file:{settings.storage_path}?mode=ro", uri=True)
        try:
            row = connection.execute(
                "SELECT COALESCE(MAX(version), 0) FROM schema_migrations"
            ).fetchone()
        finally:
            connection.close()
        version = int(row[0]) if row is not None else 0
    except sqlite3.Error:
        return DependencyCheck(
            name="storage.sqlite",
            status=CheckStatus.FAILED,
            detail="The local SQLite schema could not be read safely.",
            expected=expected,
        )
    compatible = version == settings.storage_expected_schema_version
    return DependencyCheck(
        name="storage.sqlite",
        status=CheckStatus.READY if compatible else CheckStatus.FAILED,
        detail=(
            "The local SQLite schema is compatible."
            if compatible
            else "The local SQLite schema version is incompatible."
        ),
        expected=expected,
    )


def _bind_check(settings: Settings) -> DependencyCheck:
    local = settings.host in {"127.0.0.1", "::1", "localhost"}
    return DependencyCheck(
        name="security.local_bind",
        status=CheckStatus.READY if local else CheckStatus.FAILED,
        detail=(
            "The unauthenticated private demo is bound to a loopback interface."
            if local
            else "Non-loopback operation is blocked until strong authentication is approved."
        ),
        expected={"audience": settings.local_deployment_audience},
    )


def _market_provider_check(settings: Settings) -> DependencyCheck:
    if settings.provider_mode == "credential_free":
        ready = True
        detail = "The labeled synthetic market provider is ready."
        provider = "fake_market_data_v1"
    elif settings.market_data_provider == "massive":
        provider = "massive"
        ready = (
            settings.massive_api_key is not None
            and settings.massive_terms_approved
            and settings.market_provider_request_budget > 0
        )
        detail = (
            "The selected live market provider is configured."
            if ready
            else "The selected live market provider lacks credentials, approval, or budget."
        )
    else:
        provider = "alpha_vantage"
        ready = (
            settings.alpha_vantage_api_key is not None
            and settings.alpha_vantage_terms_approved
            and settings.market_provider_request_budget > 0
        )
        detail = (
            "The selected live market provider is configured."
            if ready
            else "The selected live market provider lacks credentials, approval, or budget."
        )
    return DependencyCheck(
        name="provider.market",
        status=CheckStatus.READY if ready else CheckStatus.FAILED,
        detail=detail,
        expected={"provider": provider, "mode": settings.provider_mode},
    )


def _news_provider_check(settings: Settings) -> DependencyCheck:
    ready = settings.provider_mode == "credential_free" or (
        settings.tavily_api_key is not None
        and settings.tavily_terms_approved
        and settings.news_provider_request_budget > 0
    )
    return DependencyCheck(
        name="provider.news",
        status=CheckStatus.READY if ready else CheckStatus.FAILED,
        detail=(
            "The selected news provider is configured."
            if ready
            else "The selected news provider lacks credentials, approval, or budget."
        ),
        expected={
            "provider": "fake_news_v1" if settings.provider_mode == "credential_free" else "tavily",
            "mode": settings.provider_mode,
        },
    )


def _provider_cache_rights_check(settings: Settings) -> DependencyCheck:
    if not settings.provider_cache_enabled:
        ready = True
        detail = "The durable historical provider cache is disabled."
    elif settings.provider_mode == "credential_free":
        ready = True
        detail = "Only labeled synthetic history is eligible for durable caching."
    elif settings.provider_cache_retention_permission == "verified":
        ready = True
        detail = "Provider retention permission is recorded as verified."
    else:
        ready = (
            settings.local_deployment_audience == "owner_only"
            and settings.provider_cache_owner_risk_accepted
        )
        detail = (
            "Owner-only unverified-rights retention risk is explicitly accepted."
            if ready
            else "Unverified retention rights block this deployment audience."
        )
    return DependencyCheck(
        name="provider_cache.rights",
        status=CheckStatus.READY if ready else CheckStatus.FAILED,
        detail=detail,
        expected={
            "audience": settings.local_deployment_audience,
            "retention_permission": settings.provider_cache_retention_permission,
        },
    )


def build_health_summary(settings: Settings) -> HealthSummary:
    liveness = build_liveness(settings)
    readiness = build_readiness(settings)
    return HealthSummary(
        status=HealthStatus.OK if readiness.status == HealthStatus.OK else HealthStatus.DEGRADED,
        mode=settings.mode,
        liveness=liveness,
        readiness=readiness,
    )
