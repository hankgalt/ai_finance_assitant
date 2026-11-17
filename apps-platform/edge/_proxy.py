"""Bounded HTTP and WebSocket forwarding for resolved application targets."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable, Mapping
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
import re
import time
from typing import Any, Protocol
from urllib.parse import quote

import httpx
from google.oauth2 import id_token as google_id_token
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response, StreamingResponse
from starlette.websockets import WebSocket, WebSocketDisconnect
from websockets.asyncio.client import connect as websocket_connect
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK

from ._observability import correlation_id, record_outcome
from ._routing import RoutedApplicationRequest


MAX_METHOD_BYTES = 16
MAX_PATH_BYTES = 4_096
MAX_QUERY_BYTES = 8_192
MAX_HEADERS = 64
MAX_HEADER_NAME_BYTES = 128
MAX_HEADER_VALUE_BYTES = 8_192
MAX_HEADER_BYTES = 32_768
MAX_REQUEST_BODY_BYTES = 25 * 1_024 * 1_024
MAX_BUFFERED_RESPONSE_BYTES = 25 * 1_024 * 1_024
MAX_STREAM_BYTES = 100 * 1_024 * 1_024
MAX_WEBSOCKET_MESSAGE_BYTES = 1 * 1_024 * 1_024
CONNECT_TIMEOUT_SECONDS = 10.0
REQUEST_TIMEOUT_SECONDS = 300.0
STREAM_IDLE_TIMEOUT_SECONDS = 300.0
STREAM_ABSOLUTE_TIMEOUT_SECONDS = 55.0 * 60.0
MAX_ACTIVE_REQUESTS = 20
MAX_STREAMS = 10
MAX_CLIENT_STREAMS = 4
CLIENT_REQUESTS_PER_MINUTE = 120.0
CLIENT_REQUEST_BURST = 40.0
LOGIN_STARTS_PER_TEN_MINUTES = 10.0
LOGIN_START_BURST = 10.0
INSTANCE_REQUESTS_PER_MINUTE = 600.0
INSTANCE_REQUEST_BURST = 100.0
WEBSOCKET_MESSAGES_PER_SECOND = 20.0
WEBSOCKET_MESSAGE_BURST = 40.0
CLIENT_BUCKET_RETENTION_SECONDS = 10.0 * 60.0
MAX_CLIENT_BUCKETS = 4_096

IDENTITY_HEADER = b"x-comfforts-verified-identity"
CORRELATION_HEADER = b"x-comfforts-correlation-id"
PLATFORM_COOKIES = {
    b"__Host-comfforts-session",
    b"__Host-comfforts-oidc",
}
HOP_BY_HOP_HEADERS = {
    b"connection",
    b"keep-alive",
    b"proxy-authenticate",
    b"proxy-authorization",
    b"te",
    b"trailer",
    b"transfer-encoding",
    b"upgrade",
}
REQUEST_MANAGED_HEADERS = {
    b"authorization",
    b"host",
    CORRELATION_HEADER,
    IDENTITY_HEADER,
}
SECURITY_SENSITIVE_HEADERS = {
    b"authorization",
    b"content-length",
    b"cookie",
    b"host",
    b"transfer-encoding",
    IDENTITY_HEADER,
}
_HEADER_NAME_PATTERN = re.compile(rb"[!#$%&'*+.^_`|~0-9a-z-]+")
_CLIENT_KEY_PATTERN = re.compile(r"[A-Za-z0-9._:-]{1,128}")
_TOKEN_PATTERN = re.compile(r"[!-~]{20,8192}")
_SUBPROTOCOL_PATTERN = re.compile(r"[!#$%&'*+.^_`|~0-9A-Za-z-]{1,128}")


class ProxyUnavailable(RuntimeError):
    """A proxy dependency failed without a safe visitor-facing detail."""


class RequestBodyTooLarge(RuntimeError):
    """A streamed request crossed the approved body limit."""


class ResponseInvalid(RuntimeError):
    """An upstream response crossed a protocol or size boundary."""


@dataclass(frozen=True, slots=True)
class ProxyLimits:
    """One qualification profile; values may be lowered but never raised."""

    request_body_bytes: int = MAX_REQUEST_BODY_BYTES
    buffered_response_bytes: int = MAX_BUFFERED_RESPONSE_BYTES
    stream_bytes: int = MAX_STREAM_BYTES
    websocket_message_bytes: int = MAX_WEBSOCKET_MESSAGE_BYTES
    connect_timeout_seconds: float = CONNECT_TIMEOUT_SECONDS
    request_timeout_seconds: float = REQUEST_TIMEOUT_SECONDS
    stream_idle_timeout_seconds: float = STREAM_IDLE_TIMEOUT_SECONDS
    stream_absolute_timeout_seconds: float = STREAM_ABSOLUTE_TIMEOUT_SECONDS
    active_requests: int = MAX_ACTIVE_REQUESTS
    streams: int = MAX_STREAMS
    client_streams: int = MAX_CLIENT_STREAMS
    client_requests_per_minute: float = CLIENT_REQUESTS_PER_MINUTE
    client_request_burst: float = CLIENT_REQUEST_BURST
    login_starts_per_ten_minutes: float = LOGIN_STARTS_PER_TEN_MINUTES
    login_start_burst: float = LOGIN_START_BURST
    instance_requests_per_minute: float = INSTANCE_REQUESTS_PER_MINUTE
    instance_request_burst: float = INSTANCE_REQUEST_BURST
    websocket_messages_per_second: float = WEBSOCKET_MESSAGES_PER_SECOND
    websocket_message_burst: float = WEBSOCKET_MESSAGE_BURST

    def __post_init__(self) -> None:
        maxima = {
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
        integer_limits = {
            "request_body_bytes",
            "buffered_response_bytes",
            "stream_bytes",
            "websocket_message_bytes",
            "active_requests",
            "streams",
            "client_streams",
        }
        for name, maximum in maxima.items():
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or (name in integer_limits and not isinstance(value, int))
                or value <= 0
                or value > maximum
            ):
                raise ValueError(f"proxy limit exceeds qualification profile: {name}")


class MonotonicClock(Protocol):
    def now(self) -> float: ...


class SystemMonotonicClock:
    def now(self) -> float:
        return time.monotonic()


class TrustedClientClassifier(Protocol):
    def classify(self, scope: Mapping[str, Any]) -> str | None: ...


class ScopeTrustedClientClassifier:
    """Read only server-authenticated client metadata from an ASGI extension."""

    def classify(self, scope: Mapping[str, Any]) -> str | None:
        extensions = scope.get("extensions")
        if not isinstance(extensions, Mapping):
            return None
        metadata = extensions.get("comfforts.trusted_client")
        if not isinstance(metadata, Mapping):
            return None
        key = metadata.get("key")
        return (
            key
            if isinstance(key, str) and _CLIENT_KEY_PATTERN.fullmatch(key)
            else None
        )


@dataclass(slots=True)
class _TokenBucket:
    tokens: float
    updated_at: float

    def take(self, now: float, *, capacity: float, refill_per_second: float) -> bool:
        elapsed = max(0.0, now - self.updated_at)
        self.tokens = min(capacity, self.tokens + elapsed * refill_per_second)
        self.updated_at = now
        if self.tokens < 1.0:
            return False
        self.tokens -= 1.0
        return True


class _RequestLease:
    def __init__(self, gate: RequestGate) -> None:
        self._gate = gate
        self._released = False

    async def release(self) -> None:
        if not self._released:
            self._released = True
            await self._gate.release()


class RequestGate:
    """Per-process request rate and active-work guard."""

    def __init__(
        self,
        limits: ProxyLimits,
        clock: MonotonicClock,
    ) -> None:
        self._limits = limits
        self._clock = clock
        now = clock.now()
        self._instance = _TokenBucket(limits.instance_request_burst, now)
        self._clients: dict[str, _TokenBucket] = {}
        self._logins: dict[str, _TokenBucket] = {}
        self._last_seen: dict[str, float] = {}
        self._active = 0
        self._lock = asyncio.Lock()

    def _prune(self, now: float) -> None:
        expired = [
            key
            for key, seen_at in self._last_seen.items()
            if now - seen_at > CLIENT_BUCKET_RETENTION_SECONDS
        ]
        for key in expired:
            self._last_seen.pop(key, None)
            self._clients.pop(key, None)
            self._logins.pop(key, None)
        if len(self._last_seen) <= MAX_CLIENT_BUCKETS:
            return
        oldest = sorted(self._last_seen, key=self._last_seen.__getitem__)[
            : len(self._last_seen) - MAX_CLIENT_BUCKETS
        ]
        for key in oldest:
            self._last_seen.pop(key, None)
            self._clients.pop(key, None)
            self._logins.pop(key, None)

    async def acquire(
        self,
        client_key: str | None,
        *,
        login_start: bool,
    ) -> _RequestLease | None:
        async with self._lock:
            now = self._clock.now()
            self._prune(now)
            if not self._instance.take(
                now,
                capacity=self._limits.instance_request_burst,
                refill_per_second=(
                    self._limits.instance_requests_per_minute / 60.0
                ),
            ):
                return None
            if client_key is not None:
                self._last_seen[client_key] = now
                bucket = self._clients.setdefault(
                    client_key,
                    _TokenBucket(self._limits.client_request_burst, now),
                )
                if not bucket.take(
                    now,
                    capacity=self._limits.client_request_burst,
                    refill_per_second=(
                        self._limits.client_requests_per_minute / 60.0
                    ),
                ):
                    return None
                if login_start:
                    login_bucket = self._logins.setdefault(
                        client_key,
                        _TokenBucket(self._limits.login_start_burst, now),
                    )
                    if not login_bucket.take(
                        now,
                        capacity=self._limits.login_start_burst,
                        refill_per_second=(
                            self._limits.login_starts_per_ten_minutes / 600.0
                        ),
                    ):
                        return None
            if self._active >= self._limits.active_requests:
                return None
            self._active += 1
            return _RequestLease(self)

    async def release(self) -> None:
        async with self._lock:
            self._active = max(0, self._active - 1)


def validate_request_scope(scope: Mapping[str, Any]) -> tuple[int, str] | None:
    """Validate the bounded HTTP/WebSocket envelope before route selection."""

    scope_type = scope.get("type")
    if scope_type not in {"http", "websocket"}:
        return None
    method = scope.get("method", "GET" if scope_type == "websocket" else None)
    if not isinstance(method, str):
        return 400, "invalid request"
    try:
        method_bytes = method.encode("ascii")
    except UnicodeEncodeError:
        return 400, "invalid request"
    if (
        not 1 <= len(method_bytes) <= MAX_METHOD_BYTES
        or _HEADER_NAME_PATTERN.fullmatch(method_bytes.lower()) is None
    ):
        return 400, "invalid request"
    raw_path = scope.get("raw_path")
    if not isinstance(raw_path, bytes) or not 1 <= len(raw_path) <= MAX_PATH_BYTES:
        return 400, "invalid request"
    query = scope.get("query_string", b"")
    if not isinstance(query, bytes) or len(query) > MAX_QUERY_BYTES:
        return 400, "invalid request"
    if any(byte < 0x20 or byte > 0x7E for byte in query):
        return 400, "invalid request"
    headers = scope.get("headers", ())
    if not isinstance(headers, (list, tuple)) or len(headers) > MAX_HEADERS:
        return 400, "invalid request"
    counts: dict[bytes, int] = {}
    values: dict[bytes, list[bytes]] = {}
    aggregate = 0
    for pair in headers:
        if (
            not isinstance(pair, (list, tuple))
            or len(pair) != 2
            or not isinstance(pair[0], bytes)
            or not isinstance(pair[1], bytes)
        ):
            return 400, "invalid request"
        name, value = pair
        if (
            not 1 <= len(name) <= MAX_HEADER_NAME_BYTES
            or name != name.lower()
            or _HEADER_NAME_PATTERN.fullmatch(name) is None
            or len(value) > MAX_HEADER_VALUE_BYTES
            or any(byte in {0, 10, 13, 127} for byte in value)
        ):
            return 400, "invalid request"
        aggregate += len(name) + len(value) + 4
        counts[name] = counts.get(name, 0) + 1
        values.setdefault(name, []).append(value)
    if aggregate > MAX_HEADER_BYTES:
        return 400, "invalid request"
    if any(counts.get(name, 0) > 1 for name in SECURITY_SENSITIVE_HEADERS):
        return 400, "invalid request"
    content_length = values.get(b"content-length", [])
    transfer_encoding = values.get(b"transfer-encoding", [])
    if content_length and transfer_encoding:
        return 400, "invalid request"
    if content_length:
        raw_length = content_length[0]
        if not raw_length or not raw_length.isdigit():
            return 400, "invalid request"
        if int(raw_length) > MAX_REQUEST_BODY_BYTES:
            return 413, "request too large"
    if transfer_encoding and transfer_encoding[0].lower() != b"chunked":
        return 400, "invalid request"
    return None


async def _send_closed_http(
    send: Callable[[dict[str, Any]], Awaitable[None]],
    status: int,
    message: str,
) -> None:
    body = f"{message}\n".encode("ascii")
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"cache-control", b"no-store"),
                (b"content-length", str(len(body)).encode("ascii")),
                (b"content-type", b"text/plain; charset=utf-8"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


class RuntimeLimitMiddleware:
    """Apply envelope, rate, and active-request limits around the entire ASGI app."""

    def __init__(
        self,
        app: Callable[..., Awaitable[None]],
        *,
        limits: ProxyLimits,
        clock: MonotonicClock,
        classifier: TrustedClientClassifier | None,
    ) -> None:
        self._app = app
        self._gate = RequestGate(limits, clock)
        self._classifier = classifier

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        if scope.get("type") not in {"http", "websocket"}:
            await self._app(scope, receive, send)
            return
        violation = validate_request_scope(scope)
        if violation is not None:
            status, message = violation
            if scope["type"] == "http":
                await _send_closed_http(send, status, message)
            else:
                await send(
                    {
                        "type": "websocket.close",
                        "code": 1009 if status == 413 else 4400,
                        "reason": message,
                    }
                )
            return
        client_key: str | None = None
        if self._classifier is not None:
            try:
                client_key = self._classifier.classify(scope)
            except Exception:
                client_key = None
        state = scope.setdefault("state", {})
        if isinstance(state, dict):
            state["comfforts_trusted_client_key"] = client_key
        lease = await self._gate.acquire(
            client_key,
            login_start=scope.get("path") == "/_platform/login",
        )
        if lease is None:
            if scope["type"] == "http":
                await _send_closed_http(send, 429, "request limited")
            else:
                await send(
                    {
                        "type": "websocket.close",
                        "code": 4429,
                        "reason": "request limited",
                    }
                )
            return
        try:
            await self._app(scope, receive, send)
        finally:
            await lease.release()


class ServiceIdentityTokenSource(Protocol):
    async def token(self, audience: str) -> str: ...


class GoogleAuthServiceIdentityTokenSource:
    """Fetch a Cloud Run workload ID token through an injected google-auth request."""

    def __init__(self, auth_request: Any) -> None:
        self._auth_request = auth_request

    async def token(self, audience: str) -> str:
        try:
            token = await asyncio.to_thread(
                google_id_token.fetch_id_token,
                self._auth_request,
                audience,
            )
        except Exception as error:
            raise ProxyUnavailable("service identity unavailable") from error
        if not isinstance(token, str) or _TOKEN_PATTERN.fullmatch(token) is None:
            raise ProxyUnavailable("service identity unavailable")
        return token


@dataclass(frozen=True, slots=True)
class UpstreamHttpRequest:
    method: str
    target_uri: str
    path: str
    query_string: bytes
    headers: tuple[tuple[bytes, bytes], ...]
    body: AsyncIterator[bytes]


@dataclass(frozen=True, slots=True)
class UpstreamHttpResponse:
    status_code: int
    headers: tuple[tuple[bytes, bytes], ...]
    body: AsyncIterator[bytes]
    close: Callable[[], Awaitable[None]]


class HttpApplicationTransport(Protocol):
    async def send(self, request: UpstreamHttpRequest) -> UpstreamHttpResponse: ...


def _target_url(
    target_uri: str,
    path: str,
    query_string: bytes,
) -> httpx.URL:
    return httpx.URL(target_uri).copy_with(
        path=path,
        query=query_string,
    )


class HttpxApplicationTransport:
    """HTTPX target transport with injected client and service identity."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        identity_tokens: ServiceIdentityTokenSource,
        *,
        limits: ProxyLimits | None = None,
    ) -> None:
        self._client = client
        self._identity_tokens = identity_tokens
        self._limits = limits or ProxyLimits()

    async def send(self, request: UpstreamHttpRequest) -> UpstreamHttpResponse:
        try:
            token = await self._identity_tokens.token(request.target_uri)
            headers = list(request.headers)
            headers.append((b"authorization", f"Bearer {token}".encode("ascii")))
            outbound = self._client.build_request(
                request.method,
                _target_url(
                    request.target_uri,
                    request.path,
                    request.query_string,
                ),
                headers=headers,
                content=request.body,
                timeout=httpx.Timeout(
                    connect=self._limits.connect_timeout_seconds,
                    read=self._limits.stream_idle_timeout_seconds,
                    write=self._limits.request_timeout_seconds,
                    pool=self._limits.connect_timeout_seconds,
                ),
            )
            response = await self._client.send(
                outbound,
                stream=True,
                follow_redirects=False,
            )
        except RequestBodyTooLarge:
            raise
        except Exception as error:
            raise ProxyUnavailable("application transport unavailable") from error
        return UpstreamHttpResponse(
            status_code=response.status_code,
            headers=tuple(response.headers.raw),
            body=response.aiter_raw(),
            close=response.aclose,
        )


