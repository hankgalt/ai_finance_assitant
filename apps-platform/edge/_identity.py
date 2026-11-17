"""Google OIDC and opaque Platform Session adapters."""

from __future__ import annotations

import base64
import hashlib
import secrets
import time
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlsplit

import httpx
from authlib.integrations.httpx_client import AsyncOAuth2Client
from authlib.jose import JsonWebToken
from authlib.oidc.core import CodeIDToken


GOOGLE_DISCOVERY_URL = (
    "https://accounts.google.com/.well-known/openid-configuration"
)
GOOGLE_ISSUERS = ("https://accounts.google.com", "accounts.google.com")


class IdentityUnavailable(RuntimeError):
    """An identity dependency could not safely complete an operation."""


@dataclass(frozen=True, slots=True)
class PlatformIdentity:
    """Verified provider identity retained by the Platform Session boundary."""

    issuer: str
    subject: str
    email: str | None = None

    def __post_init__(self) -> None:
        if self.issuer not in GOOGLE_ISSUERS:
            raise ValueError("unsupported identity issuer")
        if (
            not isinstance(self.subject, str)
            or not 1 <= len(self.subject) <= 255
            or any(ord(character) < 0x20 for character in self.subject)
        ):
            raise ValueError("invalid identity subject")
        if self.email is not None and (
            not isinstance(self.email, str)
            or not 1 <= len(self.email) <= 320
            or any(ord(character) < 0x20 for character in self.email)
        ):
            raise ValueError("invalid identity display email")


@dataclass(frozen=True, slots=True)
class LoginFlow:
    """Server-side transient material for one authorization-code flow."""

    state: str
    nonce: str
    code_verifier: str
    return_to: str
    expires_at: int

    def __post_init__(self) -> None:
        if (
            not all(
                isinstance(value, str) and 1 <= len(value) <= 512
                for value in (
                    self.state,
                    self.nonce,
                    self.code_verifier,
                    self.return_to,
                )
            )
            or isinstance(self.expires_at, bool)
            or not isinstance(self.expires_at, int)
            or self.expires_at < 1
        ):
            raise ValueError("invalid login flow")


@dataclass(frozen=True, slots=True)
class PlatformSession:
    """Minimal server-side state addressed by an opaque browser cookie."""

    identity: PlatformIdentity
    expires_at: int

    def __post_init__(self) -> None:
        if (
            not isinstance(self.identity, PlatformIdentity)
            or isinstance(self.expires_at, bool)
            or not isinstance(self.expires_at, int)
            or self.expires_at < 1
        ):
            raise ValueError("invalid platform session")


class Clock(Protocol):
    def now(self) -> int: ...


class TokenSource(Protocol):
    def token(self, entropy_bytes: int) -> str: ...


class GoogleOidc(Protocol):
    async def authorization_url(
        self,
        *,
        redirect_uri: str,
        state: str,
        nonce: str,
        code_verifier: str,
    ) -> str: ...

    async def authenticate(
        self,
        *,
        code: str,
        redirect_uri: str,
        nonce: str,
        code_verifier: str,
    ) -> PlatformIdentity: ...


class IdentityStore(Protocol):
    async def put_flow(self, flow_id: str, flow: LoginFlow) -> None: ...

    async def consume_flow(self, flow_id: str) -> LoginFlow | None: ...

    async def put_session(
        self,
        session_id: str,
        session: PlatformSession,
    ) -> None: ...

    async def get_session(self, session_id: str) -> PlatformSession | None: ...

    async def delete_session(self, session_id: str) -> None: ...


class SystemClock:
    def now(self) -> int:
        return int(time.time())


class SecureTokenSource:
    def token(self, entropy_bytes: int) -> str:
        return secrets.token_urlsafe(entropy_bytes)


class InMemoryIdentityStore:
    """Deterministic test adapter; it is not a Live session store."""

    def __init__(self) -> None:
        self.flows: dict[str, LoginFlow] = {}
        self.sessions: dict[str, PlatformSession] = {}
        self.available = True

    def _require_available(self) -> None:
        if not self.available:
            raise IdentityUnavailable("identity store unavailable")

    async def put_flow(self, flow_id: str, flow: LoginFlow) -> None:
        self._require_available()
        self.flows[flow_id] = flow

    async def consume_flow(self, flow_id: str) -> LoginFlow | None:
        self._require_available()
        return self.flows.pop(flow_id, None)

    async def put_session(
        self,
        session_id: str,
        session: PlatformSession,
    ) -> None:
        self._require_available()
        self.sessions[session_id] = session

    async def get_session(self, session_id: str) -> PlatformSession | None:
        self._require_available()
        return self.sessions.get(session_id)

    async def delete_session(self, session_id: str) -> None:
        self._require_available()
        self.sessions.pop(session_id, None)


def _document_id(opaque_id: str) -> str:
    return hashlib.sha256(opaque_id.encode("ascii")).hexdigest()


