from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import replace
from types import SimpleNamespace
from typing import Any
import unittest
from unittest.mock import patch

import httpx
from starlette.requests import Request
from starlette.websockets import WebSocket
from websockets.asyncio.server import serve

from edge._attachments import CloudRunResource, ResolvedAttachment
from edge._proxy import (
    BoundedApplicationProxy,
    GoogleAuthServiceIdentityTokenSource,
    HttpxApplicationTransport,
    ProxyLimits,
    RequestGate,
    ScopeTrustedClientClassifier,
    UpstreamHttpRequest,
    UpstreamHttpResponse,
    UpstreamWebSocketRequest,
    WebsocketsApplicationConnector,
    application_request_headers,
    validate_request_scope,
)
from edge._routing import RoutedApplicationRequest


class FixedClock:
    def __init__(self, value: float = 1_000.0) -> None:
        self.value = value

    def now(self) -> float:
        return self.value


class FixedIdentityTokens:
    def __init__(self) -> None:
        self.audiences: list[str] = []

    async def token(self, audience: str) -> str:
        self.audiences.append(audience)
        return "test-only.service.identity.token"


async def byte_stream(*chunks: bytes) -> Any:
    for chunk in chunks:
        yield chunk


class StaticHttpTransport:
    def __init__(
        self,
        *,
        status_code: int = 200,
        headers: tuple[tuple[bytes, bytes], ...] = (),
        response_chunks: tuple[bytes, ...] = (),
        response_delay: float = 0.0,
    ) -> None:
        self.status_code = status_code
        self.headers = headers
        self.response_chunks = response_chunks
        self.response_delay = response_delay
        self.requests: list[UpstreamHttpRequest] = []
        self.request_bodies: list[bytes] = []
        self.close_count = 0

    async def send(self, request: UpstreamHttpRequest) -> UpstreamHttpResponse:
        self.requests.append(request)
        body = bytearray()
        async for chunk in request.body:
            body.extend(chunk)
        self.request_bodies.append(bytes(body))

        async def response_body() -> Any:
            for chunk in self.response_chunks:
                if self.response_delay:
                    await asyncio.sleep(self.response_delay)
                yield chunk

        async def close() -> None:
            self.close_count += 1

        return UpstreamHttpResponse(
            status_code=self.status_code,
            headers=self.headers,
            body=response_body(),
            close=close,
        )


class SlowHttpTransport:
    def __init__(self) -> None:
        self.cancelled = False

    async def send(self, request: UpstreamHttpRequest) -> UpstreamHttpResponse:
        del request
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        raise AssertionError("slow transport unexpectedly completed")


def routed_request(
    *,
    target_uri: str = "https://alpha-app-455651441682.us-west1.run.app",
    assertion: str | None = "signed.application.assertion",
) -> RoutedApplicationRequest:
    resource = CloudRunResource(
        project_number="455651441682",
        region="us-west1",
        service_name="alpha-app",
    )
    return RoutedApplicationRequest(
        application_id="alpha-app",
        attachment_id="web",
        attachment_owner_application_id="alpha-app",
        adapter_kind="gcp-cloud-run-v1",
        resource_reference=(
            "urn:comfforts:app-platform:gcp:cloud-run:455651441682:"
            "us-west1:alpha-app"
        ),
        path="/report",
        query_string=b"view=summary",
        identity_audience="urn:comfforts:app-platform:audience:alpha-app",
        verified_identity_assertion=assertion,
        resolved_attachment=ResolvedAttachment(
            adapter_kind="gcp-cloud-run-v1",
            resource=resource,
            target_uri=target_uri,
            audience="urn:comfforts:app-platform:audience:alpha-app",
        ),
    )


def request_scope(
    *,
    method: str = "POST",
    path: str = "/alpha/report",
    raw_path: bytes | None = None,
    query: bytes = b"view=summary",
    headers: tuple[tuple[bytes, bytes], ...] = (),
    scope_type: str = "http",
) -> dict[str, Any]:
    return {
        "type": scope_type,
        "asgi": {"version": "3.0", "spec_version": "2.4"},
        "http_version": "1.1",
        "scheme": "https",
        "method": method,
        "path": path,
        "raw_path": raw_path if raw_path is not None else path.encode("utf-8"),
        "query_string": query,
        "headers": list(headers),
        "state": {},
        "client": ("127.0.0.1", 43210),
        "server": ("testserver", 443),
        "subprotocols": ["chat"],
    }