@dataclass(frozen=True, slots=True)
class UpstreamWebSocketRequest:
    target_uri: str
    path: str
    query_string: bytes
    headers: tuple[tuple[bytes, bytes], ...]
    subprotocols: tuple[str, ...]


class UpstreamWebSocket(Protocol):
    subprotocol: str | None

    async def recv(self) -> str | bytes: ...

    async def send(self, message: str | bytes) -> None: ...

    async def close(self, code: int = 1000, reason: str = "") -> None: ...


class WebSocketApplicationConnector(Protocol):
    def connect(
        self,
        request: UpstreamWebSocketRequest,
    ) -> AbstractAsyncContextManager[UpstreamWebSocket]: ...


def _websocket_target(request: UpstreamWebSocketRequest) -> str:
    if request.target_uri.startswith("https://"):
        base = "wss://" + request.target_uri.removeprefix("https://")
    elif request.target_uri.startswith("http://"):
        base = "ws://" + request.target_uri.removeprefix("http://")
    else:
        raise ProxyUnavailable("application target unavailable")
    encoded_path = quote(
        request.path,
        safe="/!$&'()*+,-.:;=@_~",
        encoding="utf-8",
        errors="strict",
    )
    query = request.query_string.decode("ascii")
    return f"{base}{encoded_path}" + (f"?{query}" if query else "")


