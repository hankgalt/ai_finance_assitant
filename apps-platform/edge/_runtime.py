"""ASGI construction for the Shared Edge."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.routing import Route
from starlette.types import ASGIApp


@dataclass(frozen=True, slots=True)
class RuntimeConfiguration:
    """Non-secret process configuration accepted by the Shared Edge."""

    profile: Literal["qualification-v1"]

    def __post_init__(self) -> None:
        if self.profile != "qualification-v1":
            raise ValueError(f"unsupported runtime profile: {self.profile}")


@dataclass(frozen=True, slots=True)
class RuntimeAdapters:
    """Injected external behavior used by the Shared Edge."""


def create_app(
    runtime_configuration: RuntimeConfiguration,
    adapters: RuntimeAdapters,
) -> ASGIApp:
    """Create the ASGI application without opening a socket or performing I/O."""
    del runtime_configuration, adapters

    async def unavailable(_: Request) -> Response:
        return PlainTextResponse(
            "platform unavailable\n",
            status_code=503,
            headers={"Cache-Control": "no-store"},
        )

    return Starlette(routes=[Route("/{path:path}", unavailable)])