def starlette_request(
    chunks: tuple[bytes, ...],
    *,
    headers: tuple[tuple[bytes, bytes], ...] = (),
) -> Request:
    messages = [
        {
            "type": "http.request",
            "body": chunk,
            "more_body": index < len(chunks) - 1,
        }
        for index, chunk in enumerate(chunks)
    ]
    if not messages:
        messages.append({"type": "http.request", "body": b"", "more_body": False})

    async def receive() -> dict[str, Any]:
        if messages:
            return messages.pop(0)
        return {"type": "http.disconnect"}

    return Request(request_scope(headers=headers), receive)


async def render_response(
    response: Any,
    scope: dict[str, Any] | None = None,
) -> tuple[int, list[tuple[bytes, bytes]], bytes]:
    outgoing: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        return {"type": "http.disconnect"}

    async def send(message: dict[str, Any]) -> None:
        outgoing.append(message)

    await response(scope or request_scope(), receive, send)
    start = next(item for item in outgoing if item["type"] == "http.response.start")
    body = b"".join(
        item.get("body", b"")
        for item in outgoing
        if item["type"] == "http.response.body"
    )
    return start["status"], start["headers"], body


class ProxyEnvelopeTest(unittest.TestCase):
    def test_request_envelope_accepts_exact_limits_and_rejects_one_beyond(self) -> None:
        accepted = (
            request_scope(method="M" * 16),
            request_scope(raw_path=b"/" + b"a" * 4_095, path="/" + "a" * 4_095),
            request_scope(query=b"a" * 8_192),
            request_scope(headers=tuple((f"x-{index}".encode(), b"") for index in range(64))),
            request_scope(headers=((b"x" + b"a" * 127, b""),)),
            request_scope(headers=((b"x-value", b"a" * 8_192),)),
            request_scope(
                headers=tuple((b"x", b"a" * 8_187) for _ in range(4))
            ),
            request_scope(headers=((b"content-length", b"26214400"),)),
        )
        rejected = (
            (request_scope(method="M" * 17), 400),
            (
                request_scope(
                    raw_path=b"/" + b"a" * 4_096,
                    path="/" + "a" * 4_096,
                ),
                400,
            ),
            (request_scope(query=b"a" * 8_193), 400),
            (
                request_scope(
                    headers=tuple((f"x-{index}".encode(), b"") for index in range(65))
                ),
                400,
            ),
            (request_scope(headers=((b"x" + b"a" * 128, b""),)), 400),
            (request_scope(headers=((b"x-value", b"a" * 8_193),)), 400),
            (
                request_scope(
                    headers=(
                        (b"x", b"a" * 8_188),
                        *((b"x", b"a" * 8_187) for _ in range(3)),
                    )
                ),
                400,
            ),
            (request_scope(headers=((b"content-length", b"26214401"),)), 413),
        )

        for scope in accepted:
            with self.subTest(accepted=(scope["method"], len(scope["raw_path"]))):
                self.assertIsNone(validate_request_scope(scope))
        for scope, status in rejected:
            with self.subTest(rejected=(scope["method"], len(scope["raw_path"]))):
                self.assertEqual(validate_request_scope(scope)[0], status)

    def test_request_envelope_rejects_ambiguous_security_framing(self) -> None:
        cases = (
            ((b"authorization", b"one"), (b"authorization", b"two")),
            ((b"cookie", b"one=1"), (b"cookie", b"two=2")),
            ((b"content-length", b"1"), (b"transfer-encoding", b"chunked")),
            ((b"content-length", b"+1"),),
            ((b"transfer-encoding", b"gzip"),),
            ((b"X-UPPER", b"value"),),
            ((b"x-value", b"line\r\nbreak"),),
        )
        for headers in cases:
            with self.subTest(headers=headers):
                self.assertEqual(
                    validate_request_scope(request_scope(headers=headers)),
                    (400, "invalid request"),
                )

    def test_only_server_authenticated_scope_metadata_becomes_client_key(self) -> None:
        classifier = ScopeTrustedClientClassifier()
        scope = request_scope(
            headers=((b"x-forwarded-for", b"visitor-controlled"),)
        )

        self.assertIsNone(classifier.classify(scope))
        scope["extensions"] = {
            "comfforts.trusted_client": {"key": "lb-client:abc123"}
        }
        self.assertEqual(classifier.classify(scope), "lb-client:abc123")

    def test_application_headers_replace_identity_and_transport_authority(self) -> None:
        headers = application_request_headers(
            (
                (b"host", b"visitor.example"),
                (b"authorization", b"Bearer visitor-value"),
                (b"x-comfforts-correlation-id", b"visitor-controlled"),
                (b"x-comfforts-verified-identity", b"forged"),
                (b"x-forwarded-for", b"visitor-controlled"),
                (b"connection", b"keep-alive, x-remove"),
                (b"x-remove", b"remove-me"),
                (b"content-type", b"application/json"),
                (
                    b"cookie",
                    b"__Host-comfforts-session=secret; app_preference=compact",
                ),
            ),
            "signed.application.assertion",
            "request-correlation-0001",
        )

        self.assertEqual(
            headers,
            (
                (b"content-type", b"application/json"),
                (b"cookie", b"app_preference=compact"),
                (
                    b"x-comfforts-verified-identity",
                    b"signed.application.assertion",
                ),
                (
                    b"x-comfforts-correlation-id",
                    b"request-correlation-0001",
                ),
            ),
        )


