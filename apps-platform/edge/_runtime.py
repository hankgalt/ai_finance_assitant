"""ASGI construction for the Shared Edge."""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
import json
import re
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response
from starlette.routing import Route, WebSocketRoute
from starlette.types import ASGIApp
from starlette.websockets import WebSocket

from ._attachments import (
    ADAPTER_KIND,
    AttachmentResolutionRequest,
    AttachmentResolver,
)
from ._generation import (
    GenerationBinding,
    GenerationLoadError,
    GenerationSource,
    LoadedGeneration,
    load_generation,
)
from ._assertions import (
    AssertionIssuer,
    JWKS_CACHE_SECONDS,
    VerificationKeySource,
    public_key_from_jwk,
)
from ._identity import (
    Clock,
    GoogleOidc,
    IdentityStore,
    IdentityUnavailable,
    LoginFlow,
    PlatformIdentity,
    PlatformSession,
    TokenSource,
)
from ._routing import (
    RouteHandoff,
    RoutedApplicationRequest,
    is_reserved_path,
    render_catalogue,
    request_path,
    route_admission_mode,
    route_admission_policy,
    routed_application_request,
    select_application_route,
)
from ._proxy import (
    ApplicationProxy,
    MonotonicClock,
    ProxyLimits,
    RuntimeLimitMiddleware,
    SystemMonotonicClock,
    TrustedClientClassifier,
)


DIGEST_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")
OPAQUE_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{20,256}")
SESSION_COOKIE = "__Host-comfforts-session"
FLOW_COOKIE = "__Host-comfforts-oidc"
LOGIN_PATH = "/_platform/login"
CALLBACK_PATH = "/_platform/auth/callback"
LOGOUT_PATH = "/_platform/logout"
SESSION_LIFETIME_SECONDS = 8 * 60 * 60
FLOW_LIFETIME_SECONDS = 10 * 60
MAX_QUERY_BYTES = 2_048


def _closed_response(status_code: int, message: str) -> PlainTextResponse:
    return PlainTextResponse(
        f"{message}\n",
        status_code=status_code,
        headers={"Cache-Control": "no-store"},
    )


@dataclass(frozen=True, slots=True)
class RuntimeConfiguration:
    """Non-secret process configuration accepted by the Shared Edge."""

    profile: Literal["qualification-v1"]
    generation_bucket: str | None = None
    generation_object: str | None = None
    generation_object_generation: int | None = None
    generation_content_digest: str | None = None
    generation_digest: str | None = None
    external_origin: str | None = None

    def __post_init__(self) -> None:
        if self.profile != "qualification-v1":
            raise ValueError(f"unsupported runtime profile: {self.profile}")
        generation_values = (
            self.generation_bucket,
            self.generation_object,
            self.generation_object_generation,
            self.generation_content_digest,
            self.generation_digest,
        )
        if any(value is not None for value in generation_values) and any(
            value is None for value in generation_values
        ):
            raise ValueError("generation binding must be complete")
        if self.generation_bucket is not None:
            if not 3 <= len(self.generation_bucket) <= 63:
                raise ValueError("generation bucket is out of bounds")
            if not 1 <= len(self.generation_object or "") <= 1_024:
                raise ValueError("generation object is out of bounds")
            if (
                isinstance(self.generation_object_generation, bool)
                or not isinstance(self.generation_object_generation, int)
                or self.generation_object_generation < 1
            ):
                raise ValueError("generation object generation is invalid")
            for digest in (self.generation_content_digest, self.generation_digest):
                if not isinstance(digest, str) or DIGEST_PATTERN.fullmatch(digest) is None:
                    raise ValueError("generation digest is invalid")
        if self.external_origin is not None:
            parsed_origin = urlsplit(self.external_origin)
            if (
                parsed_origin.scheme != "https"
                or not parsed_origin.netloc
                or parsed_origin.username is not None
                or parsed_origin.password is not None
                or parsed_origin.path not in ("", "/")
                or parsed_origin.query
                or parsed_origin.fragment
                or self.external_origin.endswith("/")
            ):
                raise ValueError("external origin must be an HTTPS origin")

    def _generation_binding(self) -> GenerationBinding | None:
        if self.generation_bucket is None:
            return None
        return GenerationBinding(
            bucket=self.generation_bucket,
            object_name=self.generation_object or "",
            object_generation=self.generation_object_generation or 0,
            content_digest=self.generation_content_digest or "",
            generation_digest=self.generation_digest or "",
        )


