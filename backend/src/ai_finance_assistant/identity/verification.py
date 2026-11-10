"""Signed Google IAP assertion verification."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import jwt

from ai_finance_assistant.identity.models import IAP_ISSUER, VerifiedIdentity

IAP_PUBLIC_JWK_URL = "https://www.gstatic.com/iap/verify/public_key-jwk"


class InvalidIAPAssertion(ValueError):
    """The assertion did not satisfy the signed IAP contract."""


class IAPAssertionVerifier:
    def __init__(
        self,
        *,
        expected_audience: str,
        signing_key_resolver: Callable[[str], Any] | None = None,
    ) -> None:
        self._expected_audience = expected_audience
        if signing_key_resolver is None:
            jwk_client = jwt.PyJWKClient(
                IAP_PUBLIC_JWK_URL,
                cache_keys=True,
                cache_jwk_set=True,
                lifespan=3600,
            )

            def resolve_signing_key(token: str) -> Any:
                return jwk_client.get_signing_key_from_jwt(token).key

            signing_key_resolver = resolve_signing_key
        self._signing_key_resolver = signing_key_resolver

    def verify(self, assertion: str) -> VerifiedIdentity:
        try:
            signing_key = self._signing_key_resolver(assertion)
            claims = jwt.decode(
                assertion,
                signing_key,
                algorithms=["ES256"],
                audience=self._expected_audience,
                issuer=IAP_ISSUER,
                leeway=30,
                options={"require": ["iss", "aud", "sub", "email", "iat", "exp"]},
            )
            return VerifiedIdentity(
                issuer=str(claims["iss"]),
                subject=str(claims["sub"]),
                email=str(claims["email"]),
            )
        except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
            raise InvalidIAPAssertion("The signed IAP assertion is invalid.") from exc
