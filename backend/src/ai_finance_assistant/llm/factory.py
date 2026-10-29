"""Environment-owned selection of one model adapter for one Run."""

from __future__ import annotations

from typing import cast

from openai import OpenAI

from ai_finance_assistant.core.config import Settings
from ai_finance_assistant.llm.errors import ModelErrorCode, ModelProviderError
from ai_finance_assistant.llm.fake import DeterministicModelAdapter
from ai_finance_assistant.llm.models import ModelAdapterResult, ModelRequest
from ai_finance_assistant.llm.openai import (
    OPENAI_PROMPT_VERSION,
    OpenAIClient,
    OpenAIModelAdapter,
)
from ai_finance_assistant.llm.ports import ModelAdapter


class UnavailableModelAdapter:
    provider_id = "openai"
    prompt_version = OPENAI_PROMPT_VERSION

    def __init__(self, *, model_id: str, error: ModelProviderError) -> None:
        self.model_id = model_id
        self._error = error

    def generate(self, request: ModelRequest) -> ModelAdapterResult:
        del request
        raise self._error


def model_adapter_from_settings(
    settings: Settings,
    *,
    client: OpenAIClient | None = None,
) -> ModelAdapter:
    """Build a fixed adapter; live-mode readiness never falls back to the fake."""

    if settings.model_mode == "credential_free":
        return DeterministicModelAdapter()
    if not settings.openai_terms_approved:
        return UnavailableModelAdapter(
            model_id=settings.openai_model,
            error=ModelProviderError(
                code=ModelErrorCode.NOT_READY,
                message="Live model use requires explicit account-terms approval.",
            ),
        )
    if settings.openai_api_key is None:
        return UnavailableModelAdapter(
            model_id=settings.openai_model,
            error=ModelProviderError(
                code=ModelErrorCode.AUTHENTICATION_FAILED,
                message="Live model credentials are not configured.",
            ),
        )

    resolved_client = client or cast(
        OpenAIClient,
        OpenAI(
            api_key=settings.openai_api_key.get_secret_value(),
            max_retries=0,
            timeout=settings.model_timeout_seconds,
        ),
    )
    return OpenAIModelAdapter(
        client=resolved_client,
        model=settings.openai_model,
        request_budget=settings.model_request_budget,
        maximum_attempts=settings.model_maximum_attempts,
        timeout_seconds=settings.model_timeout_seconds,
        maximum_input_characters=settings.model_maximum_input_characters,
    )