class RequestGateTest(unittest.IsolatedAsyncioTestCase):
    async def test_active_request_and_client_rate_limits_fail_without_waiting(self) -> None:
        clock = FixedClock()
        active_gate = RequestGate(
            replace(ProxyLimits(), active_requests=1),
            clock,
        )
        lease = await active_gate.acquire(None, login_start=False)
        self.assertIsNotNone(lease)
        self.assertIsNone(await active_gate.acquire(None, login_start=False))
        assert lease is not None
        await lease.release()

        client_gate = RequestGate(
            replace(
                ProxyLimits(),
                client_request_burst=1,
                client_requests_per_minute=1,
            ),
            clock,
        )
        first = await client_gate.acquire("client-a", login_start=False)
        self.assertIsNotNone(first)
        assert first is not None
        await first.release()
        self.assertIsNone(
            await client_gate.acquire("client-a", login_start=False)
        )
        other = await client_gate.acquire("client-b", login_start=False)
        self.assertIsNotNone(other)

    async def test_instance_and_login_bursts_are_independent_closed_limits(self) -> None:
        clock = FixedClock()
        instance_gate = RequestGate(
            replace(
                ProxyLimits(),
                instance_request_burst=1,
                instance_requests_per_minute=1,
            ),
            clock,
        )
        first = await instance_gate.acquire(None, login_start=False)
        self.assertIsNotNone(first)
        assert first is not None
        await first.release()
        self.assertIsNone(await instance_gate.acquire(None, login_start=False))

        login_gate = RequestGate(
            replace(
                ProxyLimits(),
                login_start_burst=1,
                login_starts_per_ten_minutes=1,
            ),
            clock,
        )
        login = await login_gate.acquire("client-a", login_start=True)
        self.assertIsNotNone(login)
        assert login is not None
        await login.release()
        regular = await login_gate.acquire("client-a", login_start=False)
        self.assertIsNotNone(regular)
        assert regular is not None
        await regular.release()
        self.assertIsNone(
            await login_gate.acquire("client-a", login_start=True)
        )


