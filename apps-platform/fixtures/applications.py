"""Independent deterministic applications used for platform qualification."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from .identity import (
    VERIFIED_IDENTITY_HEADER,
    FixtureIdentityVerifier,
    SyntheticIdentity,
)
from .reference_edge import Attachment, Request, Response


FIXTURE_IDENTITY_ISSUER = "urn:comfforts:identity:fixture"
AUTHENTICATED_AUDIENCE = (
    "urn:comfforts:app-platform:audience:fixture-authenticated"
)
RESTRICTED_AUDIENCE = "urn:comfforts:app-platform:audience:fixture-restricted"
PREMIUM_ENTITLEMENT = "synthetic-premium-market-data"


@dataclass(frozen=True, slots=True)
class FixtureApplicationStateSnapshot:
    """Redacted observable state used to prove fixture isolation."""

    application_id: str
    handled_requests: int
    feature_denials: int
    principal_count: int
    principal_fingerprints: tuple[str, ...]


class FixtureApplicationState:
    """Mutable synthetic state exclusively owned by one Fixture Application."""

    __slots__ = (
        "_application_id",
        "_entitlements",
        "_feature_denials",
        "_handled_requests",
        "_principals",
    )

    def __init__(self, application_id: str) -> None:
        self._application_id = application_id
        self._handled_requests = 0
        self._feature_denials = 0
        self._principals: dict[tuple[str, str], str] = {}
        self._entitlements: dict[str, frozenset[str]] = {}

    @property
    def application_id(self) -> str:
        return self._application_id

    def record_anonymous_request(self) -> None:
        self._handled_requests += 1

    def record_verified_request(self, identity: SyntheticIdentity) -> str:
        identity_key = (identity.issuer, identity.subject)
        principal = self._principals.get(identity_key)
        if principal is None:
            principal = _application_principal(
                self.application_id, identity.issuer, identity.subject
            )
            self._principals[identity_key] = principal
            self._entitlements[principal] = frozenset()
        self._handled_requests += 1
        return principal

    def has_entitlement(self, principal: str, entitlement: str) -> bool:
        return entitlement in self._entitlements.get(principal, frozenset())

    def record_feature_denial(self) -> None:
        self._feature_denials += 1

    def snapshot(self) -> FixtureApplicationStateSnapshot:
        fingerprints = tuple(
            sorted(
                hashlib.sha256(principal.encode("utf-8")).hexdigest()
                for principal in self._principals.values()
            )
        )
        return FixtureApplicationStateSnapshot(
            application_id=self.application_id,
            handled_requests=self._handled_requests,
            feature_denials=self._feature_denials,
            principal_count=len(self._principals),
            principal_fingerprints=fingerprints,
        )


@dataclass(frozen=True, slots=True)
class FixtureApplicationSet:
    """Application-owned fixture attachments and separately retained state."""

    attachments: Mapping[str, Attachment]
    states: Mapping[str, FixtureApplicationState]


class _PublicFixtureApplication:
    def __init__(self, state: FixtureApplicationState) -> None:
        self._state = state

    def web(self, request: Request) -> Response:
        self._state.record_anonymous_request()
        return _text_response(200, "fixture-public-web", "public fixture")

    def api(self, request: Request) -> Response:
        self._state.record_anonymous_request()
        return _text_response(200, "fixture-public-api", "public fixture api")


class _ProtectedFixtureApplication:
    def __init__(
        self,
        state: FixtureApplicationState,
        verifier: FixtureIdentityVerifier,
        *,
        enforce_premium_entitlement: bool,
    ) -> None:
        self._state = state
        self._verifier = verifier
        self._enforce_premium_entitlement = enforce_premium_entitlement

    def __call__(self, request: Request) -> Response:
        assertion = _single_identity_assertion(request.headers)
        verification = self._verifier.verify(assertion)
        if not verification.accepted or verification.identity is None:
            return _text_response(401, "fixture-identity-denied", "identity denied")
        identity = SyntheticIdentity(
            verification.identity.issuer, verification.identity.subject
        )
        principal = self._state.record_verified_request(identity)
        if request.path == "/":
            return _text_response(200, "fixture-unrestricted", "unrestricted fixture")
        if request.path == "/premium" and self._enforce_premium_entitlement:
            if not self._state.has_entitlement(principal, PREMIUM_ENTITLEMENT):
                self._state.record_feature_denial()
                return _text_response(403, "fixture-feature-denied", "feature denied")
            return _text_response(200, "fixture-feature", "premium fixture")
        return _text_response(404, "fixture-path-closed", "not found")


def build_fixture_applications(
    key: bytes, clock: Callable[[], int]
) -> FixtureApplicationSet:
    """Construct the exact three fixtures with independent state and verifiers."""

    public_state = FixtureApplicationState("fixture-public")
    authenticated_state = FixtureApplicationState("fixture-authenticated")
    restricted_state = FixtureApplicationState("fixture-restricted")

    public = _PublicFixtureApplication(public_state)
    authenticated = _ProtectedFixtureApplication(
        authenticated_state,
        FixtureIdentityVerifier(
            key,
            FIXTURE_IDENTITY_ISSUER,
            AUTHENTICATED_AUDIENCE,
            clock,
        ),
        enforce_premium_entitlement=False,
    )
    restricted = _ProtectedFixtureApplication(
        restricted_state,
        FixtureIdentityVerifier(
            key,
            FIXTURE_IDENTITY_ISSUER,
            RESTRICTED_AUDIENCE,
            clock,
        ),
        enforce_premium_entitlement=True,
    )

    attachments: dict[str, Attachment] = {
        "urn:comfforts:app-platform:fixture:fixture-public:web": public.web,
        "urn:comfforts:app-platform:fixture:fixture-public:api": public.api,
        "urn:comfforts:app-platform:fixture:fixture-authenticated:web": authenticated,
        "urn:comfforts:app-platform:fixture:fixture-restricted:web": restricted,
    }
    states = {
        "fixture-public": public_state,
        "fixture-authenticated": authenticated_state,
        "fixture-restricted": restricted_state,
    }
    return FixtureApplicationSet(
        attachments=MappingProxyType(attachments),
        states=MappingProxyType(states),
    )


def _application_principal(application_id: str, issuer: str, subject: str) -> str:
    value = f"{application_id}\x00{issuer}\x00{subject}".encode("utf-8")
    return f"{application_id}:principal:{hashlib.sha256(value).hexdigest()}"


def _single_identity_assertion(headers: tuple[tuple[str, str], ...]) -> str | None:
    values = [
        value
        for name, value in headers
        if name.lower() == VERIFIED_IDENTITY_HEADER.lower()
    ]
    return values[0] if len(values) == 1 else None


def _text_response(status: int, outcome: str, text: str) -> Response:
    return Response(
        status=status,
        outcome=outcome,
        headers=(("Content-Type", "text/plain; charset=utf-8"),),
        body=f"{text}\n".encode("utf-8"),
    )
