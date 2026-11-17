from __future__ import annotations

import asyncio
from dataclasses import replace
import hashlib
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
from typing import Any
import unittest

from starlette.responses import Response, StreamingResponse
from starlette.websockets import WebSocket

from edge import RuntimeAdapters, create_app
from edge._attachments import (
    CloudRunAttachmentResolver,
    CloudRunResource,
    CloudRunServiceMetadata,
    InMemoryCloudRunMetadataProvider,
)
from edge._identity import InMemoryIdentityStore, PlatformIdentity, PlatformSession
from edge._proxy import (
    CLIENT_REQUEST_BURST,
    CLIENT_REQUESTS_PER_MINUTE,
    CONNECT_TIMEOUT_SECONDS,
    INSTANCE_REQUEST_BURST,
    INSTANCE_REQUESTS_PER_MINUTE,
    LOGIN_STARTS_PER_TEN_MINUTES,
    LOGIN_START_BURST,
    MAX_ACTIVE_REQUESTS,
    MAX_BUFFERED_RESPONSE_BYTES,
    MAX_CLIENT_STREAMS,
    MAX_REQUEST_BODY_BYTES,
    MAX_STREAM_BYTES,
    MAX_STREAMS,
    MAX_WEBSOCKET_MESSAGE_BYTES,
    REQUEST_TIMEOUT_SECONDS,
    STREAM_ABSOLUTE_TIMEOUT_SECONDS,
    STREAM_IDLE_TIMEOUT_SECONDS,
    WEBSOCKET_MESSAGE_BURST,
    WEBSOCKET_MESSAGES_PER_SECOND,
    BoundedApplicationProxy,
    ProxyLimits,
    RequestGate,
    StreamCapacity,
    UpstreamHttpRequest,
    UpstreamHttpResponse,
)
from tests.test_edge_runtime import (
    FakeGoogleOidc,
    FixedCorrelationIds,
    FixedTokenSource,
    RecordingApplicationProxy,
    RecordingRouteHandoff,
    assertion_components,
    compiled_generation,
    configured_generation,
    protected_generation,
    request_during_lifespan,
    websocket_during_lifespan,
)
from tests.test_proxy import (
    FakeUpstreamWebSocket,
    FakeWebSocketConnector,
    FixedClock,
    StaticHttpTransport,
    render_response,
    request_scope,
    routed_request,
    starlette_request,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXTRACTED_GATE = "AP_EXTRACTED_RUNTIME_GATE"


class CountingUploadTransport:
    def __init__(self) -> None:
        self.bytes_received = 0
        self.cancelled = False

    async def send(self, request: UpstreamHttpRequest) -> UpstreamHttpResponse:
        try:
            async for chunk in request.body:
                self.bytes_received += len(chunk)
        except BaseException:
            self.cancelled = True
            raise

        async def body() -> Any:
            if False:
                yield b""

        async def close() -> None:
            return None

        return UpstreamHttpResponse(
            status_code=204,
            headers=((b"content-length", b"0"),),
            body=body(),
            close=close,
        )


class PullObservedTransport:
    def __init__(self) -> None:
        self.pulls = 0
        self.closed = 0
        self.cancelled = False

    async def send(self, request: UpstreamHttpRequest) -> UpstreamHttpResponse:
        async for _ in request.body:
            pass

        async def body() -> Any:
            self.pulls += 1
            yield b"first"
            try:
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                self.cancelled = True
                raise
            self.pulls += 1
            yield b"second"

        async def close() -> None:
            self.closed += 1

        return UpstreamHttpResponse(
            status_code=200,
            headers=((b"content-type", b"text/event-stream"),),
            body=body(),
            close=close,
        )


async def _consume_stream(response: StreamingResponse) -> int:
    total = 0
    async for chunk in response.body_iterator:
        total += len(chunk)
    return total


class ExactRuntimeProfileTest(unittest.IsolatedAsyncioTestCase):
    def test_profile_accepts_exact_maxima_and_rejects_one_unit_above(self) -> None:
        limits = ProxyLimits()
        maxima: dict[str, int | float] = {
            "request_body_bytes": MAX_REQUEST_BODY_BYTES,
            "buffered_response_bytes": MAX_BUFFERED_RESPONSE_BYTES,
            "stream_bytes": MAX_STREAM_BYTES,
            "websocket_message_bytes": MAX_WEBSOCKET_MESSAGE_BYTES,
            "connect_timeout_seconds": CONNECT_TIMEOUT_SECONDS,
            "request_timeout_seconds": REQUEST_TIMEOUT_SECONDS,
            "stream_idle_timeout_seconds": STREAM_IDLE_TIMEOUT_SECONDS,
            "stream_absolute_timeout_seconds": STREAM_ABSOLUTE_TIMEOUT_SECONDS,
            "active_requests": MAX_ACTIVE_REQUESTS,
            "streams": MAX_STREAMS,
            "client_streams": MAX_CLIENT_STREAMS,
            "client_requests_per_minute": CLIENT_REQUESTS_PER_MINUTE,
            "client_request_burst": CLIENT_REQUEST_BURST,
            "login_starts_per_ten_minutes": LOGIN_STARTS_PER_TEN_MINUTES,
            "login_start_burst": LOGIN_START_BURST,
            "instance_requests_per_minute": INSTANCE_REQUESTS_PER_MINUTE,
            "instance_request_burst": INSTANCE_REQUEST_BURST,
            "websocket_messages_per_second": WEBSOCKET_MESSAGES_PER_SECOND,
            "websocket_message_burst": WEBSOCKET_MESSAGE_BURST,
        }

        for name, maximum in maxima.items():
            with self.subTest(name=name):
                self.assertEqual(getattr(limits, name), maximum)
                with self.assertRaisesRegex(ValueError, name):
                    replace(limits, **{name: maximum + 1})

    async def test_request_body_accepts_25_mib_and_rejects_one_byte_more(self) -> None:
        mebibyte = b"x" * (1_024 * 1_024)
        exact_transport = CountingUploadTransport()
        exact_proxy = BoundedApplicationProxy(exact_transport, None)
        exact_request = starlette_request((mebibyte,) * 25)

        exact_response = await exact_proxy.forward_http(
            exact_request,
            routed_request(),
        )

        self.assertEqual(exact_response.status_code, 204)
        self.assertEqual(exact_transport.bytes_received, MAX_REQUEST_BODY_BYTES)
        self.assertFalse(exact_transport.cancelled)

        overflow_transport = CountingUploadTransport()
        overflow_proxy = BoundedApplicationProxy(overflow_transport, None)
        overflow_request = starlette_request((mebibyte,) * 25 + (b"x",))
        overflow_response = await overflow_proxy.forward_http(
            overflow_request,
            routed_request(),
        )
        overflow_status, _, overflow_body = await render_response(
            overflow_response,
            overflow_request.scope,
        )

        self.assertEqual(overflow_status, 413)
        self.assertEqual(overflow_body, b"request too large\n")
        self.assertEqual(overflow_transport.bytes_received, MAX_REQUEST_BODY_BYTES)
        self.assertTrue(overflow_transport.cancelled)

    async def test_buffered_response_boundary_switches_to_bounded_streaming(self) -> None:
        mebibyte = b"x" * (1_024 * 1_024)
        exact_transport = StaticHttpTransport(
            headers=(
                (b"content-length", str(MAX_BUFFERED_RESPONSE_BYTES).encode()),
            ),
            response_chunks=(mebibyte,) * 25,
        )
        proxy = BoundedApplicationProxy(exact_transport, None)
        request = starlette_request(())

        exact_response = await proxy.forward_http(request, routed_request())

        self.assertIsInstance(exact_response, Response)
        self.assertNotIsInstance(exact_response, StreamingResponse)
        self.assertEqual(len(exact_response.body), MAX_BUFFERED_RESPONSE_BYTES)
        self.assertEqual(exact_transport.close_count, 1)

        streamed_transport = StaticHttpTransport(
            headers=(
                (
                    b"content-length",
                    str(MAX_BUFFERED_RESPONSE_BYTES + 1).encode(),
                ),
            ),
            response_chunks=(mebibyte,) * 25 + (b"x",),
        )
        streamed_proxy = BoundedApplicationProxy(streamed_transport, None)
        streamed_request = starlette_request(())
        streamed_response = await streamed_proxy.forward_http(
            streamed_request,
            routed_request(),
        )
        streamed_total = await _consume_stream(streamed_response)

        self.assertIsInstance(streamed_response, StreamingResponse)
        self.assertEqual(streamed_total, MAX_BUFFERED_RESPONSE_BYTES + 1)
        self.assertEqual(streamed_transport.close_count, 1)

    async def test_stream_accepts_100_mib_and_stops_before_one_byte_more(self) -> None:
        mebibyte = b"x" * (1_024 * 1_024)
        exact_transport = StaticHttpTransport(
            headers=((b"content-type", b"text/event-stream"),),
            response_chunks=(mebibyte,) * 100,
        )
        exact_proxy = BoundedApplicationProxy(exact_transport, None)
        exact_request = starlette_request(())
        exact_response = await exact_proxy.forward_http(
            exact_request,
            routed_request(),
        )
        exact_total = await _consume_stream(exact_response)

        self.assertEqual(exact_total, MAX_STREAM_BYTES)
        self.assertEqual(exact_transport.close_count, 1)

        overflow_transport = StaticHttpTransport(
            headers=((b"content-type", b"text/event-stream"),),
            response_chunks=(mebibyte,) * 100 + (b"x",),
        )
        overflow_proxy = BoundedApplicationProxy(overflow_transport, None)
        overflow_request = starlette_request(())
        overflow_response = await overflow_proxy.forward_http(
            overflow_request,
            routed_request(),
        )
        overflow_total = await _consume_stream(overflow_response)

        self.assertEqual(overflow_total, MAX_STREAM_BYTES)
        self.assertEqual(
            overflow_request.scope["state"]["comfforts_completion_outcome"],
            "limited",
        )
        self.assertEqual(overflow_transport.close_count, 1)

    async def test_active_and_stream_concurrency_close_one_above_maximum(self) -> None:
        gate = RequestGate(ProxyLimits(), FixedClock())
        leases = [
            await gate.acquire(None, login_start=False)
            for _ in range(MAX_ACTIVE_REQUESTS)
        ]
        self.assertTrue(all(lease is not None for lease in leases))
        self.assertIsNone(await gate.acquire(None, login_start=False))
        for lease in leases:
            assert lease is not None
            await lease.release()

        capacity = StreamCapacity(ProxyLimits())
        stream_leases = [
            await capacity.acquire(f"client-{index}")
            for index in range(MAX_STREAMS)
        ]
        self.assertTrue(all(lease is not None for lease in stream_leases))
        self.assertIsNone(await capacity.acquire("another-client"))
        for lease in stream_leases:
            assert lease is not None
            await lease.release()

        client_leases = [
            await capacity.acquire("one-client")
            for _ in range(MAX_CLIENT_STREAMS)
        ]
        self.assertTrue(all(lease is not None for lease in client_leases))
        self.assertIsNone(await capacity.acquire("one-client"))
        for lease in client_leases:
            assert lease is not None
            await lease.release()

    async def test_token_buckets_enforce_exact_bursts_and_deterministic_refill(self) -> None:
        clock = FixedClock()

        async def take_and_release(
            gate: RequestGate,
            key: str | None,
            *,
            login: bool = False,
        ) -> bool:
            lease = await gate.acquire(key, login_start=login)
            if lease is None:
                return False
            await lease.release()
            return True

        client_gate = RequestGate(ProxyLimits(), clock)
        self.assertTrue(
            all(
                [
                    await take_and_release(client_gate, "client-a")
                    for _ in range(int(CLIENT_REQUEST_BURST))
                ]
            )
        )
        self.assertFalse(await take_and_release(client_gate, "client-a"))

        instance_gate = RequestGate(ProxyLimits(), clock)
        self.assertTrue(
            all(
                [
                    await take_and_release(instance_gate, None)
                    for _ in range(int(INSTANCE_REQUEST_BURST))
                ]
            )
        )
        self.assertFalse(await take_and_release(instance_gate, None))

        login_gate = RequestGate(ProxyLimits(), clock)
        self.assertTrue(
            all(
                [
                    await take_and_release(login_gate, "login-client", login=True)
                    for _ in range(int(LOGIN_START_BURST))
                ]
            )
        )
        self.assertFalse(
            await take_and_release(login_gate, "login-client", login=True)
        )

        refill_clock = FixedClock()
        refill_gate = RequestGate(
            replace(
                ProxyLimits(),
                client_request_burst=1,
                client_requests_per_minute=120,
            ),
            refill_clock,
        )
        self.assertTrue(await take_and_release(refill_gate, "refill-client"))
        self.assertFalse(await take_and_release(refill_gate, "refill-client"))
        refill_clock.value += 0.5
        self.assertTrue(await take_and_release(refill_gate, "refill-client"))

        proxy = BoundedApplicationProxy(
            StaticHttpTransport(),
            None,
            clock=clock,
        )
        self.assertTrue(
            all(
                [
                    await proxy._message_allowed("websocket-client")
                    for _ in range(int(WEBSOCKET_MESSAGE_BURST))
                ]
            )
        )
        self.assertFalse(await proxy._message_allowed("websocket-client"))
        clock.value += 1.0
        self.assertTrue(
            all(
                [
                    await proxy._message_allowed("websocket-client")
                    for _ in range(int(WEBSOCKET_MESSAGES_PER_SECOND))
                ]
            )
        )
        self.assertFalse(await proxy._message_allowed("websocket-client"))


class StreamingBehaviorQualificationTest(unittest.IsolatedAsyncioTestCase):
    async def _bridge_messages(
        self,
        messages: list[str | bytes],
        *,
        limits: ProxyLimits | None = None,
    ) -> tuple[FakeUpstreamWebSocket, list[dict[str, Any]]]:
        incoming = list(messages)
        receive_count = 0

        async def receive() -> dict[str, Any]:
            nonlocal receive_count
            receive_count += 1
            if receive_count == 1:
                return {"type": "websocket.connect"}
            if incoming:
                value = incoming.pop(0)
                return (
                    {"type": "websocket.receive", "text": value}
                    if isinstance(value, str)
                    else {"type": "websocket.receive", "bytes": value}
                )
            return {"type": "websocket.disconnect", "code": 1000}

        outgoing: list[dict[str, Any]] = []

        async def send(message: dict[str, Any]) -> None:
            outgoing.append(message)

        websocket = WebSocket(request_scope(scope_type="websocket"), receive, send)
        upstream = FakeUpstreamWebSocket(())
        proxy = BoundedApplicationProxy(
            StaticHttpTransport(),
            FakeWebSocketConnector(upstream),
            limits=limits,
            clock=FixedClock(),
        )
        await proxy.forward_websocket(websocket, routed_request())
        return upstream, outgoing

    async def test_websocket_message_accepts_one_mib_and_rejects_one_byte_more(self) -> None:
        exact = b"x" * MAX_WEBSOCKET_MESSAGE_BYTES
        exact_upstream, exact_outgoing = await self._bridge_messages([exact])
        overflow_upstream, overflow_outgoing = await self._bridge_messages(
            [exact + b"x"]
        )

        self.assertEqual(exact_upstream.sent, [exact])
        self.assertEqual(exact_outgoing[-1]["code"], 1000)
        self.assertEqual(overflow_upstream.sent, [])
        self.assertEqual(overflow_outgoing[-1]["code"], 1009)

    async def test_websocket_burst_accepts_40_messages_and_rejects_the_41st(self) -> None:
        upstream, outgoing = await self._bridge_messages(
            [f"message-{index}" for index in range(41)]
        )

        self.assertEqual(len(upstream.sent), int(WEBSOCKET_MESSAGE_BURST))
        self.assertEqual(outgoing[-1]["code"], 4429)

    async def test_websocket_idle_timeout_closes_both_directions(self) -> None:
        receive_count = 0

        async def receive() -> dict[str, Any]:
            nonlocal receive_count
            receive_count += 1
            if receive_count == 1:
                return {"type": "websocket.connect"}
            await asyncio.sleep(60)
            raise AssertionError("visitor receive unexpectedly completed")

        outgoing: list[dict[str, Any]] = []

        async def send(message: dict[str, Any]) -> None:
            outgoing.append(message)

        upstream = FakeUpstreamWebSocket(())
        websocket = WebSocket(request_scope(scope_type="websocket"), receive, send)
        proxy = BoundedApplicationProxy(
            StaticHttpTransport(),
            FakeWebSocketConnector(upstream),
            limits=replace(
                ProxyLimits(),
                stream_idle_timeout_seconds=0.01,
                stream_absolute_timeout_seconds=1,
            ),
        )

        await proxy.forward_websocket(websocket, routed_request())

        self.assertIn(1013, upstream.close_codes)
        self.assertEqual(outgoing[-1]["code"], 1013)

    async def test_stream_pulls_on_demand_and_cancels_after_visitor_disconnect(self) -> None:
        transport = PullObservedTransport()
        request = starlette_request(())
        proxy = BoundedApplicationProxy(transport, None)

        response = await proxy.forward_http(request, routed_request())

        self.assertEqual(transport.pulls, 0)
        iterator = response.body_iterator.__aiter__()
        self.assertEqual(await anext(iterator), b"first")
        self.assertEqual(transport.pulls, 1)
        pending = asyncio.create_task(anext(iterator))
        await asyncio.sleep(0)
        pending.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await pending

        self.assertTrue(transport.cancelled)
        self.assertEqual(transport.closed, 1)
        self.assertEqual(
            request.scope["state"]["comfforts_completion_outcome"],
            "cancelled",
        )


class RuntimeIsolationQualificationTest(unittest.TestCase):
    def test_session_revocation_applies_to_the_next_request_and_stream(self) -> None:
        identity = PlatformIdentity(
            "https://accounts.google.com",
            "revoked-subject",
        )
        document = protected_generation("authenticated")
        configuration, source = configured_generation(
            document,
            external_origin="https://apps-staging.comfforts.com",
        )
        store = InMemoryIdentityStore()
        session_id = "revocation-session-0123456789"
        store.sessions[session_id] = PlatformSession(identity, expires_at=20_000)
        clock = type("Clock", (), {"now": lambda self: 10_000})()
        assertion_issuer, _ = assertion_components(
            clock,
            ["unused-assertion-correlation"],
        )
        handoff = RecordingRouteHandoff()
        app = create_app(
            configuration,
            RuntimeAdapters(
                generation_source=source,
                route_handoff=handoff,
                google_oidc=FakeGoogleOidc(identity),
                identity_store=store,
                clock=clock,
                token_source=FixedTokenSource([]),
                assertion_issuer=assertion_issuer,
                correlation_ids=FixedCorrelationIds(
                    [
                        "request-revocation-0001",
                        "request-revocation-0002",
                        "request-revocation-0003",
                    ]
                ),
            ),
        )
        cookie = (
            (b"cookie", f"__Host-comfforts-session={session_id}".encode()),
        )

        _, (first_status, _, _) = asyncio.run(
            request_during_lifespan(app, "/alpha", headers=cookie)
        )
        store.sessions.pop(session_id)
        _, (revoked_status, revoked_headers, _) = asyncio.run(
            request_during_lifespan(app, "/alpha", headers=cookie)
        )
        _, websocket_messages = asyncio.run(
            websocket_during_lifespan(app, "/alpha", headers=cookie)
        )

        self.assertEqual(first_status, 503)
        self.assertEqual(len(handoff.requests), 1)
        self.assertEqual(revoked_status, 303)
        self.assertTrue(
            revoked_headers[b"location"].startswith(b"/_platform/login?")
        )
        self.assertEqual(websocket_messages[-1]["code"], 4401)

    def test_one_application_failure_does_not_block_an_independent_route(self) -> None:
        document = _two_application_cloud_run_generation()
        configuration, source = configured_generation(document)
        edge_caller = (
            "serviceAccount:apps-platform-edge@comfforts-platform-non-prod."
            "iam.gserviceaccount.com"
        )
        beta_resource = CloudRunResource(
            project_number="455651441682",
            region="us-west1",
            service_name="beta-app",
        )
        provider = InMemoryCloudRunMetadataProvider(
            {
                beta_resource: CloudRunServiceMetadata(
                    resource=beta_resource,
                    target_uri=(
                        "https://beta-app-455651441682.us-west1.run.app"
                    ),
                    ready=True,
                    owner_application_id="beta-app",
                    audience=None,
                    invoker_principals=frozenset({edge_caller}),
                )
            }
        )
        proxy = RecordingApplicationProxy()
        app = create_app(
            configuration,
            RuntimeAdapters(
                generation_source=source,
                attachment_resolver=CloudRunAttachmentResolver(
                    provider,
                    edge_caller,
                ),
                application_proxy=proxy,
                correlation_ids=FixedCorrelationIds(
                    ["request-isolation-0001", "request-isolation-0002"]
                ),
            ),
        )

        _, (alpha_status, _, alpha_body) = asyncio.run(
            request_during_lifespan(app, "/alpha")
        )
        _, (beta_status, _, beta_body) = asyncio.run(
            request_during_lifespan(app, "/beta")
        )

        self.assertEqual(
            (alpha_status, alpha_body),
            (503, b"application attachment unavailable\n"),
        )
        self.assertEqual((beta_status, beta_body), (202, b"proxied\n"))
        self.assertEqual(len(proxy.http_requests), 1)
        self.assertEqual(proxy.http_requests[0][1].application_id, "beta-app")
        self.assertEqual(provider.requests, [
            CloudRunResource(
                project_number="455651441682",
                region="us-west1",
                service_name="alpha-app",
            ),
            beta_resource,
        ])


def _two_application_cloud_run_generation() -> dict[str, Any]:
    document = compiled_generation()
    alpha = document["routes"][0]
    alpha_attachment = alpha["attachments"][0]
    alpha_attachment.update(
        adapter_kind="gcp-cloud-run-v1",
        resource_reference=(
            "urn:comfforts:app-platform:gcp:cloud-run:455651441682:"
            "us-west1:alpha-app"
        ),
    )
    document["application_states"].append(
        {
            "application_id": "beta-app",
            "registration_revision": 1,
            "route_prefix": "/beta",
            "lifecycle": "active",
        }
    )
    document["catalogue"].append(
        {
            "application_id": "beta-app",
            "title": "Beta",
            "summary": "Independent qualification application",
            "route_prefix": "/beta",
            "admission_mode": "public",
        }
    )
    document["routes"].append(
        {
            "application_id": "beta-app",
            "route_prefix": "/beta",
            "attachments": [
                {
                    "contract_version": 1,
                    "owner_application_id": "beta-app",
                    "attachment_id": "web",
                    "adapter_kind": "gcp-cloud-run-v1",
                    "resource_reference": (
                        "urn:comfforts:app-platform:gcp:cloud-run:455651441682:"
                        "us-west1:beta-app"
                    ),
                    "mount_path": "/",
                    "forwarding_mode": "strip_application_prefix",
                    "identity_requirement": "none",
                    "audience": None,
                    "ingress_mode": "shared_edge_only",
                }
            ],
        }
    )
    document["admission_policies"].append(
        {"application_id": "beta-app", "policy": {"mode": "public"}}
    )
    return document


class GateIntegrityTest(unittest.TestCase):
    def test_test_process_rejects_dns_and_non_loopback_connections(self) -> None:
        with self.assertRaisesRegex(AssertionError, "DNS or a non-loopback"):
            socket.getaddrinfo("example.com", 443)
        candidate = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            with self.assertRaisesRegex(AssertionError, "non-loopback"):
                candidate.connect(("192.0.2.1", 443))
            with self.assertRaisesRegex(AssertionError, "non-loopback"):
                candidate.bind(("0.0.0.0", 0))
        finally:
            candidate.close()
        self.assertTrue(socket.getaddrinfo("127.0.0.1", 443))

    def test_identity_module_import_has_no_unexpected_warning(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-W",
                "error",
                "-c",
                "import edge._identity",
            ],
            cwd=PROJECT_ROOT,
            env={
                "PATH": os.environ.get("PATH", ""),
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONPATH": str(PROJECT_ROOT),
            },
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")

    def test_complete_gate_runs_from_an_unchanged_history_independent_copy(self) -> None:
        if os.environ.get(EXTRACTED_GATE) == "1":
            self.assertFalse((PROJECT_ROOT / ".git").exists())
            return
        with tempfile.TemporaryDirectory() as temporary_directory:
            extracted_root = Path(temporary_directory) / "apps-platform"
            shutil.copytree(
                PROJECT_ROOT,
                extracted_root,
                ignore=shutil.ignore_patterns(
                    ".git",
                    ".venv",
                    "__pycache__",
                    "*.pyc",
                    ".DS_Store",
                ),
            )
            before = _tree_digest(extracted_root)
            environment = {
                "PATH": os.environ.get("PATH", ""),
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONPATH": str(extracted_root),
                "TMPDIR": os.environ.get("TMPDIR", "/tmp"),
                EXTRACTED_GATE: "1",
            }

            result = subprocess.run(
                ["make", f"PYTHON={sys.executable}", "check"],
                cwd=extracted_root,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
                timeout=60,
            )

            self.assertEqual(
                result.returncode,
                0,
                result.stdout + result.stderr,
            )
            combined = (result.stdout + result.stderr).lower()
            self.assertNotIn("skipped", combined)
            self.assertNotIn("warning", combined)
            self.assertEqual(_tree_digest(extracted_root), before)

    def test_ap_eval_m6_trace_names_every_gate_and_work_package(self) -> None:
        gate_trace = {
            "AP-EVAL-M6-01": (
                "tests.test_governance.ProjectAuthorityTest",
                "tests.test_runtime_qualification.GateIntegrityTest",
            ),
            "AP-EVAL-M6-02": (
                "tests.test_proxy.ProxyEnvelopeTest",
                "tests.test_runtime_qualification.ExactRuntimeProfileTest",
            ),
            "AP-EVAL-M6-03": (
                "tests.test_edge_runtime.SharedEdgeInterfaceTest",
            ),
            "AP-EVAL-M6-04": (
                "tests.test_edge_runtime.IdentityAdapterTest",
                "tests.test_edge_runtime.SharedEdgeInterfaceTest",
            ),
            "AP-EVAL-M6-05": (
                "tests.test_edge_runtime.ApplicationVerificationTest",
                "tests.test_edge_runtime.SharedEdgeInterfaceTest",
            ),
            "AP-EVAL-M6-06": (
                "tests.test_edge_runtime.CloudRunAttachmentTest",
            ),
            "AP-EVAL-M6-07": (
                "tests.test_proxy.ProductionTransportTest",
                "tests.test_proxy.BoundedProxyTest",
                "tests.test_proxy.WebSocketBridgeTest",
                "tests.test_runtime_qualification.StreamingBehaviorQualificationTest",
                "tests.test_runtime_qualification.RuntimeIsolationQualificationTest",
            ),
            "AP-EVAL-M6-08": (
                "tests.test_observability.CompletionEventTest",
                "tests.test_observability.RuntimeStatusTest",
            ),
            "AP-EVAL-M6-09": (
                "tests.test_governance.ProjectAuthorityTest",
                "tests.test_runtime_qualification.GateIntegrityTest",
            ),
            "AP-EVAL-M6-10": (
                "tests.test_runtime_qualification.GateIntegrityTest",
            ),
        }
        work_package_trace = {
            "AP-M6-W1": ("docs/03_system_design.md",),
            "AP-M6-W2": ("pyproject.toml", "uv.lock", "edge/__init__.py"),
            "AP-M6-W3": ("edge/_generation.py",),
            "AP-M6-W4": ("edge/_routing.py",),
            "AP-M6-W5": ("edge/_identity.py",),
            "AP-M6-W6": ("edge/_assertions.py", "edge/verification.py"),
            "AP-M6-W7": ("edge/_attachments.py",),
            "AP-M6-W8": ("edge/_proxy.py",),
            "AP-M6-W9": ("edge/_observability.py",),
            "AP-M6-W10": ("tests/test_runtime_qualification.py",),
            "AP-M6-W11": (
                "README.md",
                "docs/README.md",
                "prompts/starting_prompt.md",
            ),
        }

        self.assertEqual(
            set(gate_trace),
            {f"AP-EVAL-M6-{index:02d}" for index in range(1, 11)},
        )
        self.assertEqual(
            set(work_package_trace),
            {f"AP-M6-W{index}" for index in range(1, 12)},
        )
        loader = unittest.TestLoader()
        for gate, test_names in gate_trace.items():
            with self.subTest(gate=gate):
                self.assertTrue(test_names)
                for test_name in test_names:
                    error_count = len(loader.errors)
                    self.assertGreater(
                        loader.loadTestsFromName(test_name).countTestCases(),
                        0,
                        test_name,
                    )
                    self.assertEqual(loader.errors[error_count:], [], test_name)
        for work_package, paths in work_package_trace.items():
            with self.subTest(work_package=work_package):
                self.assertTrue(paths)
                self.assertTrue(
                    all((PROJECT_ROOT / path).is_file() for path in paths),
                    paths,
                )
        self.assertIn(
            "tests.test_runtime_qualification",
            (PROJECT_ROOT / "Makefile").read_text(encoding="utf-8"),
        )


def _tree_digest(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


if __name__ == "__main__":
    unittest.main()
