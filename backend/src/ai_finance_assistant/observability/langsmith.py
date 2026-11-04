"""Optional LangSmith context that hides application inputs and outputs."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager, suppress
from importlib import import_module
from typing import Any

from langsmith import Client

_RUN_HELPERS: Any = import_module("langsmith.run_helpers")
tracing_context: Any = _RUN_HELPERS.tracing_context


class LangSmithTracing:
    def __init__(
        self,
        *,
        enabled: bool,
        project: str,
        api_key: str | None,
    ) -> None:
        self._enabled = enabled
        self._project = project
        self._api_key = api_key

    @contextmanager
    def activate(self) -> Generator[None, None, None]:
        manager_factory = tracing_context
        if not self._enabled:
            with manager_factory(enabled=False):
                yield
            return
        try:
            client = Client(
                api_key=self._api_key,
                hide_inputs=True,
                hide_outputs=True,
            )
            manager = manager_factory(
                enabled=True,
                project_name=self._project,
                client=client,
                metadata={"privacy_mode": "inputs_outputs_hidden"},
            )
            manager.__enter__()
        except Exception:
            yield
            return
        try:
            yield
        except BaseException as exc:
            with suppress(Exception):
                manager.__exit__(type(exc), exc, exc.__traceback__)
            raise
        else:
            with suppress(Exception):
                manager.__exit__(None, None, None)
