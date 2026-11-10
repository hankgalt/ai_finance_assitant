"""Request correlation without logging bodies, headers, or query values."""

import logging
import re
import time
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from ai_finance_assistant.contracts.api import ApiError
from ai_finance_assistant.contracts.errors import ErrorCategory, SafeError
from ai_finance_assistant.core.logging import reset_correlation_id, set_correlation_id
from ai_finance_assistant.identity.access import IdentityAccessError
from ai_finance_assistant.identity.models import ApplicationPrincipal

logger = logging.getLogger(__name__)
SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class PrincipalIdentityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path.endswith("/api/health/live"):
            return await call_next(request)
        services = getattr(request.app.state, "services", None)
        if services is None:
            return await call_next(request)
        try:
            principal = services.identity_access.resolve(request.headers)
        except IdentityAccessError as error:
            body = ApiError(
                error=SafeError(
                    code=error.code,
                    category=ErrorCategory.AUTHORIZATION,
                    message="Authenticated application access is unavailable.",
                )
            )
            return JSONResponse(
                status_code=error.status_code,
                content=body.model_dump(mode="json"),
            )
        request.state.principal = principal
        return await call_next(request)


def current_principal(request: Request) -> ApplicationPrincipal:
    principal = getattr(request.state, "principal", None)
    if not isinstance(principal, ApplicationPrincipal):
        raise RuntimeError("The request has no resolved Application Principal.")
    return principal


class RequestCorrelationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        supplied = request.headers.get("x-request-id")
        request_id = supplied if supplied and SAFE_REQUEST_ID.fullmatch(supplied) else str(uuid4())
        token = set_correlation_id(request_id)
        started = time.perf_counter()
        response_status = 500
        elapsed_ms = 0.0
        try:
            response = await call_next(request)
            response_status = response.status_code
            elapsed_ms = float(round((time.perf_counter() - started) * 1000))
            logger.info(
                "request_completed method=%s path=%s status=%s duration_ms=%s",
                request.method,
                request.url.path,
                response.status_code,
                elapsed_ms,
            )
            response.headers["x-request-id"] = request_id
            return response
        finally:
            elapsed_ms = (time.perf_counter() - started) * 1000
            services = getattr(request.app.state, "services", None)
            route = request.scope.get("route")
            base_path = request.app.state.settings.base_path
            route_path = getattr(route, "path", "unmatched")
            if request.url.path.startswith("/api/") and not route_path.startswith("/api/"):
                route_path = f"/api{route_path}"
            route_path = f"{base_path}{route_path}"
            if services is not None and not request.url.path.startswith("/api/health"):
                attributes = {
                    "http_method": request.method,
                    "route": route_path,
                    "status_class": f"{response_status // 100}xx",
                }
                services.observability.count("backend.http.requests", 1, attributes)
                services.observability.observe(
                    "backend.http.duration_ms",
                    elapsed_ms,
                    attributes,
                )
                if response_status >= 500:
                    services.observability.count("backend.http.errors", 1, attributes)
            reset_correlation_id(token)
