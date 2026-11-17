from __future__ import annotations

import asyncio
import json
from typing import Any
import unittest

from edge import RuntimeAdapters, create_app
from edge._identity import InMemoryIdentityStore, PlatformIdentity, PlatformSession
from edge._observability import (
    ADAPTER_NAMES,
    AdapterHealthRegistry,
    CompletionEvent,
    CompletionEventMiddleware,
    ExactSessionOperatorAuthorizer,
    StructuredLoggingCompletionSink,
)
from tests.test_edge_runtime import (
    SOURCE_REVISION,
    FixedCorrelationIds,
    compiled_generation,
    configured_generation,
    protected_generation,
    request_during_lifespan,
    websocket_during_lifespan,
)


class RecordingCompletionSink:
    def __init__(self) -> None:
        self.events: list[CompletionEvent] = []

    async def emit(self, event: CompletionEvent) -> None:
        self.events.append(event)


class FailingCompletionSink:
    async def emit(self, event: CompletionEvent) -> None:
        del event
        raise RuntimeError("prohibited-sink-detail")


class AdvancingClock:
    def __init__(self) -> None:
        self.value = 10.0

    def now(self) -> float:
        current = self.value
        self.value += 0.025
        return current


def health_registry(*, completion_events: bool = True) -> AdapterHealthRegistry:
    return AdapterHealthRegistry(
        {
            name: name == "completion_events" and completion_events
            for name in ADAPTER_NAMES
        }
    )


def http_scope() -> dict[str, Any]:
    return {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.4"},
        "http_version": "1.1",
        "scheme": "https",
        "method": "POST",
        "path": "/private/raw-path-marker",
        "raw_path": b"/private/raw-path-marker",
        "query_string": b"query-secret-marker",
        "headers": [
            (b"authorization", b"Bearer authorization-secret-marker"),
            (b"cookie", b"session=session-secret-marker"),
            (b"user-agent", b"visitor-agent-marker"),
        ],
        "state": {},
        "client": ("203.0.113.10", 44321),
        "server": ("testserver", 443),
    }


async def call_http(app: Any) -> list[dict[str, Any]]:
    incoming = [
        {
            "type": "http.request",
            "body": (
                b"request-body-secret-marker "
                b"stream-chunk-secret-marker "
                b"provider-payload-secret-marker "
                b"application-data-secret-marker "
                b"credential-secret-marker "
                b"terraform-state-secret-marker "
                b"saved-plan-secret-marker"
            ),
            "more_body": False,
        }
    ]
    outgoing: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        return incoming.pop(0)

    async def send(message: dict[str, Any]) -> None:
        outgoing.append(message)

    await app(http_scope(), receive, send)
    return outgoing


