"""Backend-neutral application persistence ports."""

from __future__ import annotations

from collections.abc import Generator, Sequence
from contextlib import AbstractContextManager
from typing import Any, Protocol


class DatabaseRow(Protocol):
    def __getitem__(self, key: str | int) -> Any: ...


class DatabaseCursor(Protocol):
    @property
    def rowcount(self) -> int: ...

    def fetchone(self) -> DatabaseRow | None: ...

    def fetchall(self) -> Sequence[DatabaseRow]: ...


class DatabaseConnection(Protocol):
    def execute(
        self,
        query: str,
        parameters: Sequence[object] = (),
    ) -> DatabaseCursor: ...


class ApplicationDatabase(Protocol):
    expected_version: int

    def migrate(self) -> None: ...

    def schema_version(self) -> int: ...

    def transaction(self) -> AbstractContextManager[DatabaseConnection]: ...

    def read(self) -> AbstractContextManager[DatabaseConnection]: ...

    def is_integrity_error(self, error: BaseException) -> bool: ...

    def close(self) -> None: ...


DatabaseGenerator = Generator[DatabaseConnection, None, None]