@dataclass(frozen=True, slots=True)
class RuntimeAdapters:
    """Injected external behavior used by the Shared Edge."""

    generation_source: GenerationSource | None = None
    attachment_resolver: AttachmentResolver | None = None
    route_handoff: RouteHandoff | None = None
    google_oidc: GoogleOidc | None = None
    identity_store: IdentityStore | None = None
    clock: Clock | None = None
    token_source: TokenSource | None = None
    assertion_issuer: AssertionIssuer | None = None
    verification_key_source: VerificationKeySource | None = None
    application_proxy: ApplicationProxy | None = None
    trusted_client_classifier: TrustedClientClassifier | None = None
    monotonic_clock: MonotonicClock | None = None
    proxy_limits: ProxyLimits | None = None


def _single_query_value(request: Request, name: str) -> str | None:
    raw_query = request.scope.get("query_string", b"")
    if not isinstance(raw_query, bytes) or len(raw_query) > MAX_QUERY_BYTES:
        return None
    try:
        pairs = parse_qsl(
            raw_query.decode("ascii"),
            keep_blank_values=True,
            strict_parsing=True,
            max_num_fields=8,
        )
    except (UnicodeDecodeError, ValueError):
        return None
    values = [value for key, value in pairs if key == name]
    return values[0] if len(values) == 1 else None


def _cookie_value(request: Request, name: str) -> str | None:
    header = request.headers.get("cookie")
    if header is None or len(header) > 4_096:
        return None
    values = []
    for item in header.split(";"):
        key, separator, value = item.strip().partition("=")
        if separator and key == name:
            values.append(value)
    if len(values) != 1 or OPAQUE_TOKEN_PATTERN.fullmatch(values[0]) is None:
        return None
    return values[0]


def _set_opaque_cookie(
    response: Response,
    name: str,
    value: str,
    max_age: int,
) -> None:
    response.set_cookie(
        name,
        value,
        max_age=max_age,
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )


def _clear_opaque_cookie(response: Response, name: str) -> None:
    response.delete_cookie(
        name,
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )


def _validated_return_to(
    configuration: dict[str, object],
    value: str,
) -> str | None:
    if len(value.encode("utf-8")) > 4_096:
        return None
    parsed = urlsplit(value)
    if (
        parsed.scheme
        or parsed.netloc
        or parsed.fragment
        or not parsed.path.startswith("/")
        or parsed.path.startswith("//")
        or len(parsed.query.encode("utf-8")) > MAX_QUERY_BYTES
        or any(ord(character) < 0x20 or ord(character) == 0x7F for character in value)
    ):
        return None
    canonical_path = request_path(
        {
            "path": parsed.path,
            "raw_path": parsed.path.encode("utf-8"),
        }
    )
    if canonical_path is None:
        return None
    if canonical_path != "/":
        if is_reserved_path(configuration, canonical_path):
            return None
        if select_application_route(configuration, canonical_path) is None:
            return None
    return value


def _identity_ready(
    runtime_configuration: RuntimeConfiguration,
    adapters: RuntimeAdapters,
) -> bool:
    return (
        runtime_configuration.external_origin is not None
        and adapters.google_oidc is not None
        and adapters.identity_store is not None
        and adapters.clock is not None
        and adapters.token_source is not None
    )


def _valid_google_authorization_url(value: str) -> bool:
    parsed = urlsplit(value)
    return (
        parsed.scheme == "https"
        and parsed.hostname == "accounts.google.com"
        and parsed.username is None
        and parsed.password is None
        and bool(parsed.query)
        and not parsed.fragment
    )


async def _session_identity(
    request: Request | WebSocket,
    adapters: RuntimeAdapters,
) -> tuple[PlatformIdentity | None, bool]:
    session_id = _cookie_value(request, SESSION_COOKIE)
    if session_id is None:
        return None, True
    if adapters.identity_store is None or adapters.clock is None:
        return None, False
    try:
        session = await adapters.identity_store.get_session(session_id)
    except IdentityUnavailable:
        return None, False
    except Exception:
        return None, False
    if session is None:
        return None, True
    if session.expires_at <= adapters.clock.now():
        try:
            await adapters.identity_store.delete_session(session_id)
        except Exception:
            pass
        return None, True
    return session.identity, True


