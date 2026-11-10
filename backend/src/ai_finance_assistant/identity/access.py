"""Request identity resolution and Principal admission policy."""

from __future__ import annotations

from collections.abc import Mapping

from ai_finance_assistant.core.config import Settings
from ai_finance_assistant.identity.models import (
    ApplicationPrincipal,
    PrincipalRole,
    PrincipalStatus,
    PrincipalView,
    loopback_verified_identity,
)
from ai_finance_assistant.identity.repositories import PrincipalRepository
from ai_finance_assistant.identity.verification import (
    IAPAssertionVerifier,
    InvalidIAPAssertion,
)


class IdentityAccessError(PermissionError):
    def __init__(self, code: str, *, status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


class IdentityAccess:
    def __init__(
        self,
        settings: Settings,
        repository: PrincipalRepository,
        *,
        iap_assertion_verifier: IAPAssertionVerifier | None = None,
    ) -> None:
        self._settings = settings
        self._repository = repository
        self._viewer_emails = frozenset(settings.iap_viewer_emails)
        self._iap_verifier: IAPAssertionVerifier | None
        self._loopback_principal: ApplicationPrincipal | None
        if settings.identity_mode == "iap":
            assert settings.iap_audience is not None
            self._iap_verifier = iap_assertion_verifier or IAPAssertionVerifier(
                expected_audience=settings.iap_audience
            )
            self._loopback_principal = None
        else:
            self._iap_verifier = None
            self._loopback_principal = repository.ensure(
                loopback_verified_identity(),
                role=PrincipalRole.OWNER,
            )

    def resolve(self, headers: Mapping[str, str]) -> ApplicationPrincipal:
        if self._settings.identity_mode == "loopback_development":
            assert self._loopback_principal is not None
            principal = self._repository.get(self._loopback_principal.principal_id)
            assert principal is not None
        else:
            assertion = headers.get("x-goog-iap-jwt-assertion")
            if not assertion:
                raise IdentityAccessError("IAP_ASSERTION_REQUIRED", status_code=401)
            assert self._iap_verifier is not None
            try:
                verified = self._iap_verifier.verify(assertion)
            except InvalidIAPAssertion as exc:
                raise IdentityAccessError("IAP_ASSERTION_INVALID", status_code=401) from exc
            assert self._settings.iap_owner_email is not None
            principal = self._repository.resolve_or_admit(
                verified,
                owner_email=self._settings.iap_owner_email,
                viewer_emails=self._viewer_emails,
            )
            if principal is None:
                raise IdentityAccessError("PRINCIPAL_NOT_ADMITTED", status_code=403)
        if principal.status == PrincipalStatus.DISABLED:
            raise IdentityAccessError("PRINCIPAL_DISABLED", status_code=403)
        return principal

    def view(self, principal: ApplicationPrincipal) -> PrincipalView:
        return PrincipalView(
            principal_id=principal.principal_id,
            email=principal.email,
            role=principal.role,
            status=principal.status,
            identity_mode=self._settings.identity_mode,
        )
