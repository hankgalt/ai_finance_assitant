"""Application composition and durable lifecycle."""

from __future__ import annotations

from datetime import UTC, datetime

from langgraph.checkpoint.base import BaseCheckpointSaver

from ai_finance_assistant.core.config import Settings
from ai_finance_assistant.finance.goal_projection import GoalProjection
from ai_finance_assistant.finance.portfolio_analysis import PortfolioAnalysis
from ai_finance_assistant.finance.portfolio_import import PortfolioImport
from ai_finance_assistant.identity.access import IdentityAccess
from ai_finance_assistant.identity.repositories import PrincipalRepository
from ai_finance_assistant.identity.verification import IAPAssertionVerifier
from ai_finance_assistant.knowledge.models import LogicalKnowledgeBase
from ai_finance_assistant.knowledge.qdrant_store import QdrantKnowledgeStore
from ai_finance_assistant.knowledge.representations import FastEmbedEncoder
from ai_finance_assistant.knowledge.retrieval import KnowledgeRetriever
from ai_finance_assistant.observability.factory import (
    TelemetryRuntime,
    telemetry_runtime_from_settings,
)
from ai_finance_assistant.persistence.checkpoints import (
    Closeable,
    create_postgres_checkpointer,
    create_sqlite_checkpointer,
    scope_legacy_checkpoint_threads,
    verify_postgres_checkpoint_schema,
)
from ai_finance_assistant.persistence.database import MigrationError, SQLiteDatabase
from ai_finance_assistant.persistence.models import SessionRecord
from ai_finance_assistant.persistence.ports import ApplicationDatabase
from ai_finance_assistant.persistence.postgres import PostgresDatabase
from ai_finance_assistant.persistence.repositories import (
    AgentContextRepository,
    ApplicationRepository,
    RunEventRepository,
)
from ai_finance_assistant.providers.durable_cache import (
    DurableCachingMarketDataProvider,
    HistoricalCachePolicy,
    HistoricalCacheRepository,
    HistoricalMemoryCache,
)
from ai_finance_assistant.providers.factory import provider_bundle_from_settings
from ai_finance_assistant.providers.models import (
    HistoricalRequest,
    HistoricalResult,
    InstrumentSearchRequest,
    InstrumentSearchResult,
    ProviderMode,
    ProviderReadiness,
    QuoteRequest,
    QuoteResult,
)
from ai_finance_assistant.providers.ports import MarketDataProvider, ProviderBundle
from ai_finance_assistant.providers.runtime import request_budget_scope
from ai_finance_assistant.response_cache.factory import response_cache_service_from_settings
from ai_finance_assistant.workflow.application import WorkflowApplication
from ai_finance_assistant.workflow.events import RunEventRecorder
from ai_finance_assistant.workflow.retrieval import (
    ActiveKnowledgeRetrieval,
    KnowledgeRetrieval,
    StaticKnowledgeRetrieval,
)


class BudgetScopedMarketDataProvider:
    """Give each Market page or MCP call its own provider request budget.

    Chat Runs build a provider bundle per Run. The Market page and MCP reuse one long-lived
    provider, which previously meant one budget for the whole process. Each call now gets a
    fresh budget while the provider's quote cache, rate window, and circuit stay shared.
    """

    def __init__(self, provider: MarketDataProvider) -> None:
        self._provider = provider

    @property
    def mode(self) -> ProviderMode:
        return self._provider.mode

    def readiness(self, required_requests: int = 1) -> ProviderReadiness:
        with request_budget_scope():
            return self._provider.readiness(required_requests)

    def search_instruments(self, request: InstrumentSearchRequest) -> InstrumentSearchResult:
        with request_budget_scope():
            return self._provider.search_instruments(request)

    def get_quote(self, request: QuoteRequest) -> QuoteResult:
        with request_budget_scope():
            return self._provider.get_quote(request)

    def get_history(self, request: HistoricalRequest) -> HistoricalResult:
        with request_budget_scope():
            return self._provider.get_history(request)