class WebsocketsApplicationConnector:
    """websockets target connector with injected identity and connection factory."""

    def __init__(
        self,
        identity_tokens: ServiceIdentityTokenSource,
        *,
        connection_factory: Callable[..., Any] = websocket_connect,
        limits: ProxyLimits | None = None,
    ) -> None:
        self._identity_tokens = identity_tokens
        self._connection_factory = connection_factory
        self._limits = limits or ProxyLimits()

    @asynccontextmanager
    async def connect(
        self,
        request: UpstreamWebSocketRequest,
    ) -> AsyncIterator[UpstreamWebSocket]:
        try:
            token = await self._identity_tokens.token(request.target_uri)
            origin: str | None = None
            headers: list[tuple[str, str]] = []
            for name, value in request.headers:
                decoded_name = name.decode("ascii")
                decoded_value = value.decode("latin-1")
                if name == b"origin":
                    origin = decoded_value
                else:
                    headers.append((decoded_name, decoded_value))
            headers.append(("authorization", f"Bearer {token}"))
            async with self._connection_factory(
                _websocket_target(request),
                additional_headers=headers,
                origin=origin,
                subprotocols=list(request.subprotocols) or None,
                compression=None,
                open_timeout=self._limits.connect_timeout_seconds,
                ping_interval=20.0,
                ping_timeout=self._limits.stream_idle_timeout_seconds,
                close_timeout=self._limits.connect_timeout_seconds,
                max_size=self._limits.websocket_message_bytes,
                max_queue=16,
                write_limit=32_768,
                user_agent_header=None,
                proxy=None,
            ) as connection:
                yield connection
        except ProxyUnavailable:
            raise
        except Exception as error:
            raise ProxyUnavailable("application WebSocket unavailable") from error