async def _resolved_request(
    routed_request: RoutedApplicationRequest,
    adapters: RuntimeAdapters,
) -> RoutedApplicationRequest | None:
    if routed_request.adapter_kind == ADAPTER_KIND:
        if adapters.attachment_resolver is None:
            return None
        try:
            resolved_attachment = await adapters.attachment_resolver.resolve(
                AttachmentResolutionRequest(
                    adapter_kind=routed_request.adapter_kind,
                    resource_reference=routed_request.resource_reference,
                    owner_application_id=(
                        routed_request.attachment_owner_application_id
                    ),
                    audience=routed_request.identity_audience,
                )
            )
        except Exception:
            return None
        return replace(
            routed_request,
            resolved_attachment=resolved_attachment,
        )
    if routed_request.adapter_kind == "contract-test-v1":
        return routed_request
    return None


async def _asserted_request(
    routed_request: RoutedApplicationRequest,
    identity: PlatformIdentity | None,
    admission_mode: str,
    adapters: RuntimeAdapters,
) -> RoutedApplicationRequest | None:
    if identity is None:
        return routed_request
    if (
        routed_request.identity_audience is None
        or adapters.assertion_issuer is None
    ):
        return routed_request if admission_mode == "public" else None
    try:
        assertion = await adapters.assertion_issuer.issue(
            identity,
            routed_request.identity_audience,
        )
    except Exception:
        return routed_request if admission_mode == "public" else None
    return replace(
        routed_request,
        verified_identity_assertion=assertion,
    )


