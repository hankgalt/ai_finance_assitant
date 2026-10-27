"""Source registry loading and offline HTTP acquisition."""

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from ai_finance_assistant.knowledge.models import FetchedSource, SourceDefinition, SourceRegistry


class SourceFetchError(RuntimeError):
    """Raised when an approved source cannot be fetched safely."""


class SourceFetcher(Protocol):
    def fetch(self, source: SourceDefinition) -> FetchedSource: ...


def load_source_registry(path: Path) -> SourceRegistry:
    return SourceRegistry.model_validate_json(path.read_text(encoding="utf-8"))


def registry_checksum(registry: SourceRegistry) -> str:
    canonical = json.dumps(
        registry.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(canonical).hexdigest()


class HttpSourceFetcher:
    """Bounded HTTPS fetcher used only by the explicit offline ingestion command."""

    def __init__(self, *, timeout_seconds: float = 30, max_bytes: int = 10_000_000) -> None:
        self._timeout_seconds = timeout_seconds
        self._max_bytes = max_bytes

    def fetch(self, source: SourceDefinition) -> FetchedSource:
        source_url = str(source.canonical_url)
        if urlparse(source_url).scheme != "https":
            raise SourceFetchError(f"source {source.source_id} must use HTTPS")

        request = Request(
            source_url,
            headers={"User-Agent": "AI-Finance-Assistant-Knowledge-Ingest/1.0"},
        )
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                final_url = response.geturl()
                if urlparse(final_url).hostname != urlparse(source_url).hostname:
                    raise SourceFetchError(
                        f"source {source.source_id} redirected to an unreviewed host"
                    )
                content_type = response.headers.get_content_type()
                if content_type not in {
                    "text/html",
                    "application/xhtml+xml",
                    "application/pdf",
                }:
                    raise SourceFetchError(
                        f"source {source.source_id} returned unsupported {content_type}"
                    )
                body = response.read(self._max_bytes + 1)
        except (HTTPError, URLError, TimeoutError) as error:
            raise SourceFetchError(f"failed to fetch {source.source_id}: {error}") from error

        if len(body) > self._max_bytes:
            raise SourceFetchError(f"source {source.source_id} exceeded the byte limit")
        if not body:
            raise SourceFetchError(f"source {source.source_id} returned an empty body")

        return FetchedSource(
            source_id=source.source_id,
            canonical_url=final_url,
            content_type=content_type,
            body=body,
            fetched_at=datetime.now(UTC),
            content_checksum=hashlib.sha256(body).hexdigest(),
        )


class FixtureSourceFetcher:
    """Deterministic, credential-free source adapter for tests and evaluation fixtures."""

    def __init__(self, bodies: Mapping[str, bytes], *, fetched_at: datetime | None = None) -> None:
        self._bodies = bodies
        self._fetched_at = fetched_at or datetime(2026, 1, 1, tzinfo=UTC)

    def fetch(self, source: SourceDefinition) -> FetchedSource:
        try:
            body = self._bodies[source.source_id]
        except KeyError as error:
            raise SourceFetchError(f"missing fixture for {source.source_id}") from error
        return FetchedSource(
            source_id=source.source_id,
            canonical_url=str(source.canonical_url),
            content_type="text/html",
            body=body,
            fetched_at=self._fetched_at,
            content_checksum=hashlib.sha256(body).hexdigest(),
        )


class CachedSourceFetcher:
    """Integrity-checked local cache around an explicit offline source fetcher."""

    def __init__(self, delegate: SourceFetcher, cache_dir: Path, *, refresh: bool = False) -> None:
        self._delegate = delegate
        self._cache_dir = cache_dir
        self._refresh = refresh

    def fetch(self, source: SourceDefinition) -> FetchedSource:
        metadata_path = self._cache_dir / f"{source.source_id}.json"
        body_path = self._cache_dir / f"{source.source_id}.bin"
        if not self._refresh and metadata_path.exists() and body_path.exists():
            body = body_path.read_bytes()
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            fetched = FetchedSource.model_validate({**metadata, "body": body})
            if fetched.source_id != source.source_id:
                raise SourceFetchError(f"cache identity mismatch for {source.source_id}")
            if fetched.content_checksum != hashlib.sha256(body).hexdigest():
                raise SourceFetchError(f"cache checksum mismatch for {source.source_id}")
            return fetched

        fetched = self._delegate.fetch(source)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        body_path.write_bytes(fetched.body)
        metadata_path.write_text(
            json.dumps(
                fetched.model_dump(mode="json", exclude={"body"}),
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return fetched
