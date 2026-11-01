"""Deterministic M6.1 workflow benchmark for cache paths."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from time import monotonic, sleep
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from ai_finance_assistant.agents.context import InMemoryAgentContextRepository
from ai_finance_assistant.contracts.agents import AgentId
from ai_finance_assistant.core.config import Settings
from ai_finance_assistant.knowledge.models import Evidence, LogicalKnowledgeBase, SparseEmbedding
from ai_finance_assistant.llm.fake import DeterministicModelAdapter
from ai_finance_assistant.llm.models import (
    ModelAdapterResult,
    ModelRequest,
    PublicRagCacheEligibility,
    RoutingModelOutput,
    RoutingModelRequest,
    RoutingReason,
)
from ai_finance_assistant.observability.memory import InMemoryObservability
from ai_finance_assistant.providers.factory import credential_free_bundle
from ai_finance_assistant.response_cache.adapters import (
    DisabledModelResponseCache,
    InMemoryModelResponseCache,
)
from ai_finance_assistant.response_cache.ports import ModelResponseCache
from ai_finance_assistant.response_cache.service import ResponseCacheService, normalize_query
from ai_finance_assistant.workflow.application import WorkflowApplication
from ai_finance_assistant.workflow.events import InMemoryRunEventRepository, RunEventRecorder
from ai_finance_assistant.workflow.models import WorkflowRequest, WorkflowRunResult
from ai_finance_assistant.workflow.retrieval import StaticKnowledgeRetrieval

Scenario = Literal["cache_disabled", "exact_hit", "semantic_hit", "near_miss"]
_CANONICAL = "Compare ETFs and mutual funds."
_PARAPHRASE = "Compare mutual funds and ETFs."
_NEAR_MISS = "What is concentration risk and why does it matter?"
_SCENARIOS: tuple[Scenario, ...] = (
    "cache_disabled",
    "exact_hit",
    "semantic_hit",
    "near_miss",
)


class ScenarioReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    scenario: Scenario
    sample_count: int = Field(gt=0)
    p50_milliseconds: float = Field(ge=0.0)
    p95_milliseconds: float = Field(ge=0.0)
    route_model_calls: int = Field(ge=0)
    generation_model_calls: int = Field(ge=0)
    answer_equivalent: bool
    citations_equivalent: bool


class BenchmarkReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1"
    measured_at: datetime
    workflow_version: str = "1"
    cache_policy_version: str = "public-rag-evidence-bound-v2"
    semantic_similarity: float = 0.92
    synthetic_model_delay_milliseconds: float
    model_usage_method: str = "deterministic_fixture_count_v1"
    monetary_cost: None = None
    scenarios: tuple[ScenarioReport, ...]


class BenchmarkEncoder:
    dense_model_id = "benchmark-mapping-v1"
    sparse_model_id = "unused"
    dense_model_revision = "benchmark-revision-v1"
    dense_artifact_sha256 = "a" * 64
    sparse_model_revision = "unused"
    sparse_artifact_sha256 = "b" * 64
    dense_dimensions = 2

    def embed_dense(self, texts: Sequence[str]) -> list[list[float]]:
        return [
            [0.0, 1.0] if normalize_query(text) == normalize_query(_NEAR_MISS) else [1.0, 0.0]
            for text in texts
        ]

    def embed_sparse(self, texts: Sequence[str]) -> list[SparseEmbedding]:
        return [SparseEmbedding(indices=(1,), values=(1.0,)) for _ in texts]


class DelayedCountingModel(DeterministicModelAdapter):
    def __init__(self, *, delay_seconds: float) -> None:
        route = RoutingModelOutput(
            selected_agent_ids=(AgentId.FINANCE_QA,),
            reason_category=RoutingReason.SINGLE_DOMAIN,
            cache_eligibility=PublicRagCacheEligibility.PUBLIC_RAG,
        )
        super().__init__(
            routing_responses={
                _CANONICAL: route,
                _PARAPHRASE: route,
                _NEAR_MISS: route,
            }
        )
        self.delay_seconds = delay_seconds
        self.route_calls = 0
        self.generate_calls = 0

    def route(self, request: RoutingModelRequest) -> ModelAdapterResult:
        self.route_calls += 1
        sleep(self.delay_seconds)
        return super().route(request)

    def generate(self, request: ModelRequest) -> ModelAdapterResult:
        self.generate_calls += 1
        sleep(self.delay_seconds)
        return super().generate(request)


def benchmark(*, sample_count: int, model_delay_milliseconds: float) -> BenchmarkReport:
    if sample_count < 1:
        raise ValueError("sample_count must be positive")
    if model_delay_milliseconds < 0:
        raise ValueError("model_delay_milliseconds cannot be negative")
    delay_seconds = model_delay_milliseconds / 1_000
    baseline = _run_sample(scenario="cache_disabled", delay_seconds=delay_seconds)[1]
    reports = tuple(
        _benchmark_scenario(
            scenario=scenario,
            sample_count=sample_count,
            delay_seconds=delay_seconds,
            baseline=baseline,
        )
        for scenario in _SCENARIOS
    )
    return BenchmarkReport(
        measured_at=datetime.now(UTC),
        synthetic_model_delay_milliseconds=model_delay_milliseconds,
        scenarios=reports,
    )


def _benchmark_scenario(
    *,
    scenario: Scenario,
    sample_count: int,
    delay_seconds: float,
    baseline: WorkflowRunResult,
) -> ScenarioReport:
    durations: list[float] = []
    route_calls = 0
    generation_calls = 0
    results: list[WorkflowRunResult] = []
    for _ in range(sample_count):
        elapsed, result, measured_route_calls, measured_generation_calls = _run_sample(
            scenario=scenario,
            delay_seconds=delay_seconds,
        )
        durations.append(elapsed)
        results.append(result)
        route_calls += measured_route_calls
        generation_calls += measured_generation_calls
    baseline_summary = baseline.agent_results[0].summary
    baseline_evidence = baseline.agent_results[0].evidence
    return ScenarioReport(
        scenario=scenario,
        sample_count=sample_count,
        p50_milliseconds=_percentile(durations, 0.50),
        p95_milliseconds=_percentile(durations, 0.95),
        route_model_calls=route_calls,
        generation_model_calls=generation_calls,
        answer_equivalent=all(
            result.agent_results[0].summary == baseline_summary for result in results
        ),
        citations_equivalent=all(
            result.agent_results[0].evidence == baseline_evidence for result in results
        ),
    )


def _run_sample(
    *,
    scenario: Scenario,
    delay_seconds: float,
) -> tuple[float, WorkflowRunResult, int, int]:
    model = DelayedCountingModel(delay_seconds=delay_seconds)
    adapter: ModelResponseCache = (
        DisabledModelResponseCache()
        if scenario == "cache_disabled"
        else InMemoryModelResponseCache()
    )
    app = _application(model=model, adapter=adapter)
    if scenario != "cache_disabled":
        app.run(_request(_CANONICAL))
    before_route = model.route_calls
    before_generation = model.generate_calls
    message = {
        "cache_disabled": _CANONICAL,
        "exact_hit": _CANONICAL,
        "semantic_hit": _PARAPHRASE,
        "near_miss": _NEAR_MISS,
    }[scenario]
    started = monotonic()
    result = app.run(_request(message))
    elapsed = (monotonic() - started) * 1_000
    return (
        elapsed,
        result,
        model.route_calls - before_route,
        model.generate_calls - before_generation,
    )


def _application(
    *,
    model: DelayedCountingModel,
    adapter: ModelResponseCache,
) -> WorkflowApplication:
    telemetry = InMemoryObservability()
    return WorkflowApplication(
        settings=Settings(
            mode="test",
            provider_mode="credential_free",
            model_mode="credential_free",
            langsmith_tracing_enabled=False,
        ),
        retrieval=StaticKnowledgeRetrieval({LogicalKnowledgeBase.FINANCE: (_evidence(),)}),
        contexts=InMemoryAgentContextRepository(),
        model_adapter_builder=lambda _: model,
        event_recorder=RunEventRecorder(
            repository=InMemoryRunEventRepository(),
            observability=telemetry,
        ),
        observability=telemetry,
        provider_bundle_builder=lambda _: credential_free_bundle(),
        response_cache=ResponseCacheService(
            adapter=adapter,
            encoder=BenchmarkEncoder(),
            policy_version="public-rag-evidence-bound-v2",
            schema_version="1",
            ttl_seconds=300,
            minimum_semantic_similarity=0.92,
            semantic_mode="serving",
        ),
    )


def _request(message: str) -> WorkflowRequest:
    return WorkflowRequest(
        execution_id=f"benchmark-{uuid4().hex}",
        session_id="benchmark-session",
        workflow_id="finance-assistant",
        workflow_version="1",
        message=message,
        deadline_at=datetime.now(UTC) + timedelta(minutes=1),
    )


def _evidence() -> Evidence:
    return Evidence(
        chunk_id="finance-benchmark-chunk",
        document_id="finance-benchmark-document",
        title="Public education benchmark evidence",
        publisher="Deterministic Fixture",
        canonical_url="https://example.invalid/benchmark",
        section_path="Overview",
        text="Grounded public Finance education fixture.",
        score=0.99,
        rank=1,
        collection_name="finance_education_v1",
        collection_version="v1",
        document_version="document-v1",
        content_hash="c" * 64,
        fetched_at=datetime(2026, 10, 31, 12, 0, tzinfo=UTC),
        jurisdiction="US-Federal",
    )


def _percentile(values: Sequence[float], percentile: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int((len(ordered) - 1) * percentile + 0.5)))
    return ordered[index]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the deterministic M6.1 workflow benchmark")
    parser.add_argument("--samples", type=int, default=20)
    parser.add_argument("--model-delay-ms", type=float, default=10.0)
    args = parser.parse_args()
    report = benchmark(
        sample_count=args.samples,
        model_delay_milliseconds=args.model_delay_ms,
    )
    print(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