def create_app(
    runtime_configuration: RuntimeConfiguration,
    adapters: RuntimeAdapters,
) -> ASGIApp:
    """Create the ASGI application without opening a socket or performing I/O."""
    active_generation: LoadedGeneration | None = None

    @asynccontextmanager
    async def lifespan(_: Starlette):
        nonlocal active_generation
        binding = runtime_configuration._generation_binding()
        if binding is not None and active_generation is None:
            if adapters.generation_source is None:
                raise RuntimeError("generation startup failed: GENERATION_SOURCE_UNAVAILABLE")
            try:
                active_generation = await load_generation(
                    binding,
                    adapters.generation_source,
                )
            except GenerationLoadError as error:
                raise RuntimeError(f"generation startup failed: {error.code}") from None
        yield

    async def unavailable(request: Request) -> Response:
        if active_generation is None:
            return _closed_response(503, "platform unavailable")
        path = request_path(request.scope)
        if path is None:
            return _closed_response(400, "invalid request")
        identity_ready = _identity_ready(runtime_configuration, adapters)

        if path == LOGIN_PATH:
            if not identity_ready:
                return _closed_response(503, "identity unavailable")
            return_to = _single_query_value(request, "return_to")
            if return_to is None:
                return_to = "/"
            return_to = _validated_return_to(
                active_generation.configuration,
                return_to,
            )
            if return_to is None:
                return _closed_response(400, "invalid return location")
            assert adapters.token_source is not None
            assert adapters.clock is not None
            assert adapters.identity_store is not None
            assert adapters.google_oidc is not None
            flow_id = adapters.token_source.token(32)
            state = adapters.token_source.token(32)
            nonce = adapters.token_source.token(32)
            code_verifier = adapters.token_source.token(48)
            flow = LoginFlow(
                state=state,
                nonce=nonce,
                code_verifier=code_verifier,
                return_to=return_to,
                expires_at=adapters.clock.now() + FLOW_LIFETIME_SECONDS,
            )
            redirect_uri = f"{runtime_configuration.external_origin}{CALLBACK_PATH}"
            try:
                await adapters.identity_store.put_flow(flow_id, flow)
                provider_url = await adapters.google_oidc.authorization_url(
                    redirect_uri=redirect_uri,
                    state=state,
                    nonce=nonce,
                    code_verifier=code_verifier,
                )
                if not _valid_google_authorization_url(provider_url):
                    raise IdentityUnavailable("identity provider unavailable")
            except Exception:
                return _closed_response(503, "identity unavailable")
            response = RedirectResponse(provider_url, status_code=303)
            response.headers["Cache-Control"] = "no-store"
            _set_opaque_cookie(response, FLOW_COOKIE, flow_id, FLOW_LIFETIME_SECONDS)
            return response

        if path == CALLBACK_PATH:
            if not identity_ready:
                return _closed_response(503, "identity unavailable")
            state = _single_query_value(request, "state")
            code = _single_query_value(request, "code")
            flow_id = _cookie_value(request, FLOW_COOKIE)
            if state is None or code is None or flow_id is None:
                return _closed_response(400, "invalid identity response")
            assert adapters.identity_store is not None
            assert adapters.clock is not None
            assert adapters.google_oidc is not None
            assert adapters.token_source is not None
            try:
                flow = await adapters.identity_store.consume_flow(flow_id)
                if (
                    flow is None
                    or flow.state != state
                    or flow.expires_at <= adapters.clock.now()
                ):
                    return _closed_response(400, "invalid identity response")
                return_to = _validated_return_to(
                    active_generation.configuration,
                    flow.return_to,
                )
                if return_to is None:
                    return _closed_response(400, "invalid identity response")
                identity = await adapters.google_oidc.authenticate(
                    code=code,
                    redirect_uri=(
                        f"{runtime_configuration.external_origin}{CALLBACK_PATH}"
                    ),
                    nonce=flow.nonce,
                    code_verifier=flow.code_verifier,
                )
                session_id = adapters.token_source.token(32)
                await adapters.identity_store.put_session(
                    session_id,
                    PlatformSession(
                        identity=identity,
                        expires_at=adapters.clock.now() + SESSION_LIFETIME_SECONDS,
                    ),
                )
            except Exception:
                return _closed_response(503, "identity unavailable")
            response = RedirectResponse(return_to, status_code=303)
            response.headers["Cache-Control"] = "no-store"
            _clear_opaque_cookie(response, FLOW_COOKIE)
            _set_opaque_cookie(
                response,
                SESSION_COOKIE,
                session_id,
                SESSION_LIFETIME_SECONDS,
            )
            return response

        if path == LOGOUT_PATH:
            return_to = _single_query_value(request, "return_to")
            if return_to is None:
                return_to = "/"
            return_to = _validated_return_to(
                active_generation.configuration,
                return_to,
            )
            if return_to is None:
                return _closed_response(400, "invalid return location")
            session_id = _cookie_value(request, SESSION_COOKIE)
            if session_id is not None and adapters.identity_store is not None:
                try:
                    await adapters.identity_store.delete_session(session_id)
                except Exception:
                    return _closed_response(503, "identity unavailable")
            response = RedirectResponse(return_to, status_code=303)
            response.headers["Cache-Control"] = "no-store"
            _clear_opaque_cookie(response, SESSION_COOKIE)
            return response

        if path == "/.well-known/jwks.json":
            if adapters.verification_key_source is None:
                return _closed_response(503, "verification keys unavailable")
            try:
                keys = await adapters.verification_key_source.verification_keys()
                if not 1 <= len(keys) <= 3:
                    raise ValueError("invalid verification key set")
                key_ids: set[str] = set()
                for key in keys:
                    public_key_from_jwk(key)
                    if key["kid"] in key_ids:
                        raise ValueError("duplicate verification key identifier")
                    key_ids.add(key["kid"])
                payload = json.dumps(
                    {"keys": list(keys)},
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            except Exception:
                return _closed_response(503, "verification keys unavailable")
            return Response(
                payload,
                media_type="application/json",
                headers={"Cache-Control": f"public, max-age={JWKS_CACHE_SECONDS}"},
            )

        if path == "/":
            return HTMLResponse(
                render_catalogue(active_generation.configuration),
                headers={"Cache-Control": "no-store"},
            )
        if is_reserved_path(active_generation.configuration, path):
            return _closed_response(404, "not found")
        route = select_application_route(active_generation.configuration, path)
        if route is None:
            return _closed_response(404, "not found")
        admission_mode = route_admission_mode(
            active_generation.configuration,
            route["application_id"],
        )
        identity, identity_store_available = await _session_identity(request, adapters)
        if admission_mode != "public" and identity is None:
            if not identity_ready or not identity_store_available:
                return _closed_response(503, "identity unavailable")
            return_to = path
            raw_query = request.scope.get("query_string", b"")
            if isinstance(raw_query, bytes) and raw_query:
                try:
                    return_to += "?" + raw_query.decode("ascii")
                except UnicodeDecodeError:
                    return _closed_response(400, "invalid request")
            login_location = LOGIN_PATH + "?" + urlencode({"return_to": return_to})
            response = RedirectResponse(login_location, status_code=303)
            response.headers["Cache-Control"] = "no-store"
            return response
        if admission_mode == "restricted" and identity is not None:
            policy = route_admission_policy(
                active_generation.configuration,
                route["application_id"],
            )
            members = policy.get("members", []) if policy is not None else []
            if not any(
                member.get("issuer") == identity.issuer
                and member.get("subject") == identity.subject
                for member in members
            ):
                return _closed_response(403, "forbidden")
        routed_request = routed_application_request(
            route,
            path,
            request.scope.get("query_string", b""),
        )
        if routed_request is None:
            return _closed_response(404, "not found")
        routed_request = await _resolved_request(routed_request, adapters)
        if routed_request is None:
            return _closed_response(503, "application attachment unavailable")
        routed_request = await _asserted_request(
            routed_request,
            identity,
            admission_mode,
            adapters,
        )
        if routed_request is None:
            return _closed_response(503, "identity assertion unavailable")
        if adapters.route_handoff is not None:
            try:
                await adapters.route_handoff.dispatch(routed_request)
            except Exception:
                pass
        if (
            routed_request.resolved_attachment is not None
            and adapters.application_proxy is not None
        ):
            return await adapters.application_proxy.forward_http(
                request,
                routed_request,
            )
        return _closed_response(503, "application forwarding unavailable")

    async def websocket_application(websocket: WebSocket) -> None:
        if active_generation is None:
            await websocket.close(code=1013, reason="platform unavailable")
            return
        path = request_path(websocket.scope)
        if path is None:
            await websocket.close(code=4400, reason="invalid request")
            return
        if path == "/" or is_reserved_path(active_generation.configuration, path):
            await websocket.close(code=4404, reason="not found")
            return
        route = select_application_route(active_generation.configuration, path)
        if route is None:
            await websocket.close(code=4404, reason="not found")
            return
        admission_mode = route_admission_mode(
            active_generation.configuration,
            route["application_id"],
        )
        identity, identity_store_available = await _session_identity(
            websocket,
            adapters,
        )
        if admission_mode != "public" and identity is None:
            close_code = (
                4401
                if _identity_ready(runtime_configuration, adapters)
                and identity_store_available
                else 1013
            )
            await websocket.close(
                code=close_code,
                reason=(
                    "authentication required"
                    if close_code == 4401
                    else "identity unavailable"
                ),
            )
            return
        if admission_mode == "restricted" and identity is not None:
            policy = route_admission_policy(
                active_generation.configuration,
                route["application_id"],
            )
            members = policy.get("members", []) if policy is not None else []
            if not any(
                member.get("issuer") == identity.issuer
                and member.get("subject") == identity.subject
                for member in members
            ):
                await websocket.close(code=4403, reason="forbidden")
                return
        routed_request = routed_application_request(
            route,
            path,
            websocket.scope.get("query_string", b""),
        )
        if routed_request is None:
            await websocket.close(code=4404, reason="not found")
            return
        routed_request = await _resolved_request(routed_request, adapters)
        if routed_request is None:
            await websocket.close(code=1013, reason="application unavailable")
            return
        routed_request = await _asserted_request(
            routed_request,
            identity,
            admission_mode,
            adapters,
        )
        if routed_request is None:
            await websocket.close(code=1013, reason="identity unavailable")
            return
        if adapters.route_handoff is not None:
            try:
                await adapters.route_handoff.dispatch(routed_request)
            except Exception:
                pass
        if (
            routed_request.resolved_attachment is None
            or adapters.application_proxy is None
        ):
            await websocket.close(code=1013, reason="application unavailable")
            return
        await adapters.application_proxy.forward_websocket(
            websocket,
            routed_request,
        )

    application = Starlette(
        routes=[
            Route("/{path:path}", unavailable),
            WebSocketRoute("/{path:path}", websocket_application),
        ],
        lifespan=lifespan,
    )
    return RuntimeLimitMiddleware(
        application,
        limits=adapters.proxy_limits or ProxyLimits(),
        clock=adapters.monotonic_clock or SystemMonotonicClock(),
        classifier=adapters.trusted_client_classifier,
    )