class CompletionEventTest(unittest.IsolatedAsyncioTestCase):
    async def test_one_allowlisted_event_excludes_request_and_response_data(self) -> None:
        async def application(scope: Any, receive: Any, send: Any) -> None:
            del scope
            await receive()
            await send(
                {
                    "type": "http.response.start",
                    "status": 201,
                    "headers": [(b"x-private", b"response-secret-marker")],
                }
            )
            await send(
                {
                    "type": "http.response.body",
                    "body": b"response-body-secret-marker",
                }
            )

        sink = RecordingCompletionSink()
        health = health_registry()
        middleware = CompletionEventMiddleware(
            application,
            source_revision=SOURCE_REVISION,
            generation_digest=(
                "sha256:dbbf3a48ddfa7457bb5260bf4060958f"
                "31c2485317a255d51b7adca86c9f9224"
            ),
            correlation_ids=FixedCorrelationIds(["request-correlation-0001"]),
            sink=sink,
            clock=AdvancingClock(),
            health=health,
        )

        outgoing = await call_http(middleware)

        self.assertEqual(outgoing[0]["status"], 201)
        self.assertEqual(len(sink.events), 1)
        event = sink.events[0]
        self.assertEqual(event.outcome, "success")
        self.assertEqual(event.status_class, "2xx")
        self.assertEqual(event.correlation_id, "request-correlation-0001")
        self.assertGreater(event.latency_ms, 0)
        serialized = json.dumps(event.as_dict(), sort_keys=True)
        for prohibited in (
            "private/raw-path-marker",
            "query-secret-marker",
            "authorization-secret-marker",
            "session-secret-marker",
            "visitor-agent-marker",
            "203.0.113.10",
            "request-body-secret-marker",
            "stream-chunk-secret-marker",
            "provider-payload-secret-marker",
            "application-data-secret-marker",
            "credential-secret-marker",
            "terraform-state-secret-marker",
            "saved-plan-secret-marker",
            "response-secret-marker",
            "response-body-secret-marker",
        ):
            self.assertNotIn(prohibited, serialized)
        self.assertEqual(health.snapshot()["completion_events"], "available")

    async def test_sink_failure_does_not_change_the_visitor_response(self) -> None:
        async def application(scope: Any, receive: Any, send: Any) -> None:
            del scope, receive
            await send(
                {"type": "http.response.start", "status": 204, "headers": []}
            )
            await send({"type": "http.response.body", "body": b""})

        health = health_registry()
        middleware = CompletionEventMiddleware(
            application,
            source_revision=SOURCE_REVISION,
            generation_digest=None,
            correlation_ids=FixedCorrelationIds(["request-correlation-0002"]),
            sink=FailingCompletionSink(),
            clock=AdvancingClock(),
            health=health,
        )

        outgoing = await call_http(middleware)

        self.assertEqual(outgoing[0]["status"], 204)
        self.assertEqual(health.snapshot()["completion_events"], "degraded")

    async def test_structured_logging_adapter_emits_only_the_event_document(self) -> None:
        messages: list[str] = []

        class RecordingLogger:
            def info(self, message: str) -> None:
                messages.append(message)

        event = CompletionEvent(
            event_version=1,
            event_type="request_completion",
            source_revision=SOURCE_REVISION,
            generation_digest=None,
            application_id=None,
            route_identifier=None,
            outcome="not_found",
            status_class="4xx",
            latency_ms=3,
            correlation_id="request-correlation-0003",
        )
        sink = StructuredLoggingCompletionSink(RecordingLogger())  # type: ignore[arg-type]

        await sink.emit(event)

        self.assertEqual(json.loads(messages[0]), event.as_dict())


