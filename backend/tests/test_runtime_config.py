"""Runtime configuration invariants that must fail before service initialization."""

import pytest
from pydantic import ValidationError

from ai_finance_assistant.core.config import Settings


def test_runtime_rejects_a_stale_application_schema_pin() -> None:
    with pytest.raises(ValidationError, match="runtime storage schema version must be 4"):
        Settings(storage_expected_schema_version=3)
