"""Immutable Application Principal contracts."""

from __future__ import annotations

import hashlib
from enum import StrEnum
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from ai_finance_assistant.contracts.common import Identifier

IAP_ISSUER = "https://cloud.google.com/iap"
LOOPBACK_ISSUER = "urn:ai-finance-assistant:identity:loopback-development"
LOOPBACK_SUBJECT = "owner"
LOOPBACK_EMAIL = "local-owner@example.invalid"


class PrincipalRole(StrEnum):
    OWNER = "owner"
    VIEWER = "viewer"


class PrincipalStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class VerifiedIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    issuer: str = Field(min_length=1, max_length=256)
    subject: str = Field(min_length=1, max_length=256)
    email: str = Field(min_length=3, max_length=320)


class ApplicationPrincipal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    principal_id: Identifier
    issuer: str = Field(min_length=1, max_length=256)
    subject: str = Field(min_length=1, max_length=256)
    email: str = Field(min_length=3, max_length=320)
    role: PrincipalRole
    status: PrincipalStatus
    created_at: AwareDatetime
    updated_at: AwareDatetime


IdentityMode = Literal["loopback_development", "iap"]


class PrincipalView(BaseModel):
    """Browser-safe current identity; issuer and subject stay server-side."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    principal_id: Identifier
    email: str = Field(min_length=3, max_length=320)
    role: PrincipalRole
    status: PrincipalStatus
    identity_mode: IdentityMode


def derive_principal_id(issuer: str, subject: str) -> str:
    digest = hashlib.sha256(
        "\0".join(("application-principal-v1", issuer, subject)).encode()
    ).hexdigest()
    return f"principal-{digest}"


def loopback_verified_identity() -> VerifiedIdentity:
    return VerifiedIdentity(
        issuer=LOOPBACK_ISSUER,
        subject=LOOPBACK_SUBJECT,
        email=LOOPBACK_EMAIL,
    )