class FirestoreIdentityStore:
    """Minimal opaque flow and session storage backed by Firestore Native."""

    def __init__(self, client: Any, *, collection_prefix: str = "platform") -> None:
        if not collection_prefix or "/" in collection_prefix:
            raise ValueError("invalid Firestore collection prefix")
        self._client = client
        self._flow_collection = f"{collection_prefix}-login-flows"
        self._session_collection = f"{collection_prefix}-sessions"

    def _flow_document(self, flow_id: str) -> Any:
        return self._client.collection(self._flow_collection).document(
            _document_id(flow_id)
        )

    def _session_document(self, session_id: str) -> Any:
        return self._client.collection(self._session_collection).document(
            _document_id(session_id)
        )

    async def put_flow(self, flow_id: str, flow: LoginFlow) -> None:
        try:
            await self._flow_document(flow_id).create(
                {
                    "state": flow.state,
                    "nonce": flow.nonce,
                    "code_verifier": flow.code_verifier,
                    "return_to": flow.return_to,
                    "expires_at": flow.expires_at,
                }
            )
        except Exception as error:
            raise IdentityUnavailable("identity store unavailable") from error

    async def consume_flow(self, flow_id: str) -> LoginFlow | None:
        try:
            document = self._flow_document(flow_id)
            transaction = self._client.transaction()
            snapshot = await document.get(transaction=transaction)
            if not snapshot.exists:
                await transaction.commit()
                return None
            data = snapshot.to_dict()
            transaction.delete(document)
            await transaction.commit()
            if not isinstance(data, dict):
                return None
            return LoginFlow(
                state=data["state"],
                nonce=data["nonce"],
                code_verifier=data["code_verifier"],
                return_to=data["return_to"],
                expires_at=data["expires_at"],
            )
        except Exception as error:
            raise IdentityUnavailable("identity store unavailable") from error

    async def put_session(
        self,
        session_id: str,
        session: PlatformSession,
    ) -> None:
        try:
            await self._session_document(session_id).create(
                {
                    "issuer": session.identity.issuer,
                    "subject": session.identity.subject,
                    "email": session.identity.email,
                    "expires_at": session.expires_at,
                }
            )
        except Exception as error:
            raise IdentityUnavailable("identity store unavailable") from error

    async def get_session(self, session_id: str) -> PlatformSession | None:
        try:
            snapshot = await self._session_document(session_id).get()
            if not snapshot.exists:
                return None
            data = snapshot.to_dict()
            if not isinstance(data, dict):
                return None
            return PlatformSession(
                identity=PlatformIdentity(
                    issuer=data["issuer"],
                    subject=data["subject"],
                    email=data.get("email"),
                ),
                expires_at=data["expires_at"],
            )
        except Exception as error:
            raise IdentityUnavailable("identity store unavailable") from error

    async def delete_session(self, session_id: str) -> None:
        try:
            await self._session_document(session_id).delete()
        except Exception as error:
            raise IdentityUnavailable("identity store unavailable") from error


def _pkce_challenge(code_verifier: str) -> str:
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


class AuthlibGoogleOidc:
    """Google-only OIDC adapter that discards provider tokens after validation."""

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not client_id or not client_secret:
            raise ValueError("Google OIDC client credentials are required")
        self._client_id = client_id
        self._client_secret = client_secret
        self._transport = transport

    async def _metadata(self) -> dict[str, Any]:
        async with httpx.AsyncClient(transport=self._transport) as client:
            response = await client.get(GOOGLE_DISCOVERY_URL)
            response.raise_for_status()
            metadata = response.json()
        if metadata.get("issuer") not in GOOGLE_ISSUERS:
            raise IdentityUnavailable("identity provider unavailable")
        for key in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
            value = metadata.get(key)
            if not isinstance(value, str) or urlsplit(value).scheme != "https":
                raise IdentityUnavailable("identity provider unavailable")
        return metadata

    def _client(self, redirect_uri: str) -> AsyncOAuth2Client:
        return AsyncOAuth2Client(
            client_id=self._client_id,
            client_secret=self._client_secret,
            redirect_uri=redirect_uri,
            scope="openid email",
            code_challenge_method="S256",
            transport=self._transport,
        )

    async def authorization_url(
        self,
        *,
        redirect_uri: str,
        state: str,
        nonce: str,
        code_verifier: str,
    ) -> str:
        try:
            metadata = await self._metadata()
            async with self._client(redirect_uri) as client:
                url, _ = client.create_authorization_url(
                    metadata["authorization_endpoint"],
                    state=state,
                    nonce=nonce,
                    code_verifier=code_verifier,
                    code_challenge=_pkce_challenge(code_verifier),
                    code_challenge_method="S256",
                    access_type="online",
                    prompt="select_account",
                )
            return url
        except IdentityUnavailable:
            raise
        except Exception as error:
            raise IdentityUnavailable("identity provider unavailable") from error

    async def authenticate(
        self,
        *,
        code: str,
        redirect_uri: str,
        nonce: str,
        code_verifier: str,
    ) -> PlatformIdentity:
        try:
            metadata = await self._metadata()
            async with self._client(redirect_uri) as client:
                token = await client.fetch_token(
                    metadata["token_endpoint"],
                    code=code,
                    code_verifier=code_verifier,
                )
            id_token = token.get("id_token")
            if not isinstance(id_token, str):
                raise IdentityUnavailable("identity provider unavailable")
            async with httpx.AsyncClient(transport=self._transport) as client:
                response = await client.get(metadata["jwks_uri"])
                response.raise_for_status()
                jwks = response.json()
            claims = JsonWebToken(["RS256"]).decode(
                id_token,
                jwks,
                claims_cls=CodeIDToken,
                claims_options={
                    "iss": {"values": list(GOOGLE_ISSUERS)},
                    "aud": {"value": self._client_id},
                },
                claims_params={
                    "client_id": self._client_id,
                    "nonce": nonce,
                },
            )
            claims.validate()
            issuer = claims.get("iss")
            subject = claims.get("sub")
            email = claims.get("email")
            if issuer not in GOOGLE_ISSUERS or not isinstance(subject, str) or not subject:
                raise IdentityUnavailable("identity provider unavailable")
            return PlatformIdentity(
                issuer=issuer,
                subject=subject,
                email=email if isinstance(email, str) else None,
            )
        except IdentityUnavailable:
            raise
        except Exception as error:
            raise IdentityUnavailable("identity provider unavailable") from error
