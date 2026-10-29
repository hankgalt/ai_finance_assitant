"""Stable, privacy-safe API failures."""

from dataclasses import dataclass

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ai_finance_assistant.contracts.api import ApiError
from ai_finance_assistant.contracts.errors import ErrorCategory, SafeError


@dataclass
class ApiProblem(Exception):
    status_code: int
    code: str
    category: ErrorCategory
    message: str
    retryable: bool = False


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiProblem)
    async def api_problem_handler(request: Request, error: ApiProblem) -> JSONResponse:
        del request
        body = ApiError(
            error=SafeError(
                code=error.code,
                category=error.category,
                message=error.message,
                retryable=error.retryable,
            )
        )
        return JSONResponse(status_code=error.status_code, content=body.model_dump(mode="json"))

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, error: RequestValidationError) -> JSONResponse:
        del request, error
        body = ApiError(
            error=SafeError(
                code="REQUEST_VALIDATION_FAILED",
                category=ErrorCategory.VALIDATION,
                message="The request did not match the versioned API contract.",
            )
        )
        return JSONResponse(status_code=422, content=body.model_dump(mode="json"))
