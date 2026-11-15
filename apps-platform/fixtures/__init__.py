"""Deterministic App Platform qualification fixtures."""

from .identity import (
    FIXTURE_SESSION_HEADER,
    VERIFIED_IDENTITY_HEADER,
    FixtureIdentitySigner,
    FixtureIdentityVerifier,
    IdentityAssertionError,
    SyntheticIdentity,
    SyntheticIdentityAdapter,
    VerificationResult,
    VerifiedIdentity,
)
from .reference_edge import (
    ActivationIssue,
    ActivationResult,
    ReferenceEdge,
    Request,
    Response,
)
from .applications import (
    AUTHENTICATED_AUDIENCE,
    FIXTURE_IDENTITY_ISSUER,
    PREMIUM_ENTITLEMENT,
    RESTRICTED_AUDIENCE,
    FixtureApplicationSet,
    FixtureApplicationState,
    FixtureApplicationStateSnapshot,
    build_fixture_applications,
)

__all__ = (
    "ActivationIssue",
    "ActivationResult",
    "AUTHENTICATED_AUDIENCE",
    "FIXTURE_SESSION_HEADER",
    "FIXTURE_IDENTITY_ISSUER",
    "PREMIUM_ENTITLEMENT",
    "RESTRICTED_AUDIENCE",
    "VERIFIED_IDENTITY_HEADER",
    "FixtureApplicationSet",
    "FixtureApplicationState",
    "FixtureApplicationStateSnapshot",
    "FixtureIdentitySigner",
    "FixtureIdentityVerifier",
    "IdentityAssertionError",
    "ReferenceEdge",
    "Request",
    "Response",
    "SyntheticIdentity",
    "SyntheticIdentityAdapter",
    "VerificationResult",
    "VerifiedIdentity",
    "build_fixture_applications",
)
