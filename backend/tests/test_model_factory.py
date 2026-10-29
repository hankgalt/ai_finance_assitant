from datetime import UTC, datetime, timedelta

import pytest
from pydantic import SecretStr
from pytest import MonkeyPatch

from ai_finance_assistant.contracts.agents import AgentId
from ai_finance_assistant.core.config import Settings
from ai_finance_assistant.llm.errors import ModelErrorCode, ModelProviderError
from ai_finance_assistant.llm.factory import model_adapter_from_settings
from ai_finance_assistant.llm.fake import DeterministicModelAdapter
from ai_finance_assistant.llm.models import ModelRequest
from ai_finance_assistant.llm.openai import OpenAIModelAdapter, ResponsesEndpoint


def model_request() -> ModelRequest:
    return ModelRequest(
        agent_id=AgentId.FINANCE_QA,
        user_message="What is an ETF?",
        instructions="Explain from evidence.",
        deadline_at=datetime.now(UTC) + timedelta(minutes=1),
    )


def test_credential_free_mode_builds_only_deterministic_adapter() -> None:
    model = model_adapter_from_settings(
        Settings(mode="test", model_mode="credential_free", _env_file=None)
    )

    assert isinstance(model, DeterministicModelAdapter)


@pytest.mark.parametrize(
    ("settings", "code"),
    (
        (
            Settings(
                mode="test",
                model_mode="openai_live",
                openai_terms_approved=False,
                openai_api_key=SecretStr("fixture"),
                _env_file=None,
            ),
            ModelErrorCode.NOT_READY,
        ),
        (
            Settings(
                mode="test",
                model_mode="openai_live",
                openai_terms_approved=True,
                openai_api_key=None,
                _env_file=None,
            ),
            ModelErrorCode.AUTHENTICATION_FAILED,
        ),
    ),
)
def test_live_mode_missing_gate_returns_typed_unavailable_adapter(
    settings: Settings,
    code: ModelErrorCode,
) -> None:
    model = model_adapter_from_settings(settings)

    with pytest.raises(ModelProviderError) as caught:
        model.generate(model_request())

    assert caught.value.code == code
    assert model.provider_id == "openai"
    assert model.model_id == "gpt-6.1-sol"


def test_approved_live_mode_builds_openai_adapter_with_injected_client() -> None:
    class FakeClient:
        @property
        def responses(self) -> ResponsesEndpoint:
            raise AssertionError("the factory test does not call the provider")

    model = model_adapter_from_settings(
        Settings(
            mode="test",
            model_mode="openai_live",
            openai_terms_approved=True,
            openai_api_key=SecretStr("fixture"),
            _env_file=None,
        ),
        client=FakeClient(),
    )

    assert isinstance(model, OpenAIModelAdapter)
    assert model.model_id == "gpt-6.1-sol"


def test_standard_and_legacy_langsmith_environment_names_are_supported(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    monkeypatch.setenv("LANGCHAIN_API_KEY", "legacy-fixture")
    monkeypatch.setenv("LANGCHAIN_PROJECT", "legacy-project")

    legacy = Settings(_env_file=None)

    assert legacy.langsmith_tracing_enabled is True
    assert legacy.langsmith_api_key is not None
    assert legacy.langsmith_api_key.get_secret_value() == "legacy-fixture"
    assert legacy.langsmith_project == "legacy-project"

    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "current-fixture")
    monkeypatch.setenv("LANGSMITH_PROJECT", "current-project")

    current = Settings(_env_file=None)

    assert current.langsmith_tracing_enabled is True
    assert current.langsmith_api_key is not None
    assert current.langsmith_api_key.get_secret_value() == "current-fixture"
    assert current.langsmith_project == "current-project"


def test_openai_standard_environment_key_is_supported(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "openai-fixture")

    settings = Settings(_env_file=None)

    assert settings.openai_api_key is not None
    assert settings.openai_api_key.get_secret_value() == "openai-fixture"
