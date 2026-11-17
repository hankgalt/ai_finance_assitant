"""Read-only runtime status and minimized completion events."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import logging
import re
import secrets
from typing import Any, Literal, Mapping, Protocol

from starlette.requests import Request

from ._generation import LoadedGeneration
from ._identity import PlatformIdentity


RUNTIME_COMPONENT = "shared-edge"
RUNTIME_VERSION = "0.0.0"
CORRELATION_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
SOURCE_REVISION_PATTERN = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
ADAPTER_NAMES = (
    "application_proxy",
    "assertion_issuer",
    "attachment_resolver",
    "completion_events",
    "generation_source",
    "identity_provider",
    "operator_authorization",
    "session_store",
    "verification_keys",
)
OUTCOMES = {
    "cancelled",
    "dependency_unavailable",
    "failed",
    "invalid",
    "limited",
    "not_found",
    "redirected",
    "rejected",
    "success",
}

_CORRELATION_STATE = "comfforts_correlation_id"
_APPLICATION_STATE = "comfforts_application_id"
_ROUTE_STATE = "comfforts_route_identifier"
_OUTCOME_STATE = "comfforts_completion_outcome"


class CorrelationIdSource(Protocol):
    def new(self) -> str: ...


class SecureCorrelationIdSource:
    """Create an opaque request identifier without external I/O."""

    def new(self) -> str:
        return f"request-{secrets.token_hex(16)}"


class OperatorAuthorizer(Protocol):
    async def authorized(
        self,
        request: Request,
        identity: PlatformIdentity | None,
    ) -> bool: ...


class ExactSessionOperatorAuthorizer:
    """Authorize exact immutable identities from an existing Platform Session."""

    def __init__(self, members: tuple[tuple[str, str], ...]) -> None:
        if not 1 <= len(members) <= 16 or len(set(members)) != len(members):
            raise ValueError("operator membership is invalid")
        for issuer, subject in members:
            PlatformIdentity(issuer=issuer, subject=subject)
        self._members = frozenset(members)

    async def authorized(
        self,
        request: Request,
        identity: PlatformIdentity | None,
    ) -> bool:
        del request
        return identity is not None and (
            identity.issuer,
            identity.subject,
        ) in self._members


class AdapterHealthRegistry:
    """Retain only coarse process-local adapter observations."""

    def __init__(self, configured: Mapping[str, bool]) -> None:
        if set(configured) != set(ADAPTER_NAMES):
            raise ValueError("adapter health configuration is incomplete")
        self._states = {
            name: "configured" if configured[name] else "unavailable"
            for name in ADAPTER_NAMES
        }

    def observe(self, name: str, *, available: bool) -> None:
        if name not in self._states:
            raise ValueError("unknown adapter health name")
        self._states[name] = "available" if available else "degraded"

    def snapshot(self) -> dict[str, str]:
        return {name: self._states[name] for name in ADAPTER_NAMES}


@dataclass(frozen=True, slots=True)
class CompletionEvent:
    """The complete allow-list for one request or stream completion record."""

    event_version: Literal[1]
    event_type: Literal["request_completion"]
    source_revision: str
    generation_digest: str | None
    application_id: str | None
    route_identifier: str | None
    outcome: str
    status_class: str
    latency_ms: int
    correlation_id: str
    component: Literal["shared-edge"] = RUNTIME_COMPONENT
    component_version: str = RUNTIME_VERSION

    def __post_init__(self) -> None:
        if (
            self.event_version != 1
            or isinstance(self.event_version, bool)
            or self.event_type != "request_completion"
            or self.component != RUNTIME_COMPONENT
            or self.component_version != RUNTIME_VERSION
        ):
            raise ValueError("completion event metadata is invalid")
        if (
            not isinstance(self.source_revision, str)
            or SOURCE_REVISION_PATTERN.fullmatch(self.source_revision) is None
        ):
            raise ValueError("completion source revision is invalid")
        if self.generation_digest is not None and (
            not isinstance(self.generation_digest, str)
            or re.fullmatch(
                r"sha256:[0-9a-f]{64}",
                self.generation_digest,
            )
            is None
        ):
            raise ValueError("completion generation digest is invalid")
        if self.outcome not in OUTCOMES:
            raise ValueError("completion outcome is invalid")
        if re.fullmatch(r"[1-5]xx|websocket", self.status_class) is None:
            raise ValueError("completion status class is invalid")
        if (
            isinstance(self.latency_ms, bool)
            or not isinstance(self.latency_ms, int)
            or not 0 <= self.latency_ms <= 86_400_000
        ):
            raise ValueError("completion latency is invalid")
        if (
            not isinstance(self.correlation_id, str)
            or CORRELATION_PATTERN.fullmatch(self.correlation_id) is None
        ):
            raise ValueError("completion correlation identifier is invalid")
        for value, label in (
            (self.application_id, "application identifier"),
            (self.route_identifier, "route identifier"),
        ):
            if value is not None and (
                not 1 <= len(value) <= 128
                or re.fullmatch(r"[a-z0-9][a-z0-9:-]*", value) is None
            ):
                raise ValueError(f"completion {label} is invalid")

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class CompletionEventSink(Protocol):
    async def emit(self, event: CompletionEvent) -> None: ...


class StructuredLoggingCompletionSink:
    """Write one minimized JSON object through an injected standard logger."""

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger

    async def emit(self, event: CompletionEvent) -> None:
        self._logger.info(
            json.dumps(
                event.as_dict(),
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            )
        )


def correlation_id(scope: Mapping[str, Any]) -> str | None:
    state = scope.get("state")
    if not isinstance(state, Mapping):
        return None
    value = state.get(_CORRELATION_STATE)
    return (
        value
        if isinstance(value, str) and CORRELATION_PATTERN.fullmatch(value)
        else None
    )


def record_route(
    scope: Mapping[str, Any],
    application_id: str,
    attachment_id: str,
) -> None:
    state = scope.get("state")
    if isinstance(state, dict):
        state[_APPLICATION_STATE] = application_id
        state[_ROUTE_STATE] = f"{application_id}:{attachment_id}"


def record_outcome(scope: Mapping[str, Any], outcome: str) -> None:
    if outcome not in OUTCOMES:
        raise ValueError("completion outcome is invalid")
    state = scope.get("state")
    if isinstance(state, dict):
        state[_OUTCOME_STATE] = outcome


def runtime_status_document(
    *,
    source_revision: str,
    generation: LoadedGeneration,
    health: AdapterHealthRegistry,
) -> dict[str, Any]:
    configuration = generation.configuration
    return {
        "status_version": 1,
        "source_revision": source_revision,
        "component": RUNTIME_COMPONENT,
        "component_version": RUNTIME_VERSION,
        "generation": {
            "contract_version": configuration["contract_version"],
            "compiler_version": configuration["compiler_version"],
            "number": configuration["generation"],
            "digest": generation.generation_digest,
        },
        "adapter_health": health.snapshot(),
    }


def _status_class(scope_type: str, status_code: int | None) -> str:
    if scope_type == "websocket":
        return "websocket"
    if status_code is None or not 100 <= status_code <= 599:
        return "5xx"
    return f"{status_code // 100}xx"


def _default_outcome(
    scope_type: str,
    status_code: int | None,
    failed: bool,
) -> str:
    if failed:
        return "failed"
    if scope_type == "websocket":
        if status_code in {1000, 1001}:
            return "success"
        if status_code in {4400, 1002, 1009}:
            return "invalid"
        if status_code == 4404:
            return "not_found"
        if status_code == 4429:
            return "limited"
        if status_code in {4401, 4403}:
            return "rejected"
        return "dependency_unavailable"
    if status_code is None:
        return "failed"
    if 200 <= status_code <= 299:
        return "success"
    if 300 <= status_code <= 399:
        return "redirected"
    if status_code == 400:
        return "invalid"
    if status_code in {401, 403}:
        return "rejected"
    if status_code == 404:
        return "not_found"
    if status_code in {413, 429}:
        return "limited"
    return "dependency_unavailable" if status_code >= 500 else "rejected"


class CompletionEventMiddleware:
    """Create one minimized event after each HTTP or WebSocket boundary."""

    def __init__(
        self,
        app: Any,
        *,
        source_revision: str,
        generation_digest: str | None,
        correlation_ids: CorrelationIdSource,
        sink: CompletionEventSink | None,
        clock: Any,
        health: AdapterHealthRegistry,
    ) -> None:
        if (
            not isinstance(source_revision, str)
            or SOURCE_REVISION_PATTERN.fullmatch(source_revision) is None
        ):
            raise ValueError("runtime source revision is invalid")
        self._app = app
        self._source_revision = source_revision
        self._generation_digest = generation_digest
        self._correlation_ids = correlation_ids
        self._sink = sink
        self._clock = clock
        self._health = health
        self._fallback_ids = SecureCorrelationIdSource()

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        scope_type = scope.get("type")
        if scope_type not in {"http", "websocket"}:
            await self._app(scope, receive, send)
            return
        try:
            request_id = self._correlation_ids.new()
        except Exception:
            request_id = self._fallback_ids.new()
        if (
            not isinstance(request_id, str)
            or CORRELATION_PATTERN.fullmatch(request_id) is None
        ):
            request_id = self._fallback_ids.new()
        state = scope.setdefault("state", {})
        if isinstance(state, dict):
            state[_CORRELATION_STATE] = request_id
        started_at = self._clock.now()
        status_code: int | None = None
        failed = False

        async def observed_send(message: dict[str, Any]) -> None:
            nonlocal status_code
            if message.get("type") == "http.response.start":
                value = message.get("status")
                if isinstance(value, int):
                    status_code = value
            elif message.get("type") == "websocket.close":
                value = message.get("code", 1000)
                if isinstance(value, int):
                    status_code = value
            await send(message)

        try:
            await self._app(scope, receive, observed_send)
        except BaseException:
            failed = True
            raise
        finally:
            finished_at = self._clock.now()
            state = scope.get("state")
            state = state if isinstance(state, Mapping) else {}
            explicit_outcome = state.get(_OUTCOME_STATE)
            outcome = (
                explicit_outcome
                if isinstance(explicit_outcome, str) and explicit_outcome in OUTCOMES
                else _default_outcome(scope_type, status_code, failed)
            )
            event = CompletionEvent(
                event_version=1,
                event_type="request_completion",
                source_revision=self._source_revision,
                generation_digest=self._generation_digest,
                application_id=(
                    state.get(_APPLICATION_STATE)
                    if isinstance(state.get(_APPLICATION_STATE), str)
                    else None
                ),
                route_identifier=(
                    state.get(_ROUTE_STATE)
                    if isinstance(state.get(_ROUTE_STATE), str)
                    else None
                ),
                outcome=outcome,
                status_class=_status_class(scope_type, status_code),
                latency_ms=min(
                    86_400_000,
                    max(0, int((finished_at - started_at) * 1_000)),
                ),
                correlation_id=request_id,
            )
            if self._sink is not None:
                try:
                    await self._sink.emit(event)
                    self._health.observe("completion_events", available=True)
                except Exception:
                    self._health.observe("completion_events", available=False)
