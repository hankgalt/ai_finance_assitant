"""Request correlation without logging bodies, headers, or query values."""

import logging
import re
import time
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from ai_finance_assistant.core.logging import reset_correlation_id, set_correlation_id

logger = logging.getLogger(__name__)
SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


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
            root_path = request.scope.get("root_path", "")
            route_path = f"{root_path}{getattr(route, 'path', 'unmatched')}"
            if request.url.path.startswith("/api/") and not route_path.startswith("/api/"):
                route_path = f"/api{route_path}"
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