def _connection_tokens(headers: Iterable[tuple[bytes, bytes]]) -> set[bytes]:
    tokens: set[bytes] = set()
    for name, value in headers:
        if name == b"connection":
            for item in value.split(b","):
                token = item.strip().lower()
                if _HEADER_NAME_PATTERN.fullmatch(token) is not None:
                    tokens.add(token)
    return tokens


def _application_cookies(value: bytes) -> bytes | None:
    retained = []
    for item in value.split(b";"):
        name, separator, _ = item.strip().partition(b"=")
        if separator and name not in PLATFORM_COOKIES:
            retained.append(item.strip())
    return b"; ".join(retained) if retained else None


def _safe_application_set_cookie(value: bytes) -> bool:
    name, separator, _ = value.partition(b"=")
    return bool(separator and name.strip() not in PLATFORM_COOKIES)


def application_request_headers(
    headers: Iterable[tuple[bytes, bytes]],
    assertion: str | None,
    request_correlation_id: str | None = None,
) -> tuple[tuple[bytes, bytes], ...]:
    """Remove visitor-controlled transport and identity headers."""

    raw = tuple(headers)
    nominated = _connection_tokens(raw)
    result: list[tuple[bytes, bytes]] = []
    for name, value in raw:
        if (
            name in HOP_BY_HOP_HEADERS
            or name in nominated
            or name in REQUEST_MANAGED_HEADERS
            or name.startswith(b"x-forwarded-")
            or name == b"forwarded"
            or name.startswith(b"sec-websocket-")
        ):
            continue
        if name == b"cookie":
            value = _application_cookies(value) or b""
            if not value:
                continue
        result.append((name, value))
    if assertion is not None:
        result.append((IDENTITY_HEADER, assertion.encode("ascii")))
    if request_correlation_id is not None:
        result.append(
            (CORRELATION_HEADER, request_correlation_id.encode("ascii"))
        )
    return tuple(result)


