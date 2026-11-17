"""ASGI construction for the Shared Edge."""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
import re
from typing import Literal

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.routing import Route
from starlette.types import ASGIApp

from ._generation import (
    GenerationBinding,
    GenerationLoadError,
    GenerationSource,
    LoadedGeneration,
    load_generation,
)


DIGEST_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")


@dataclass(frozen=True, slots=True)
class RuntimeConfiguration:
    """Non-secret process configuration accepted by the Shared Edge."""

    profile: Literal["qualification-v1"]
    generation_bucket: str | None = None
    generation_object: str | None = None
    generation_object_generation: int | None = None
    generation_content_digest: str | None = None
    generation_digest: str | None = None

    def __post_init__(self) -> None:
        if self.profile != "qualification-v1":
            raise ValueError(f"unsupported runtime profile: {self.profile}")
        generation_values = (
            self.generation_bucket,
            self.generation_object,
            self.generation_object_generation,
            self.generation_content_digest,
            self.generation_digest,
        )
        if any(value is not None for value in generation_values) and any(
            value is None for value in generation_values
        ):
            raise ValueError("generation binding must be complete")
        if self.generation_bucket is not None:
            if not 3 <= len(self.generation_bucket) <= 63:
                raise ValueError("generation bucket is out of bounds")
            if not 1 <= len(self.generation_object or "") <= 1_024:
                raise ValueError("generation object is out of bounds")
            if (
                isinstance(self.generation_object_generation, bool)
                or not isinstance(self.generation_object_generation, int)
                or self.generation_object_generation < 1
            ):
                raise ValueError("generation object generation is invalid")
            for digest in (self.generation_content_digest, self.generation_digest):
                if not isinstance(digest, str) or DIGEST_PATTERN.fullmatch(digest) is None:
                    raise ValueError("generation digest is invalid")

    def _generation_binding(self) -> GenerationBinding | None:
        if self.generation_bucket is None:
            return None
        return GenerationBinding(
            bucket=self.generation_bucket,
            object_name=self.generation_object or "",
            object_generation=self.generation_object_generation or 0,
            content_digest=self.generation_content_digest or "",
            generation_digest=self.generation_digest or "",
        )


@dataclass(frozen=True, slots=True)
class RuntimeAdapters:
    """Injected external behavior used by the Shared Edge."""

    generation_source: GenerationSource | None = None


def create_app(
    runtime_configuration: RuntimeConfiguration,
    adapters: RuntimeAdapters,
) -> ASGIApp:
    """Create the ASGI application without opening a socket or performing I/O."""
    active_generation: LoadedGeneration | None = None

    @asynccontextmanager
    async def lifespan(_: Starlette):
        nonlocal active_generation
        binding = runtime_configuration._generation_binding()
        if binding is not None and active_generation is None:
            if adapters.generation_source is None:
                raise RuntimeError("generation startup failed: GENERATION_SOURCE_UNAVAILABLE")
            try:
                active_generation = await load_generation(
                    binding,
                    adapters.generation_source,
                )
            except GenerationLoadError as error:
                raise RuntimeError(f"generation startup failed: {error.code}") from None
        yield

    async def unavailable(_: Request) -> Response:
        message = (
            "platform routing unavailable\n"
            if active_generation is not None
            else "platform unavailable\n"
        )
        return PlainTextResponse(
            message,
            status_code=503,
            headers={"Cache-Control": "no-store"},
        )

    return Starlette(
        routes=[Route("/{path:path}", unavailable)],
        lifespan=lifespan,
    )
