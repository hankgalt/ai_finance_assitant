"""Structured model seam and selected adapters."""

from ai_finance_assistant.llm.fake import DeterministicModelAdapter
from ai_finance_assistant.llm.models import ModelOutput, ModelRequest
from ai_finance_assistant.llm.openai import OpenAIModelAdapter
from ai_finance_assistant.llm.ports import ModelAdapter

__all__ = [
    "DeterministicModelAdapter",
    "ModelAdapter",
    "ModelOutput",
    "ModelRequest",
    "OpenAIModelAdapter",
]