class ProductionTransportTest(unittest.IsolatedAsyncioTestCase):
    async def test_google_identity_adapter_is_inert_until_token_request(self) -> None:
        auth_request = object()
        source = GoogleAuthServiceIdentityTokenSource(auth_request)

        with patch(
            "edge._proxy.google_id_token.fetch_id_token",
            return_value="test-only.service.identity.token",
        ) as fetch:
            fetch.assert_not_called()
            token = await source.token("https://service.run.app")

        self.assertEqual(token, "test-only.service.identity.token")
        fetch.assert_called_once_with(auth_request, "https://service.run.app")

    async def test_httpx_transport_uses_loopback_and_preserves_path_query_upload(self) -> None:
        observed: dict[str, Any] = {}

        async def handler(
            reader: asyncio.StreamReader,
            writer: asyncio.StreamWriter,
        ) -> None:
            head = await reader.readuntil(b"\r\n\r\n")
            lines = head.split(b"\r\n")
            observed["request_line"] = lines[0]
            headers = {
                name.lower(): value.strip()
                for line in lines[1:]
                if line
                for name, value in (line.split(b":", 1),)
            }
            observed["authorization"] = headers[b"authorization"]
            length = int(headers[b"content-length"])
            observed["body"] = await reader.readexactly(length)
            writer.write(
                b"HTTP/1.1 201 Created\r\n"
                b"Content-Length: 2\r\n"
                b"Content-Type: text/plain\r\n\r\nok"
            )
            await writer.drain()
            writer.close()
            await writer.wait_closed()

        server = await asyncio.start_server(handler, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        tokens = FixedIdentityTokens()
        try:
            async with httpx.AsyncClient(trust_env=False) as client:
                transport = HttpxApplicationTransport(client, tokens)
                response = await transport.send(
                    UpstreamHttpRequest(
                        method="POST",
                        target_uri=f"http://127.0.0.1:{port}",
                        path="/upload",
                        query_string=b"item=%2Fone",
                        headers=(
                            (b"content-length", b"4"),
                            (b"content-type", b"text/plain"),
                        ),
                        body=byte_stream(b"da", b"ta"),
                    )
                )
                body = b"".join([chunk async for chunk in response.body])
                await response.close()
        finally:
            server.close()
            await server.wait_closed()

        self.assertEqual(
            observed["request_line"],
            b"POST /upload?item=%2Fone HTTP/1.1",
        )
        self.assertEqual(
            observed["authorization"],
            b"Bearer test-only.service.identity.token",
        )
        self.assertEqual(observed["body"], b"data")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(body, b"ok")
        self.assertEqual(tokens.audiences, [f"http://127.0.0.1:{port}"])

    async def test_websocket_connector_uses_process_local_loopback(self) -> None:
        observed: dict[str, Any] = {}

        async def handler(connection: Any) -> None:
            observed["path"] = connection.request.path
            observed["authorization"] = connection.request.headers["authorization"]
            message = await connection.recv()
            await connection.send(f"echo:{message}")

        server = await serve(
            handler,
            "127.0.0.1",
            0,
            subprotocols=["chat"],
            server_header=None,
        )
        port = server.sockets[0].getsockname()[1]
        tokens = FixedIdentityTokens()
        connector = WebsocketsApplicationConnector(tokens)
        try:
            async with connector.connect(
                UpstreamWebSocketRequest(
                    target_uri=f"http://127.0.0.1:{port}",
                    path="/stream",
                    query_string=b"view=compact",
                    headers=((b"x-test", b"value"),),
                    subprotocols=("chat",),
                )
            ) as connection:
                await connection.send("hello")
                reply = await connection.recv()
                subprotocol = connection.subprotocol
        finally:
            server.close()
            await server.wait_closed()

        self.assertEqual(reply, "echo:hello")
        self.assertEqual(subprotocol, "chat")
        self.assertEqual(observed["path"], "/stream?view=compact")
        self.assertEqual(
            observed["authorization"],
            "Bearer test-only.service.identity.token",
        )


class BoundedProxyTest(unittest.IsolatedAsyncioTestCase):
    async def test_buffered_proxy_forwards_upload_and_safe_status_headers(self) -> None:
        transport = StaticHttpTransport(
            status_code=201,
            headers=(
                (b"content-length", b"2"),
                (b"content-type", b"text/plain"),
                (b"connection", b"x-remove"),
                (b"x-remove", b"unsafe"),
                (
                    b"set-cookie",
                    b"__Host-comfforts-session=application-controlled; Path=/",
                ),
                (b"set-cookie", b"app_preference=compact; Path=/alpha"),
                (b"clear-site-data", b'"cookies"'),
            ),
            response_chunks=(b"ok",),
        )
        proxy = BoundedApplicationProxy(transport, None)
        request = starlette_request(
            (b"pay", b"load"),
            headers=(
                (b"content-length", b"7"),
                (b"authorization", b"visitor"),
                (b"x-comfforts-verified-identity", b"forged"),
            ),
        )

        response = await proxy.forward_http(request, routed_request())
        status, headers, body = await render_response(response, request.scope)

        self.assertEqual(status, 201)
        self.assertEqual(body, b"ok")
        self.assertEqual(transport.request_bodies, [b"payload"])
        forwarded = transport.requests[0]
        self.assertEqual(forwarded.path, "/report")
        self.assertEqual(forwarded.query_string, b"view=summary")
        self.assertNotIn((b"authorization", b"visitor"), forwarded.headers)
        self.assertIn(
            (
                b"x-comfforts-verified-identity",
                b"signed.application.assertion",
            ),
            forwarded.headers,
        )
        self.assertNotIn((b"x-remove", b"unsafe"), headers)
        self.assertNotIn(
            (
                b"set-cookie",
                b"__Host-comfforts-session=application-controlled; Path=/",
            ),
            headers,
        )
        self.assertIn(
            (b"set-cookie", b"app_preference=compact; Path=/alpha"),
            headers,
        )
        self.assertNotIn((b"clear-site-data", b'"cookies"'), headers)
        self.assertEqual(transport.close_count, 1)

    async def test_upload_overflow_is_cancelled_with_closed_413(self) -> None:
        transport = StaticHttpTransport()
        proxy = BoundedApplicationProxy(
            transport,
            None,
            limits=replace(ProxyLimits(), request_body_bytes=5),
        )
        request = starlette_request((b"123", b"456"))

        response = await proxy.forward_http(request, routed_request())
        status, _, body = await render_response(response, request.scope)

        self.assertEqual(status, 413)
        self.assertEqual(body, b"request too large\n")
        self.assertEqual(transport.request_bodies, [])

    async def test_sse_stream_closes_on_limit_and_releases_transport(self) -> None:
        transport = StaticHttpTransport(
            headers=((b"content-type", b"text/event-stream"),),
            response_chunks=(b"123", b"456"),
        )
        proxy = BoundedApplicationProxy(
            transport,
            None,
            limits=replace(ProxyLimits(), stream_bytes=5),
        )
        request = starlette_request(())

        response = await proxy.forward_http(request, routed_request())
        status, headers, body = await render_response(response, request.scope)

        self.assertEqual(status, 200)
        self.assertIn((b"content-type", b"text/event-stream"), headers)
        self.assertEqual(body, b"123")
        self.assertEqual(transport.close_count, 1)

    async def test_stream_idle_timeout_closes_without_leaking_error_detail(self) -> None:
        transport = StaticHttpTransport(
            headers=((b"content-type", b"text/event-stream"),),
            response_chunks=(b"late",),
            response_delay=0.05,
        )
        proxy = BoundedApplicationProxy(
            transport,
            None,
            limits=replace(ProxyLimits(), stream_idle_timeout_seconds=0.01),
        )
        request = starlette_request(())

        response = await proxy.forward_http(request, routed_request())
        status, _, body = await render_response(response, request.scope)

        self.assertEqual(status, 200)
        self.assertEqual(body, b"")
        self.assertEqual(transport.close_count, 1)

    async def test_non_stream_timeout_cancels_target_work(self) -> None:
        transport = SlowHttpTransport()
        proxy = BoundedApplicationProxy(
            transport,
            None,
            limits=replace(ProxyLimits(), request_timeout_seconds=0.01),
        )
        request = starlette_request(())

        response = await proxy.forward_http(request, routed_request())
        status, _, body = await render_response(response, request.scope)

        self.assertEqual(status, 503)
        self.assertEqual(body, b"application unavailable\n")
        self.assertTrue(transport.cancelled)

    async def test_malformed_buffered_response_fails_before_delivery(self) -> None:
        transport = StaticHttpTransport(
            headers=((b"content-length", b"6"),),
            response_chunks=(b"short",),
        )
        proxy = BoundedApplicationProxy(transport, None)
        request = starlette_request(())

        response = await proxy.forward_http(request, routed_request())
        status, _, body = await render_response(response, request.scope)

        self.assertEqual(status, 502)
        self.assertEqual(body, b"application response invalid\n")
        self.assertEqual(transport.close_count, 1)

    async def test_stream_capacity_rejects_without_selecting_another_target(self) -> None:
        transport = StaticHttpTransport(
            headers=((b"content-type", b"text/event-stream"),),
            response_chunks=(b"event",),
        )
        proxy = BoundedApplicationProxy(
            transport,
            None,
            limits=replace(ProxyLimits(), streams=1, client_streams=1),
        )
        first_request = starlette_request(())
        first_request.scope["state"]["comfforts_trusted_client_key"] = "client-a"
        second_request = starlette_request(())
        second_request.scope["state"]["comfforts_trusted_client_key"] = "client-a"

        first_response = await proxy.forward_http(
            first_request,
            routed_request(),
        )
        second_response = await proxy.forward_http(
            second_request,
            routed_request(),
        )
        second_status, _, second_body = await render_response(
            second_response,
            second_request.scope,
        )
        await render_response(first_response, first_request.scope)

        self.assertEqual(second_status, 429)
        self.assertEqual(second_body, b"stream limited\n")
        self.assertEqual(len(transport.requests), 2)


class FakeUpstreamWebSocket:
    def __init__(self, incoming: tuple[str | bytes, ...]) -> None:
        self.subprotocol = "chat"
        self._incoming: asyncio.Queue[str | bytes] = asyncio.Queue()
        for item in incoming:
            self._incoming.put_nowait(item)
        self.sent: list[str | bytes] = []
        self.close_codes: list[int] = []

    async def recv(self) -> str | bytes:
        return await self._incoming.get()

    async def send(self, message: str | bytes) -> None:
        self.sent.append(message)

    async def close(self, code: int = 1000, reason: str = "") -> None:
        del reason
        self.close_codes.append(code)


class FakeWebSocketConnector:
    def __init__(self, upstream: FakeUpstreamWebSocket) -> None:
        self.upstream = upstream
        self.requests: list[UpstreamWebSocketRequest] = []
        self.exit_count = 0

    @asynccontextmanager
    async def connect(self, request: UpstreamWebSocketRequest) -> Any:
        self.requests.append(request)
        try:
            yield self.upstream
        finally:
            self.exit_count += 1


class WebSocketBridgeTest(unittest.IsolatedAsyncioTestCase):
    async def test_bridge_preserves_subprotocol_and_bidirectional_messages(self) -> None:
        incoming_count = 0

        async def receive() -> dict[str, Any]:
            nonlocal incoming_count
            incoming_count += 1
            if incoming_count == 1:
                return {"type": "websocket.connect"}
            if incoming_count == 2:
                return {"type": "websocket.receive", "text": "from-visitor"}
            await asyncio.sleep(0.02)
            return {"type": "websocket.disconnect", "code": 1000}

        outgoing: list[dict[str, Any]] = []

        async def send(message: dict[str, Any]) -> None:
            outgoing.append(message)

        scope = request_scope(
            scope_type="websocket",
            headers=((b"x-comfforts-verified-identity", b"forged"),),
        )
        websocket = WebSocket(scope, receive, send)
        upstream = FakeUpstreamWebSocket(("from-application",))
        connector = FakeWebSocketConnector(upstream)
        proxy = BoundedApplicationProxy(StaticHttpTransport(), connector)

        await proxy.forward_websocket(websocket, routed_request())

        self.assertEqual(outgoing[0]["type"], "websocket.accept")
        self.assertEqual(outgoing[0]["subprotocol"], "chat")
        self.assertIn(
            {"type": "websocket.send", "text": "from-application"},
            outgoing,
        )
        self.assertEqual(upstream.sent, ["from-visitor"])
        self.assertTrue(upstream.close_codes)
        self.assertEqual(connector.exit_count, 1)
        forwarded_headers = connector.requests[0].headers
        self.assertNotIn(
            (b"x-comfforts-verified-identity", b"forged"),
            forwarded_headers,
        )
        self.assertIn(
            (
                b"x-comfforts-verified-identity",
                b"signed.application.assertion",
            ),
            forwarded_headers,
        )

    async def test_oversized_websocket_message_closes_with_1009(self) -> None:
        incoming_count = 0

        async def receive() -> dict[str, Any]:
            nonlocal incoming_count
            incoming_count += 1
            if incoming_count == 1:
                return {"type": "websocket.connect"}
            return {"type": "websocket.receive", "bytes": b"123456"}

        outgoing: list[dict[str, Any]] = []

        async def send(message: dict[str, Any]) -> None:
            outgoing.append(message)

        websocket = WebSocket(request_scope(scope_type="websocket"), receive, send)
        upstream = FakeUpstreamWebSocket(())
        connector = FakeWebSocketConnector(upstream)
        proxy = BoundedApplicationProxy(
            StaticHttpTransport(),
            connector,
            limits=replace(ProxyLimits(), websocket_message_bytes=5),
        )

        await proxy.forward_websocket(websocket, routed_request())

        self.assertEqual(upstream.sent, [])
        self.assertIn(1009, upstream.close_codes)
        self.assertTrue(
            any(
                message["type"] == "websocket.close" and message["code"] == 1009
                for message in outgoing
            )
        )

    async def test_websocket_message_rate_limit_closes_with_4429(self) -> None:
        incoming_count = 0

        async def receive() -> dict[str, Any]:
            nonlocal incoming_count
            incoming_count += 1
            if incoming_count == 1:
                return {"type": "websocket.connect"}
            return {"type": "websocket.receive", "text": f"message-{incoming_count}"}

        outgoing: list[dict[str, Any]] = []

        async def send(message: dict[str, Any]) -> None:
            outgoing.append(message)

        websocket = WebSocket(request_scope(scope_type="websocket"), receive, send)
        upstream = FakeUpstreamWebSocket(())
        connector = FakeWebSocketConnector(upstream)
        proxy = BoundedApplicationProxy(
            StaticHttpTransport(),
            connector,
            limits=replace(
                ProxyLimits(),
                websocket_message_burst=1,
                websocket_messages_per_second=1,
            ),
            clock=FixedClock(),
        )

        await proxy.forward_websocket(websocket, routed_request())

        self.assertEqual(upstream.sent, ["message-2"])
        self.assertIn(4429, upstream.close_codes)
        self.assertTrue(
            any(
                message["type"] == "websocket.close" and message["code"] == 4429
                for message in outgoing
            )
        )

    async def test_websocket_absolute_timeout_cancels_both_directions(self) -> None:
        incoming_count = 0

        async def receive() -> dict[str, Any]:
            nonlocal incoming_count
            incoming_count += 1
            if incoming_count == 1:
                return {"type": "websocket.connect"}
            await asyncio.sleep(60)
            raise AssertionError("visitor receive unexpectedly completed")

        outgoing: list[dict[str, Any]] = []

        async def send(message: dict[str, Any]) -> None:
            outgoing.append(message)

        websocket = WebSocket(request_scope(scope_type="websocket"), receive, send)
        upstream = FakeUpstreamWebSocket(())
        connector = FakeWebSocketConnector(upstream)
        proxy = BoundedApplicationProxy(
            StaticHttpTransport(),
            connector,
            limits=replace(
                ProxyLimits(),
                stream_idle_timeout_seconds=1,
                stream_absolute_timeout_seconds=0.01,
            ),
        )

        await proxy.forward_websocket(websocket, routed_request())

        self.assertIn(1013, upstream.close_codes)
        self.assertTrue(
            any(
                message["type"] == "websocket.close" and message["code"] == 1013
                for message in outgoing
            )
        )


if __name__ == "__main__":
    unittest.main()