def _response_headers(
    headers: Iterable[tuple[bytes, bytes]],
) -> tuple[tuple[tuple[bytes, bytes], ...], int | None, bool]:
    raw = tuple((name.lower(), value) for name, value in headers)
    if len(raw) > MAX_HEADERS:
        raise ResponseInvalid("application response invalid")
    nominated = _connection_tokens(raw)
    result: list[tuple[bytes, bytes]] = []
    content_lengths: list[bytes] = []
    event_stream = False
    aggregate = 0
    for name, value in raw:
        if (
            not name
            or len(name) > MAX_HEADER_NAME_BYTES
            or _HEADER_NAME_PATTERN.fullmatch(name) is None
            or len(value) > MAX_HEADER_VALUE_BYTES
            or any(byte in {0, 10, 13, 127} for byte in value)
        ):
            raise ResponseInvalid("application response invalid")
        aggregate += len(name) + len(value) + 4
        if name == b"content-length":
            content_lengths.append(value)
        if name == b"content-type":
            event_stream = value.split(b";", 1)[0].strip().lower() == b"text/event-stream"
        if (
            name in HOP_BY_HOP_HEADERS
            or name in nominated
            or name == IDENTITY_HEADER
            or name == b"clear-site-data"
        ):
            continue
        if name == b"set-cookie" and not _safe_application_set_cookie(value):
            continue
        result.append((name, value))
    if aggregate > MAX_HEADER_BYTES or len(content_lengths) > 1:
        raise ResponseInvalid("application response invalid")
    content_length: int | None = None
    if content_lengths:
        if not content_lengths[0] or not content_lengths[0].isdigit():
            raise ResponseInvalid("application response invalid")
        content_length = int(content_lengths[0])
    return tuple(result), content_length, event_stream