class RuntimeStatusTest(unittest.TestCase):
    def test_status_is_unavailable_without_an_operator_authorizer(self) -> None:
        configuration, source = configured_generation(compiled_generation())
        app = create_app(
            configuration,
            RuntimeAdapters(
                generation_source=source,
                correlation_ids=FixedCorrelationIds(
                    ["request-correlation-0099"]
                ),
            ),
        )

        _, (status, _, body) = asyncio.run(
            request_during_lifespan(app, "/_platform/status")
        )

        self.assertEqual((status, body), (503, b"status unavailable\n"))
        self.assertEqual(source.load_count, 1)

    def test_status_requires_exact_operator_and_reports_read_only_facts(self) -> None:
        restricted_member = "restricted-member-secret-marker"
        configuration, source = configured_generation(
            protected_generation(
                "restricted",
                members=[
                    {
                        "issuer": "https://accounts.google.com",
                        "subject": restricted_member,
                    }
                ],
            )
        )
        identity = PlatformIdentity(
            "https://accounts.google.com",
            "operator-subject-secret-marker",
            "operator-email-secret-marker@example.com",
        )
        session_id = "operator-session-secret-marker"
        store = InMemoryIdentityStore()
        store.sessions[session_id] = PlatformSession(identity, expires_at=20_000)
        events = RecordingCompletionSink()
        app = create_app(
            configuration,
            RuntimeAdapters(
                generation_source=source,
                identity_store=store,
                clock=type("Clock", (), {"now": lambda self: 10_000})(),
                operator_authorizer=ExactSessionOperatorAuthorizer(
                    ((identity.issuer, identity.subject),)
                ),
                correlation_ids=FixedCorrelationIds(
                    [
                        "request-correlation-0100",
                        "request-correlation-0101",
                        "request-correlation-0102",
                    ]
                ),
                completion_events=events,
            ),
        )

        asyncio.run(request_during_lifespan(app, "/"))
        _, (status, headers, body) = asyncio.run(
            request_during_lifespan(
                app,
                "/_platform/status",
                headers=(
                    (
                        b"cookie",
                        f"__Host-comfforts-session={session_id}".encode("ascii"),
                    ),
                    (b"authorization", b"Bearer operator-token-secret-marker"),
                ),
            )
        )
        _, (denied_status, _, denied_body) = asyncio.run(
            request_during_lifespan(app, "/_platform/status")
        )

        self.assertEqual(status, 200)
        self.assertEqual(headers[b"cache-control"], b"no-store")
        document = json.loads(body)
        self.assertEqual(
            set(document),
            {
                "adapter_health",
                "component",
                "component_version",
                "generation",
                "source_revision",
                "status_version",
            },
        )
        self.assertEqual(document["source_revision"], SOURCE_REVISION)
        self.assertEqual(document["generation"]["number"], 2)
        self.assertEqual(
            document["generation"]["digest"],
            compiled_generation()["generation_digest"],
        )
        self.assertEqual(
            document["adapter_health"]["generation_source"],
            "available",
        )
        self.assertEqual(
            document["adapter_health"]["session_store"],
            "available",
        )
        self.assertEqual(
            document["adapter_health"]["identity_provider"],
            "unavailable",
        )
        self.assertEqual(
            document["adapter_health"]["operator_authorization"],
            "available",
        )
        self.assertEqual(
            document["adapter_health"]["completion_events"],
            "available",
        )
        self.assertEqual((denied_status, denied_body), (403, b"forbidden\n"))
        self.assertEqual(source.load_count, 1)
        self.assertEqual(len(events.events), 3)
        serialized = json.dumps(
            {
                "status": document,
                "events": [event.as_dict() for event in events.events],
            },
            sort_keys=True,
        )
        for prohibited in (
            identity.subject,
            identity.email,
            session_id,
            "operator-token-secret-marker",
            restricted_member,
        ):
            assert prohibited is not None
            self.assertNotIn(prohibited, serialized)

    def test_application_and_websocket_events_use_normalized_identifiers(self) -> None:
        configuration, source = configured_generation(compiled_generation())
        events = RecordingCompletionSink()
        app = create_app(
            configuration,
            RuntimeAdapters(
                generation_source=source,
                correlation_ids=FixedCorrelationIds(
                    ["request-correlation-0200", "request-correlation-0201"]
                ),
                completion_events=events,
            ),
        )

        _, (status, _, _) = asyncio.run(
            request_during_lifespan(
                app,
                "/alpha/report",
                query_string=b"private-query-marker",
                headers=(
                    (b"authorization", b"private-authorization-marker"),
                    (b"x-comfforts-verified-identity", b"private-assertion-marker"),
                ),
            )
        )
        _, outgoing = asyncio.run(
            websocket_during_lifespan(app, "/alpha/stream")
        )

        self.assertEqual(status, 503)
        self.assertEqual(outgoing[-1]["code"], 1013)
        self.assertEqual(len(events.events), 2)
        for event in events.events:
            self.assertEqual(event.application_id, "alpha-app")
            self.assertEqual(event.route_identifier, "alpha-app:web")
            self.assertEqual(event.outcome, "dependency_unavailable")
        serialized = json.dumps(
            [event.as_dict() for event in events.events],
            sort_keys=True,
        )
        self.assertNotIn("private-query-marker", serialized)
        self.assertNotIn("private-authorization-marker", serialized)
        self.assertNotIn("private-assertion-marker", serialized)


if __name__ == "__main__":
    unittest.main()
