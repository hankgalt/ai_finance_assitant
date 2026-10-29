import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_BACKEND_ROOT = Path(__file__).parents[1]
os.environ["AIFA_ENV_FILE"] = os.environ.get(
    "AIFA_TEST_ENV_FILE",
    str(_BACKEND_ROOT / ".test.env"),
)


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    from ai_finance_assistant.api.app import create_app
    from ai_finance_assistant.core.config import Settings

    app = create_app(
        Settings(
            mode="test",
            log_level="WARNING",
            storage_path=tmp_path / "application.sqlite3",
            provider_mode="credential_free",
            model_mode="credential_free",
            qdrant_url=None,
            langsmith_tracing_enabled=False,
        )
    )
    with TestClient(app) as test_client:
        yield test_client
