"""M5 application composition and durable local lifecycle."""

from __future__ import annotations

from datetime import UTC, datetime

from ai_finance_assistant.core.config import Settings
from ai_finance_assistant.finance.goal_projection import GoalProjection
from ai_finance_assistant.finance.portfolio_analysis import PortfolioAnalysis
from ai_finance_assistant.finance.portfolio_import import PortfolioImport
from ai_finance_assistant.knowledge.models import LogicalKnowledgeBase
from ai_finance_assistant.knowledge.qdrant_store import QdrantKnowledgeStore
from ai_finance_assistant.knowledge.representations import FastEmbedEncoder
from ai_finance_assistant.knowledge.retrieval import KnowledgeRetriever
from ai_finance_assistant.observability.factory import (
    TelemetryRuntime,
    telemetry_runtime_from_settings,
)
from ai_finance_assistant.persistence.checkpoints import create_sqlite_checkpointer
from ai_finance_assistant.persistence.database import SQLiteDatabase
from ai_finance_assistant.persistence.repositories import (
    SQLiteAgentContextRepository,
    SQLiteApplicationRepository,
    SQLiteRunEventRepository,
)
from ai_finance_assistant.providers.durable_cache import (
    DurableCachingMarketDataProvider,
    HistoricalCachePolicy,
    HistoricalMemoryCache,
    SQLiteHistoricalCacheRepository,
)
from ai_finance_assistant.providers.factory import provider_bundle_from_settings
from ai_finance_assistant.providers.ports import ProviderBundle
from ai_finance_assistant.workflow.application import WorkflowApplication
from ai_finance_assistant.workflow.events import RunEventRecorder
from ai_finance_assistant.workflow.retrieval import (
    ActiveKnowledgeRetrieval,
    KnowledgeRetrieval,
    StaticKnowledgeRetrieval,
)


class ApplicationServices:
    def __init__(
        self,
        settings: Settings,
        *,
        telemetry: TelemetryRuntime | None = None,
    ) -> None:
        self.settings = settings
        self.telemetry = telemetry or telemetry_runtime_from_settings(settings)
        self.observability = self.telemetry.observability
        self.database = SQLiteDatabase(
            settings.storage_path,
            expected_version=settings.storage_expected_schema_version,
            observability=self.observability,
        )
        self.database.migrate()
        self.checkpointer, self._checkpoint_connection = create_sqlite_checkpointer(self.database)
        self.application_repository = SQLiteApplicationRepository(
            self.database,
            session_retention_days=settings.session_retention_days,
            portfolio_retention_days=settings.portfolio_retention_days,
            run_event_retention_days=settings.run_event_retention_days,
        )
        for expired_session_id in self.application_repository.purge_expired():
            self.checkpointer.delete_thread(f"{expired_session_id}:finance-assistant")
        self.event_repository = SQLiteRunEventRepository(self.database)
        self.context_repository = SQLiteAgentContextRepository(self.database)
        self.provider_cache_repository = SQLiteHistoricalCacheRepository(self.database)
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
        self.market = self._market_bundle.market
        self.news = self._market_bundle.news
        self.workflow = WorkflowApplication(
            settings=settings,
            retrieval=self._knowledge_retrieval(),
            contexts=self.context_repository,
            event_recorder=self.event_recorder,
            observability=self.observability,
            provider_bundle_builder=lambda _: self._provider_bundle(),
            checkpointer=self.checkpointer,
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
                store=QdrantKnowledgeStore(self.settings.qdrant_url),
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

    def delete_session(self, session_id: str) -> bool:
        deleted = self.application_repository.delete_archived_session(session_id)
        if deleted:
            self.checkpointer.delete_thread(f"{session_id}:finance-assistant")
        return deleted

    def purge_provider_cache(self, *, provider: str | None = None) -> int:
        count = self.provider_cache_repository.purge(provider=provider)
        self._memory_cache.clear()
        return count

    def close(self) -> None:
        self.telemetry.shutdown()
        self._checkpoint_connection.close()
        self.database.close()