async def _bounded_request_body(
    request: Request,
    limit: int,
) -> AsyncIterator[bytes]:
    total = 0
    async for chunk in request.stream():
        if not isinstance(chunk, bytes):
            raise ProxyUnavailable("invalid request body")
        total += len(chunk)
        if total > limit:
            raise RequestBodyTooLarge("request body exceeds limit")
        if chunk:
            yield chunk


def _closed_response(status: int, message: str) -> PlainTextResponse:
    return PlainTextResponse(
        f"{message}\n",
        status_code=status,
        headers={"Cache-Control": "no-store"},
    )


async def _safe_close(response: UpstreamHttpResponse) -> None:
    try:
        await response.close()
    except Exception:
        pass


class _StreamLease:
    def __init__(self, capacity: StreamCapacity, client_key: str | None) -> None:
        self._capacity = capacity
        self._client_key = client_key
        self._released = False

    async def release(self) -> None:
        if not self._released:
            self._released = True
            await self._capacity.release(self._client_key)


class StreamCapacity:
    def __init__(self, limits: ProxyLimits) -> None:
        self._limits = limits
        self._active = 0
        self._clients: dict[str, int] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, client_key: str | None) -> _StreamLease | None:
        async with self._lock:
            if self._active >= self._limits.streams:
                return None
            if (
                client_key is not None
                and self._clients.get(client_key, 0) >= self._limits.client_streams
            ):
                return None
            self._active += 1
            if client_key is not None:
                self._clients[client_key] = self._clients.get(client_key, 0) + 1
            return _StreamLease(self, client_key)

    async def release(self, client_key: str | None) -> None:
        async with self._lock:
            self._active = max(0, self._active - 1)
            if client_key is not None:
                remaining = self._clients.get(client_key, 0) - 1
                if remaining > 0:
                    self._clients[client_key] = remaining
                else:
                    self._clients.pop(client_key, None)


class ApplicationProxy(Protocol):
    async def forward_http(
        self,
        request: Request,
        routed: RoutedApplicationRequest,
    ) -> Response: ...

    async def forward_websocket(
        self,
        websocket: WebSocket,
        routed: RoutedApplicationRequest,
    ) -> None: ...


def _client_key(scope: Mapping[str, Any]) -> str | None:
    state = scope.get("state")
    if not isinstance(state, Mapping):
        return None
    value = state.get("comfforts_trusted_client_key")
    return value if isinstance(value, str) else None


def _websocket_outcome(close_code: int) -> str:
    if close_code in {1000, 1001}:
        return "success"
    if close_code in {1002, 1009}:
        return "invalid"
    if close_code == 4429:
        return "limited"
    return "dependency_unavailable"


def _response_with_raw_headers(
    body: bytes,
    status_code: int,
    headers: tuple[tuple[bytes, bytes], ...],
) -> Response:
    response = Response(body, status_code=status_code)
    response.raw_headers = list(headers)
    return response