class ApplicationServices:
    def __init__(
        self,
        settings: Settings,
        *,
        telemetry: TelemetryRuntime | None = None,
        iap_assertion_verifier: IAPAssertionVerifier | None = None,
    ) -> None:
        self.settings = settings
        self.telemetry = telemetry or telemetry_runtime_from_settings(settings)
        self.observability = self.telemetry.observability
        self.response_cache = response_cache_service_from_settings(settings)
        self.database, self.checkpointer, self._checkpoint_resource = self._persistence()
        self.principal_repository = PrincipalRepository(self.database)
        self.identity_access = IdentityAccess(
            settings,
            self.principal_repository,
            iap_assertion_verifier=iap_assertion_verifier,
        )
        self.application_repository = ApplicationRepository(
            self.database,
            session_retention_days=settings.session_retention_days,
            portfolio_retention_days=settings.portfolio_retention_days,
            run_event_retention_days=settings.run_event_retention_days,
        )
        if settings.retention_execution_mode == "startup":
            self.run_retention()
        self.event_repository = RunEventRepository(self.database)
        self.context_repository = AgentContextRepository(self.database)
        self.provider_cache_repository = HistoricalCacheRepository(self.database)
        if settings.retention_execution_mode == "startup":
            self.provider_cache_repository.purge_expired(now=datetime.now(UTC))
        self.event_recorder = RunEventRecorder(
            repository=self.event_repository,
            observability=self.observability,
        )
        self.portfolio_import = PortfolioImport()
        self.portfolio_analysis = PortfolioAnalysis()
        self.goal_projection = GoalProjection()
        self._cache_policy = HistoricalCachePolicy(
            enabled=settings.provider_cache_enabled,
            deployment_audience=settings.local_deployment_audience,
            retention_permission=settings.provider_cache_retention_permission,
            owner_risk_accepted=settings.provider_cache_owner_risk_accepted,
            retention_days=settings.provider_cache_retention_days,
            recent_tail_days=settings.provider_cache_recent_tail_days,
            tail_refresh_seconds=settings.provider_cache_tail_refresh_seconds,
            memory_ttl_seconds=settings.provider_cache_memory_ttl_seconds,
            memory_max_entries=settings.provider_cache_memory_max_entries,
            schema_version=settings.provider_cache_schema_version,
            policy_version=settings.provider_cache_policy_version,
        )
        self._memory_cache = HistoricalMemoryCache(
            ttl_seconds=settings.provider_cache_memory_ttl_seconds,
            max_entries=settings.provider_cache_memory_max_entries,
        )
        self._market_bundle = self._provider_bundle()
        self.market: MarketDataProvider = BudgetScopedMarketDataProvider(self._market_bundle.market)
        self.news = self._market_bundle.news
        self.knowledge = self._knowledge_retrieval()
        self.workflow = WorkflowApplication(
            settings=settings,
            retrieval=self.knowledge,
            contexts=self.context_repository,
            event_recorder=self.event_recorder,
            observability=self.observability,
            # One shared bundle per process: every chat Run counts against the same provider
            # rate window and cache; WorkflowApplication.run scopes the request budget per Run.
            provider_bundle_builder=lambda _: self._market_bundle,
            checkpointer=self.checkpointer,
            response_cache=self.response_cache,
        )

    def _knowledge_retrieval(self) -> KnowledgeRetrieval:
        if self.settings.qdrant_url is None:
            return StaticKnowledgeRetrieval(
                {
                    LogicalKnowledgeBase.FINANCE: (),
                    LogicalKnowledgeBase.TAX: (),
                }
            )
        return ActiveKnowledgeRetrieval(
            retriever=KnowledgeRetriever(
                store=QdrantKnowledgeStore(
                    self.settings.qdrant_url,
                    api_key=(
                        None
                        if self.settings.qdrant_api_key is None
                        else self.settings.qdrant_api_key.get_secret_value()
                    ),
                ),
                encoder=FastEmbedEncoder(),
            ),
            aliases={
                LogicalKnowledgeBase.FINANCE: self.settings.finance_collection_alias,
                LogicalKnowledgeBase.TAX: self.settings.tax_collection_alias,
            },
        )

    def _provider_bundle(self) -> ProviderBundle:
        selected = provider_bundle_from_settings(self.settings)
        return ProviderBundle(
            market=DurableCachingMarketDataProvider(
                selected.market,
                repository=self.provider_cache_repository,
                policy=self._cache_policy,
                observability=self.observability,
                memory_cache=self._memory_cache,
            ),
            news=selected.news,
        )

    def archive_session(self, principal_id: str, session_id: str) -> SessionRecord | None:
        archived = self.application_repository.archive_session(principal_id, session_id)
        if archived is not None:
            self.response_cache.purge_session(session_id, principal_id=principal_id)
            self.response_cache.purge_session(session_id)
        return archived

    def delete_session(self, principal_id: str, session_id: str) -> bool:
        deleted = self.application_repository.delete_archived_session(principal_id, session_id)
        if deleted:
            self.checkpointer.delete_thread(
                f"{principal_id}:{session_id}:{self.settings.workflow_id}"
            )
            self.response_cache.purge_session(session_id, principal_id=principal_id)
            self.response_cache.purge_session(session_id)
        return deleted

    def purge_provider_cache(self, *, provider: str | None = None) -> int:
        count = self.provider_cache_repository.purge(provider=provider)
        self._memory_cache.clear()
        return count

    def purge_response_cache(self) -> int:
        return self.response_cache.purge_all()

    def run_retention(self) -> tuple[tuple[str, str], ...]:
        expired = self.application_repository.purge_expired()
        for principal_id, expired_session_id in expired:
            self.checkpointer.delete_thread(
                f"{principal_id}:{expired_session_id}:{self.settings.workflow_id}"
            )
            self.response_cache.purge_session(
                expired_session_id,
                principal_id=principal_id,
            )
            self.response_cache.purge_session(expired_session_id)
        return expired

    def _persistence(
        self,
    ) -> tuple[ApplicationDatabase, BaseCheckpointSaver[str], Closeable]:
        if self.settings.storage_backend == "sqlite":
            database = SQLiteDatabase(
                self.settings.storage_path,
                expected_version=self.settings.storage_expected_schema_version,
                observability=self.observability,
            )
            if self.settings.storage_migration_mode == "auto":
                database.migrate()
            elif database.schema_version() != database.expected_version:
                database.close()
                raise MigrationError("SQLite storage schema is not ready.")
            checkpointer, resource = create_sqlite_checkpointer(database)
            scope_legacy_checkpoint_threads(database, resource)
            return database, checkpointer, resource

        assert self.settings.postgres_dsn is not None
        managed_database = PostgresDatabase(
            self.settings.postgres_dsn.get_secret_value(),
            expected_version=self.settings.storage_expected_schema_version,
            pool_min_size=self.settings.postgres_pool_min_size,
            pool_max_size=self.settings.postgres_pool_max_size,
            timeout_seconds=self.settings.postgres_connect_timeout_seconds,
            observability=self.observability,
        )
        managed_resource: Closeable | None = None
        try:
            apply_migrations = self.settings.storage_migration_mode == "auto"
            if apply_migrations:
                managed_database.migrate()
            elif managed_database.schema_version() != managed_database.expected_version:
                raise MigrationError("PostgreSQL storage schema is not ready.")
            managed_checkpointer, managed_resource = create_postgres_checkpointer(
                self.settings.postgres_dsn.get_secret_value(),
                pool_min_size=self.settings.postgres_pool_min_size,
                pool_max_size=self.settings.postgres_pool_max_size,
                timeout_seconds=self.settings.postgres_connect_timeout_seconds,
                setup=apply_migrations,
            )
            if not apply_migrations:
                verify_postgres_checkpoint_schema(managed_database)
        except BaseException:
            if managed_resource is not None:
                managed_resource.close()
            managed_database.close()
            raise
        assert managed_resource is not None
        return managed_database, managed_checkpointer, managed_resource

    def close(self) -> None:
        self.response_cache.close()
        self.telemetry.shutdown()
        self._checkpoint_resource.close()
        self.database.close()
