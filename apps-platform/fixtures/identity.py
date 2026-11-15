"""Fixture-only synthetic identity issuance and independent verification."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from types import MappingProxyType
from typing import Any

from contracts.validation import load_contract_schemas, validate_contract_instance


FIXTURE_SESSION_HEADER = "X-Comfforts-Fixture-Session"
VERIFIED_IDENTITY_HEADER = "X-Comfforts-Verified-Identity"
MAX_ASSERTION_BYTES = 1_024
MAX_ASSERTION_LIFETIME_SECONDS = 60
MAX_REPLAY_ENTRIES = 256

_CONTEXT_SCHEMA = "urn:comfforts:app-platform:schema:verified-identity-context:v1"
_ENVELOPE_PREFIX = "fixture-v1"
_SESSION_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class IdentityAssertionError(ValueError):
    """Fixture identity input cannot produce a valid Version 1 assertion."""


@dataclass(frozen=True, slots=True)
class SyntheticIdentity:
    """One immutable synthetic issuer-and-subject pair."""

    issuer: str
    subject: str


@dataclass(frozen=True, slots=True)
class VerifiedIdentity:
    """The independently verified Version 1 identity claim payload."""

    contract_version: int
    issuer: str
    subject: str
    audience: str
    issued_at: int
    expires_at: int
    correlation_id: str


@dataclass(frozen=True, slots=True)
class VerificationResult:
    """One fail-closed assertion-verification result."""

    accepted: bool
    code: str
    identity: VerifiedIdentity | None


class SyntheticIdentityAdapter:
    """Resolve explicitly configured session labels to synthetic identities."""

    def __init__(self, sessions: Mapping[str, SyntheticIdentity]) -> None:
        if len(sessions) > 256:
            raise ValueError("fixture identity adapter supports at most 256 sessions")
        copied: dict[str, SyntheticIdentity] = {}
        for label, identity in sessions.items():
            if not isinstance(label, str) or not _SESSION_LABEL.fullmatch(label):
                raise ValueError("fixture session label is not canonical")
            if not isinstance(identity, SyntheticIdentity):
                raise TypeError("fixture sessions must map to SyntheticIdentity values")
            copied[label] = identity
        self._sessions = MappingProxyType(copied)

    def resolve(self, session_label: str | None) -> SyntheticIdentity | None:
        if session_label is None:
            return None
        return self._sessions.get(session_label)


class FixtureIdentitySigner:
    """Issue deterministic fixture envelopes around Version 1 identity claims."""

    def __init__(
        self,
        key: bytes,
        clock: Callable[[], int],
        correlation_ids: Callable[[], str],
    ) -> None:
        self._key = _validated_key(key)
        self._clock = clock
        self._correlation_ids = correlation_ids
        self._registry = load_contract_schemas()

    def issue(self, identity: SyntheticIdentity, audience: str) -> str:
        if not isinstance(identity, SyntheticIdentity):
            raise IdentityAssertionError("identity must be synthetic fixture data")
        issued_at = _clock_value(self._clock)
        correlation_id = self._correlation_ids()
        context = VerifiedIdentity(
            contract_version=1,
            issuer=identity.issuer,
            subject=identity.subject,
            audience=audience,
            issued_at=issued_at,
            expires_at=issued_at + MAX_ASSERTION_LIFETIME_SECONDS,
            correlation_id=correlation_id,
        )
        payload = asdict(context)
        violations = validate_contract_instance(payload, _CONTEXT_SCHEMA, self._registry)
        if violations:
            raise IdentityAssertionError("identity claim does not satisfy Version 1")
        assertion = _encode_envelope(payload, self._key)
        if len(assertion.encode("ascii")) > MAX_ASSERTION_BYTES:
            raise IdentityAssertionError("identity assertion exceeds the fixture profile")
        return assertion


class FixtureIdentityVerifier:
    """Independently verify one application audience and bounded replay history."""

    def __init__(
        self,
        key: bytes,
        expected_issuer: str,
        expected_audience: str,
        clock: Callable[[], int],
    ) -> None:
        self._key = _validated_key(key)
        self._expected_issuer = expected_issuer
        self._expected_audience = expected_audience
        self._clock = clock
        self._replay_expiry: dict[str, int] = {}
        self._registry = load_contract_schemas()

    def verify(self, assertion: str | None) -> VerificationResult:
        if assertion is None:
            return _rejected("assertion_missing")
        if not isinstance(assertion, str):
            return _rejected("assertion_malformed")
        try:
            assertion_bytes = assertion.encode("ascii")
        except UnicodeEncodeError:
            return _rejected("assertion_malformed")
        if not assertion_bytes or len(assertion_bytes) > MAX_ASSERTION_BYTES:
            return _rejected("assertion_malformed")

        parts = assertion.split(".")
        if len(parts) != 3 or parts[0] != _ENVELOPE_PREFIX:
            return _rejected("assertion_malformed")
        payload_segment, signature_segment = parts[1], parts[2]
        payload_bytes = _decode_segment(payload_segment)
        signature = _decode_segment(signature_segment)
        if payload_bytes is None or signature is None or len(signature) != 32:
            return _rejected("assertion_malformed")

        signed = f"{_ENVELOPE_PREFIX}.{payload_segment}".encode("ascii")
        expected_signature = hmac.new(self._key, signed, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected_signature):
            return _rejected("assertion_signature_invalid")

        payload = _parse_canonical_payload(payload_bytes)
        if payload is None:
            return _rejected("identity_contract_invalid")
        violations = validate_contract_instance(payload, _CONTEXT_SCHEMA, self._registry)
        if violations:
            return _rejected("identity_contract_invalid")

        identity = VerifiedIdentity(**payload)
        if identity.issuer != self._expected_issuer:
            return _rejected("identity_issuer_invalid")
        if identity.audience != self._expected_audience:
            return _rejected("identity_audience_invalid")

        try:
            now = _clock_value(self._clock)
        except IdentityAssertionError:
            return _rejected("identity_clock_invalid")
        if identity.issued_at > now:
            return _rejected("identity_not_yet_valid")
        if identity.expires_at <= now:
            return _rejected("identity_expired")
        if identity.expires_at - identity.issued_at > MAX_ASSERTION_LIFETIME_SECONDS:
            return _rejected("identity_lifetime_invalid")

        replay_code = self._consume_replay_identifier(identity, now)
        if replay_code is not None:
            return _rejected(replay_code)
        return VerificationResult(True, "identity_verified", identity)

    def _consume_replay_identifier(
        self, identity: VerifiedIdentity, now: int
    ) -> str | None:
        expired = [
            correlation_id
            for correlation_id, expires_at in self._replay_expiry.items()
            if expires_at <= now
        ]
        for correlation_id in expired:
            del self._replay_expiry[correlation_id]
        if identity.correlation_id in self._replay_expiry:
            return "identity_replayed"
        if len(self._replay_expiry) >= MAX_REPLAY_ENTRIES:
            return "replay_capacity"
        self._replay_expiry[identity.correlation_id] = identity.expires_at
        return None


def _validated_key(key: bytes) -> bytes:
    if not isinstance(key, bytes):
        raise TypeError("fixture test key material must be bytes")
    if not 1 <= len(key) <= 1_024:
        raise ValueError("fixture test key material is outside the fixture profile")
    return key


def _clock_value(clock: Callable[[], int]) -> int:
    value = clock()
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or not 0 <= value <= 253_402_300_739
    ):
        raise IdentityAssertionError("fixture clock returned an invalid timestamp")
    return value


def _canonical_payload(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _encode_segment(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode_segment(value: str) -> bytes | None:
    if not value or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        return None
    padding = "=" * (-len(value) % 4)
    try:
        decoded = base64.b64decode(
            f"{value}{padding}", altchars=b"-_", validate=True
        )
    except (binascii.Error, ValueError, TypeError):
        return None
    if _encode_segment(decoded) != value:
        return None
    return decoded


def _encode_envelope(payload: Mapping[str, Any], key: bytes) -> str:
    payload_segment = _encode_segment(_canonical_payload(payload))
    signed = f"{_ENVELOPE_PREFIX}.{payload_segment}".encode("ascii")
    signature = hmac.new(key, signed, hashlib.sha256).digest()
    return f"{_ENVELOPE_PREFIX}.{payload_segment}.{_encode_segment(signature)}"


def _parse_canonical_payload(payload_bytes: bytes) -> dict[str, Any] | None:
    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
        if not isinstance(payload, dict):
            return None
        if _canonical_payload(payload) != payload_bytes:
            return None
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        return None
    return payload


def _rejected(code: str) -> VerificationResult:
    return VerificationResult(False, code, None)
