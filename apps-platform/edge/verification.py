"""Independent application-side verification of platform identity assertions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence
from urllib.parse import urlsplit

from contracts import load_json_bytes, validate_contract_instance

from ._assertions import (
    ASSERTION_CLOCK_SKEW_SECONDS,
    ASSERTION_LIFETIME_SECONDS,
    IDENTITY_CONTEXT_SCHEMA,
    JWKS_CACHE_SECONDS,
    KEY_ID_PATTERN,
    MAX_ASSERTION_BYTES,
    MAX_JWKS_BYTES,
    VerifiedIdentityContext,
    _canonical_json,
    _clock_value,
    _decode_segment,
    public_key_from_jwk,
    verify_es256_signature,
)
from ._identity import Clock


class JwksFetcher(Protocol):
    async def fetch(self) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class VerificationResult:
    """One fail-closed application verification result."""

    accepted: bool
    code: str
    identity: VerifiedIdentityContext | None


def _rejected(code: str) -> VerificationResult:
    return VerificationResult(False, code, None)


class InMemoryJwksFetcher:
    """Deterministic rotating JWKS fetcher for application verifier tests."""

    def __init__(self, documents: Sequence[Mapping[str, Any]]) -> None:
        if not documents:
            raise ValueError("at least one JWKS document is required")
        self._documents = tuple(
            json.loads(json.dumps(document)) for document in documents
        )
        self.fetch_count = 0
        self.available = True

    async def fetch(self) -> dict[str, Any]:
        if not self.available:
            raise RuntimeError("verification key source unavailable")
        index = min(self.fetch_count, len(self._documents) - 1)
        self.fetch_count += 1
        return json.loads(json.dumps(self._documents[index]))


class HttpJwksFetcher:
    """Fetch the platform JWKS through an injected asynchronous HTTP client."""

    def __init__(self, client: Any, jwks_url: str) -> None:
        parsed = urlsplit(jwks_url)
        if (
            parsed.scheme != "https"
            or not parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path != "/.well-known/jwks.json"
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("JWKS URL must be an exact HTTPS platform endpoint")
        self._client = client
        self._jwks_url = jwks_url

    async def fetch(self) -> dict[str, Any]:
        response = await self._client.get(self._jwks_url)
        response.raise_for_status()
        if str(response.url) != self._jwks_url:
            raise RuntimeError("verification key redirect is forbidden")
        payload = bytes(response.content)
        if len(payload) > MAX_JWKS_BYTES:
            raise RuntimeError("verification key response is too large")
        document = load_json_bytes(payload, max_bytes=MAX_JWKS_BYTES)
        if document.violations or not isinstance(document.value, dict):
            raise RuntimeError("verification key response is invalid")
        return document.value


class ApplicationIdentityVerifier:
    """Verify an assertion for exactly one application issuer and audience."""

    def __init__(
        self,
        *,
        expected_issuer: str,
        expected_audience: str,
        key_fetcher: JwksFetcher,
        clock: Clock,
    ) -> None:
        if not expected_issuer or not expected_audience:
            raise ValueError("expected issuer and audience are required")
        self._expected_issuer = expected_issuer
        self._expected_audience = expected_audience
        self._key_fetcher = key_fetcher
        self._clock = clock
        self._keys: dict[str, Any] = {}
        self._keys_fetched_at: int | None = None

    async def _refresh_keys(self, now: int) -> None:
        document = await self._key_fetcher.fetch()
        if set(document) != {"keys"} or not isinstance(document["keys"], list):
            raise ValueError("invalid JWKS document")
        if not 1 <= len(document["keys"]) <= 3:
            raise ValueError("invalid JWKS document")
        keys: dict[str, Any] = {}
        for item in document["keys"]:
            if not isinstance(item, dict):
                raise ValueError("invalid JWKS document")
            key_id = item.get("kid")
            if not isinstance(key_id, str) or key_id in keys:
                raise ValueError("invalid JWKS document")
            keys[key_id] = public_key_from_jwk(item)
        self._keys = keys
        self._keys_fetched_at = now

    async def _verification_key(self, key_id: str, now: int) -> Any | None:
        stale = (
            self._keys_fetched_at is None
            or now - self._keys_fetched_at >= JWKS_CACHE_SECONDS
        )
        if stale:
            await self._refresh_keys(now)
        key = self._keys.get(key_id)
        if key is None:
            await self._refresh_keys(now)
            key = self._keys.get(key_id)
        return key

    async def verify(self, assertion: str | None) -> VerificationResult:
        if not isinstance(assertion, str):
            return _rejected("assertion_missing" if assertion is None else "assertion_malformed")
        try:
            assertion_bytes = assertion.encode("ascii")
        except UnicodeEncodeError:
            return _rejected("assertion_malformed")
        if not assertion_bytes or len(assertion_bytes) > MAX_ASSERTION_BYTES:
            return _rejected("assertion_malformed")
        parts = assertion.split(".")
        if len(parts) != 3:
            return _rejected("assertion_malformed")
        header_bytes = _decode_segment(parts[0])
        payload_bytes = _decode_segment(parts[1])
        signature = _decode_segment(parts[2])
        if header_bytes is None or payload_bytes is None or signature is None:
            return _rejected("assertion_malformed")
        try:
            header = json.loads(header_bytes.decode("utf-8"))
            if not isinstance(header, dict) or _canonical_json(header) != header_bytes:
                return _rejected("assertion_malformed")
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
            return _rejected("assertion_malformed")
        if (
            set(header) != {"alg", "kid", "typ"}
            or header.get("alg") != "ES256"
            or header.get("typ") != "JWT"
            or not isinstance(header.get("kid"), str)
            or KEY_ID_PATTERN.fullmatch(header["kid"]) is None
        ):
            return _rejected("assertion_malformed")
        try:
            now = _clock_value(self._clock)
        except Exception:
            return _rejected("identity_clock_invalid")
        try:
            key = await self._verification_key(header["kid"], now)
        except Exception:
            return _rejected("verification_keys_unavailable")
        if key is None:
            return _rejected("assertion_key_unknown")
        signing_input = f"{parts[0]}.{parts[1]}".encode("ascii")
        if not verify_es256_signature(key, signing_input, signature):
            return _rejected("assertion_signature_invalid")
        try:
            payload = json.loads(payload_bytes.decode("utf-8"))
            if not isinstance(payload, dict) or _canonical_json(payload) != payload_bytes:
                return _rejected("identity_contract_invalid")
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
            return _rejected("identity_contract_invalid")
        if validate_contract_instance(payload, IDENTITY_CONTEXT_SCHEMA):
            return _rejected("identity_contract_invalid")
        identity = VerifiedIdentityContext(**payload)
        if identity.issuer != self._expected_issuer:
            return _rejected("identity_issuer_invalid")
        if identity.audience != self._expected_audience:
            return _rejected("identity_audience_invalid")
        if identity.issued_at > now + ASSERTION_CLOCK_SKEW_SECONDS:
            return _rejected("identity_not_yet_valid")
        if identity.expires_at + ASSERTION_CLOCK_SKEW_SECONDS < now:
            return _rejected("identity_expired")
        if identity.expires_at - identity.issued_at > ASSERTION_LIFETIME_SECONDS:
            return _rejected("identity_lifetime_invalid")
        return VerificationResult(True, "identity_verified", identity)
