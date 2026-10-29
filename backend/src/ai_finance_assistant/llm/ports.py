"""True-external structured model interface."""

from typing import Protocol

from ai_finance_assistant.llm.models import ModelAdapterResult, ModelRequest


class ModelAdapter(Protocol):
    @property
    def model_id(self) -> str: ...

    @property
    def provider_id(self) -> str: ...

    @property
    def prompt_version(self) -> str: ...

    def generate(self, request: ModelRequest) -> ModelAdapterResult: ...
