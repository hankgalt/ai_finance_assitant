"""Truthful, privacy-filtered cache RunEvents and operational measurements."""

from __future__ import annotations

from collections.abc import Callable
from time import monotonic
from typing import TYPE_CHECKING
from uuid import uuid4

from pydantic import JsonValue

from ai_finance_assistant.contracts.agents import AgentId
from ai_finance_assistant.contracts.events import (
    EventStatus,
    EventType,
    ToolResultMetadata,
)
from ai_finance_assistant.observability.ports import Observability
from ai_finance_assistant.response_cache.models import (
    CacheLookupOutcome,
    CacheOperationResult,
    CacheWriteResult,
)
from ai_finance_assistant.response_cache.service import ResponseCacheService

if TYPE_CHECKING:
    from ai_finance_assistant.workflow.events import EventIdentity, RunEventRecorder

_TOOL_NAME = "model_response_cache"


def observe_cache_lookup(
    *,
    events: RunEventRecorder,
    observability: Observability,
    cache: ResponseCacheService,
    identity: EventIdentity,
    node_id: str,
    agent_id: AgentId | None,
    operation: str,
    invoke: Callable[[], CacheOperationResult],
) -> CacheOperationResult:
    started_monotonic = monotonic()
    tool_call_id = f"tool:response-cache:{uuid4().hex[:12]}"
    started = events.record(
        identity,
        event_type=EventType.TOOL_STARTED,
        status=EventStatus.RUNNING,
        node_id=node_id,
        agent_id=agent_id,
        tool_call_id=tool_call_id,
        tool_name=_TOOL_NAME,
        summary="Model response-cache lookup started.",
        safe_metadata={"operation": operation, "policy_version": cache.policy_version},
    )
    with observability.span(
        "model_response_cache.lookup",
        {"operation": operation, "policy_version": cache.policy_version},
    ):
        result = invoke()
    attributes = {
        "operation": operation,
        "outcome": result.outcome.value,
        "match_kind": result.match_kind.value if result.match_kind is not None else "none",
        "policy_version": cache.policy_version,
    }
    observability.count("model_response_cache.lookups", 1, attributes)
    observability.observe(
        "model_response_cache.lookup_duration_ms",
        (monotonic() - started_monotonic) * 1_000,
        attributes,
    )
    events.record(
        identity,
        event_type=EventType.TOOL_COMPLETED,
        status=EventStatus.COMPLETED,
        node_id=node_id,
        agent_id=agent_id,
        tool_call_id=tool_call_id,
        tool_name=_TOOL_NAME,
        summary=f"Model response-cache lookup finished with {result.outcome.value} status.",
        tool_result=ToolResultMetadata(
            result_status=EventStatus.COMPLETED,
            provider=cache.adapter_name,
            cache_status=result.outcome.value,
        ),
        safe_metadata=_lookup_metadata(cache, operation, result),
        started_at=started.started_at,
        completed=True,
        parent_event_id=started.event_id,
    )
    return result


def observe_cache_store(
    *,
    events: RunEventRecorder,
    observability: Observability,
    cache: ResponseCacheService,
    identity: EventIdentity,
    node_id: str,
    agent_id: AgentId | None,
    operation: str,
    invoke: Callable[[], CacheWriteResult],
) -> CacheWriteResult:
    started_monotonic = monotonic()
    tool_call_id = f"tool:response-cache:{uuid4().hex[:12]}"
    started = events.record(
        identity,
        event_type=EventType.TOOL_STARTED,
        status=EventStatus.RUNNING,
        node_id=node_id,
        agent_id=agent_id,
        tool_call_id=tool_call_id,
        tool_name=_TOOL_NAME,
        summary="Model response-cache store started.",
        safe_metadata={"operation": operation, "policy_version": cache.policy_version},
    )
    with observability.span(
        "model_response_cache.store",
        {"operation": operation, "policy_version": cache.policy_version},
    ):
        result = invoke()
    attributes = {
        "operation": operation,
        "outcome": result.outcome.value,
        "policy_version": cache.policy_version,
    }
    observability.count("model_response_cache.stores", 1, attributes)
    observability.observe(
        "model_response_cache.store_duration_ms",
        (monotonic() - started_monotonic) * 1_000,
        attributes,
    )
    safe_metadata: dict[str, JsonValue] = {
        "operation": operation,
        "outcome": result.outcome.value,
        "policy_version": cache.policy_version,
    }
    if result.reason is not None:
        safe_metadata["reason"] = result.reason
    events.record(
        identity,
        event_type=EventType.TOOL_COMPLETED,
        status=EventStatus.COMPLETED,
        node_id=node_id,
        agent_id=agent_id,
        tool_call_id=tool_call_id,
        tool_name=_TOOL_NAME,
        summary=f"Model response-cache store finished with {result.outcome.value} status.",
        tool_result=ToolResultMetadata(
            result_status=EventStatus.COMPLETED,
            provider=cache.adapter_name,
            cache_status=result.outcome.value,
        ),
        safe_metadata=safe_metadata,
        started_at=started.started_at,
        completed=True,
        parent_event_id=started.event_id,
    )
    return result


def _lookup_metadata(
    cache: ResponseCacheService,
    operation: str,
    result: CacheOperationResult,
) -> dict[str, JsonValue]:
    metadata: dict[str, JsonValue] = {
        "operation": operation,
        "outcome": result.outcome.value,
        "policy_version": cache.policy_version,
        "semantic_mode": cache.semantic_mode,
        "avoided_model_request": result.outcome == CacheLookupOutcome.HIT,
    }
    if result.match_kind is not None:
        metadata["match_kind"] = result.match_kind.value
    if result.reason is not None:
        metadata["reason"] = result.reason
    if result.similarity is not None:
        metadata["similarity_bucket"] = _similarity_bucket(result.similarity)
    if result.entry_age_seconds is not None:
        metadata["entry_age_bucket"] = _age_bucket(result.entry_age_seconds)
    return metadata


def _similarity_bucket(similarity: float) -> str:
    if similarity >= 0.98:
        return "0.98_to_1.00"
    if similarity >= 0.95:
        return "0.95_to_0.98"
    if similarity >= 0.90:
        return "0.90_to_0.95"
    return "below_0.90"


def _age_bucket(seconds: float) -> str:
    if seconds < 60:
        return "under_1m"
    if seconds < 3_600:
        return "1m_to_1h"
    if seconds < 21_600:
        return "1h_to_6h"
    return "6h_to_24h"