class BoundedApplicationProxy:
    """Forward only resolved targets while enforcing the qualification profile."""

    def __init__(
        self,
        http_transport: HttpApplicationTransport,
        websocket_connector: WebSocketApplicationConnector | None,
        *,
        limits: ProxyLimits | None = None,
        clock: MonotonicClock | None = None,
    ) -> None:
        self._limits = limits or ProxyLimits()
        self._clock = clock or SystemMonotonicClock()
        self._http_transport = http_transport
        self._websocket_connector = websocket_connector
        self._streams = StreamCapacity(self._limits)
        self._message_buckets: dict[str, _TokenBucket] = {}
        self._message_last_seen: dict[str, float] = {}
        self._message_lock = asyncio.Lock()

    async def forward_http(
        self,
        request: Request,
        routed: RoutedApplicationRequest,
    ) -> Response:
        resolved = routed.resolved_attachment
        if resolved is None:
            return _closed_response(503, "application unavailable")
        headers = application_request_headers(
            request.scope.get("headers", ()),
            routed.verified_identity_assertion,
            correlation_id(request.scope),
        )
        upstream_request = UpstreamHttpRequest(
            method=request.method,
            target_uri=resolved.target_uri,
            path=routed.path,
            query_string=routed.query_string,
            headers=headers,
            body=_bounded_request_body(request, self._limits.request_body_bytes),
        )
        started_at = asyncio.get_running_loop().time()
        try:
            upstream = await asyncio.wait_for(
                self._http_transport.send(upstream_request),
                timeout=self._limits.request_timeout_seconds,
            )
        except RequestBodyTooLarge:
            record_outcome(request.scope, "limited")
            return _closed_response(413, "request too large")
        except Exception:
            record_outcome(request.scope, "dependency_unavailable")
            return _closed_response(503, "application unavailable")
        try:
            if not 200 <= upstream.status_code <= 599:
                raise ResponseInvalid("application response invalid")
            response_headers, content_length, event_stream = _response_headers(
                upstream.headers
            )
            if content_length is not None and content_length > self._limits.stream_bytes:
                raise ResponseInvalid("application response invalid")
            streaming = (
                event_stream
                or content_length is None
                or content_length > self._limits.buffered_response_bytes
            )
            if request.method == "HEAD" or upstream.status_code in {204, 304}:
                await _safe_close(upstream)
                return _response_with_raw_headers(
                    b"",
                    upstream.status_code,
                    response_headers,
                )
            if not streaming:
                body = bytearray()
                remaining = max(
                    0.001,
                    self._limits.request_timeout_seconds
                    - (asyncio.get_running_loop().time() - started_at),
                )
                async with asyncio.timeout(remaining):
                    async for chunk in upstream.body:
                        if not isinstance(chunk, bytes):
                            raise ResponseInvalid("application response invalid")
                        body.extend(chunk)
                        if len(body) > self._limits.buffered_response_bytes:
                            raise ResponseInvalid("application response invalid")
                if content_length is not None and content_length != len(body):
                    raise ResponseInvalid("application response invalid")
                await _safe_close(upstream)
                return _response_with_raw_headers(
                    bytes(body),
                    upstream.status_code,
                    response_headers,
                )
            stream_lease = await self._streams.acquire(_client_key(request.scope))
            if stream_lease is None:
                await _safe_close(upstream)
                record_outcome(request.scope, "limited")
                return _closed_response(429, "stream limited")
        except Exception:
            await _safe_close(upstream)
            record_outcome(request.scope, "invalid")
            return _closed_response(502, "application response invalid")

        async def stream_body() -> AsyncIterator[bytes]:
            total = 0
            deadline = started_at + self._limits.stream_absolute_timeout_seconds
            iterator = upstream.body.__aiter__()
            try:
                while True:
                    remaining = deadline - asyncio.get_running_loop().time()
                    if remaining <= 0:
                        record_outcome(request.scope, "dependency_unavailable")
                        return
                    try:
                        chunk = await asyncio.wait_for(
                            anext(iterator),
                            timeout=min(
                                self._limits.stream_idle_timeout_seconds,
                                remaining,
                            ),
                        )
                    except StopAsyncIteration:
                        return
                    except TimeoutError:
                        record_outcome(request.scope, "dependency_unavailable")
                        return
                    if not isinstance(chunk, bytes):
                        record_outcome(request.scope, "invalid")
                        return
                    total += len(chunk)
                    if total > self._limits.stream_bytes:
                        record_outcome(request.scope, "limited")
                        return
                    if chunk:
                        yield chunk
            except asyncio.CancelledError:
                record_outcome(request.scope, "cancelled")
                raise
            finally:
                await _safe_close(upstream)
                await stream_lease.release()

        response = StreamingResponse(
            stream_body(),
            status_code=upstream.status_code,
        )
        response.raw_headers = list(response_headers)
        return response

    async def _message_allowed(self, key: str) -> bool:
        async with self._message_lock:
            now = self._clock.now()
            expired = [
                candidate
                for candidate, seen_at in self._message_last_seen.items()
                if now - seen_at > CLIENT_BUCKET_RETENTION_SECONDS
            ]
            for candidate in expired:
                self._message_last_seen.pop(candidate, None)
                self._message_buckets.pop(candidate, None)
            if (
                key not in self._message_buckets
                and len(self._message_buckets) >= MAX_CLIENT_BUCKETS
            ):
                oldest = min(
                    self._message_last_seen,
                    key=self._message_last_seen.__getitem__,
                )
                self._message_last_seen.pop(oldest, None)
                self._message_buckets.pop(oldest, None)
            bucket = self._message_buckets.setdefault(
                key,
                _TokenBucket(self._limits.websocket_message_burst, now),
            )
            self._message_last_seen[key] = now
            return bucket.take(
                now,
                capacity=self._limits.websocket_message_burst,
                refill_per_second=self._limits.websocket_messages_per_second,
            )

    async def forward_websocket(
        self,
        websocket: WebSocket,
        routed: RoutedApplicationRequest,
    ) -> None:
        resolved = routed.resolved_attachment
        if resolved is None or self._websocket_connector is None:
            await websocket.close(code=1013, reason="application unavailable")
            return
        client_key = _client_key(websocket.scope)
        stream_lease = await self._streams.acquire(client_key)
        if stream_lease is None:
            await websocket.close(code=4429, reason="stream limited")
            return
        request = UpstreamWebSocketRequest(
            target_uri=resolved.target_uri,
            path=routed.path,
            query_string=routed.query_string,
            headers=application_request_headers(
                websocket.scope.get("headers", ()),
                routed.verified_identity_assertion,
                correlation_id(websocket.scope),
            ),
            subprotocols=tuple(websocket.scope.get("subprotocols", ())),
        )
        if (
            len(request.subprotocols) > 16
            or any(
                not isinstance(item, str)
                or _SUBPROTOCOL_PATTERN.fullmatch(item) is None
                for item in request.subprotocols
            )
        ):
            await websocket.close(code=4400, reason="invalid request")
            await stream_lease.release()
            return
        manager = self._websocket_connector.connect(request)
        upstream: UpstreamWebSocket | None = None
        try:
            upstream = await asyncio.wait_for(
                manager.__aenter__(),
                timeout=self._limits.connect_timeout_seconds,
            )
            if (
                upstream.subprotocol is not None
                and upstream.subprotocol not in request.subprotocols
            ):
                raise ProxyUnavailable("invalid application subprotocol")
            await websocket.accept(subprotocol=upstream.subprotocol)
            total = 0
            total_lock = asyncio.Lock()
            message_key = client_key or f"connection:{id(websocket)}"

            async def count_message(message: str | bytes) -> bool:
                nonlocal total
                size = (
                    len(message.encode("utf-8"))
                    if isinstance(message, str)
                    else len(message)
                )
                if size > self._limits.websocket_message_bytes:
                    return False
                async with total_lock:
                    total += size
                    return total <= self._limits.stream_bytes

            async def visitor_to_application() -> int:
                while True:
                    try:
                        message = await asyncio.wait_for(
                            websocket.receive(),
                            timeout=self._limits.stream_idle_timeout_seconds,
                        )
                    except TimeoutError:
                        return 1013
                    if message["type"] == "websocket.disconnect":
                        return 1000
                    value: str | bytes
                    if message.get("text") is not None:
                        value = message["text"]
                    elif message.get("bytes") is not None:
                        value = message["bytes"]
                    else:
                        return 1002
                    if not await count_message(value):
                        return 1009
                    if not await self._message_allowed(message_key):
                        return 4429
                    await upstream.send(value)

            async def application_to_visitor() -> int:
                while True:
                    try:
                        value = await asyncio.wait_for(
                            upstream.recv(),
                            timeout=self._limits.stream_idle_timeout_seconds,
                        )
                    except TimeoutError:
                        return 1013
                    except ConnectionClosedOK as error:
                        return error.code if error.code in {1000, 1001} else 1000
                    except ConnectionClosedError:
                        return 1011
                    except Exception:
                        return 1011
                    if not isinstance(value, (str, bytes)):
                        return 1002
                    if not await count_message(value):
                        return 1009
                    if isinstance(value, str):
                        await websocket.send_text(value)
                    else:
                        await websocket.send_bytes(value)

            tasks = {
                asyncio.create_task(visitor_to_application()),
                asyncio.create_task(application_to_visitor()),
            }
            try:
                done, pending = await asyncio.wait_for(
                    asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED),
                    timeout=self._limits.stream_absolute_timeout_seconds,
                )
                close_code = next(iter(done)).result()
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
            except TimeoutError:
                close_code = 1013
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
            record_outcome(
                websocket.scope,
                _websocket_outcome(close_code),
            )
            await upstream.close(code=close_code)
            try:
                await websocket.close(code=close_code)
            except (RuntimeError, WebSocketDisconnect):
                pass
        except Exception:
            record_outcome(websocket.scope, "dependency_unavailable")
            if upstream is not None:
                try:
                    await upstream.close(code=1013)
                except Exception:
                    pass
            try:
                await websocket.close(code=1013, reason="application unavailable")
            except RuntimeError:
                pass
        finally:
            try:
                await manager.__aexit__(None, None, None)
            except Exception:
                pass
            if client_key is None:
                async with self._message_lock:
                    self._message_buckets.pop(f"connection:{id(websocket)}", None)
                    self._message_last_seen.pop(
                        f"connection:{id(websocket)}",
                        None,
                    )
            await stream_lease.release()
