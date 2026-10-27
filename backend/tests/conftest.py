from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from ai_finance_assistant.api.app import create_app
from ai_finance_assistant.core.config import Settings


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app(Settings(mode="test", log_level="WARNING"))
    with TestClient(app) as test_client:
        yield test_client
