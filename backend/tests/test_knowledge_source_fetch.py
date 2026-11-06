"""Offline source acquisition safety: HTTPS, host, media-type, size, and cache integrity."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from email.message import Message
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError

import pytest
from pydantic import HttpUrl, TypeAdapter

from ai_finance_assistant.knowledge import registry as knowledge_registry
from ai_finance_assistant.knowledge.models import (
    LogicalKnowledgeBase,
    PermittedUse,
    SourceDefinition,
    SourceRegistry,
    SourceStatus,
    SourceType,
)
from ai_finance_assistant.knowledge.registry import (
    CachedSourceFetcher,
    FixtureSourceFetcher,
    HttpSourceFetcher,
    SourceFetchError,
    load_source_registry,
    registry_checksum,
)

REVIEWED_AT = datetime(2026, 10, 27, tzinfo=UTC)
_http_url = TypeAdapter(HttpUrl)


def _source(url: str = "https://example.gov/guide") -> SourceDefinition:
    return SourceDefinition(
        source_id="guide",
        logical_kb=LogicalKnowledgeBase.FINANCE,
        title="Guide",
        publisher="Example Federal Agency",
        canonical_url=_http_url.validate_python(url),
        source_type=SourceType.HTML,
        jurisdiction="US-Federal",
        status=SourceStatus.APPROVED,
        permitted_use=PermittedUse(
            basis="United States government work; source review recorded.",
            reviewer="repository-owner",
            ai_processing_allowed=True,
            redistribution_allowed=True,
            attribution_required=True,
            reviewed_at=REVIEWED_AT,
        ),
        ingestion_enabled=True,
    )


class _Response:
    def __init__(self, *, url: str, content_type: str, body: bytes) -> None:
        self._url = url
        self._body = body
        self.headers = Message()
        self.headers["Content-Type"] = content_type
        self.read_limits: list[int] = []

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def geturl(self) -> str:
        return self._url

    def read(self, limit: int) -> bytes:
        self.read_limits.append(limit)
        return self._body[:limit]


def _serve(monkeypatch: pytest.MonkeyPatch, outcome: _Response | Exception) -> list[Any]:
    requests: list[Any] = []

    def fake_urlopen(request: Any, timeout: float) -> _Response:
        requests.append((request, timeout))
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(knowledge_registry, "urlopen", fake_urlopen)
    return requests


def test_http_fetcher_returns_checksummed_body_with_identifying_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = b"<html><body>Guide</body></html>"
    requests = _serve(
        monkeypatch,
        _Response(
            url="https://example.gov/guide?v=2", content_type="text/html; charset=utf-8", body=body
        ),
    )

    fetched = HttpSourceFetcher(timeout_seconds=5, max_bytes=1024).fetch(_source())

    request, timeout = requests[0]
    assert timeout == 5
    assert request.get_header("User-agent") == "AI-Finance-Assistant-Knowledge-Ingest/1.0"
    assert fetched.canonical_url == "https://example.gov/guide?v=2"
    assert fetched.content_type == "text/html"
    assert fetched.body == body
    assert fetched.content_checksum == hashlib.sha256(body).hexdigest()


def test_http_fetcher_requires_https(monkeypatch: pytest.MonkeyPatch) -> None:
    requests = _serve(monkeypatch, AssertionError("must not fetch"))

    with pytest.raises(SourceFetchError, match="must use HTTPS"):
        HttpSourceFetcher().fetch(_source("http://example.gov/guide"))
    assert requests == []


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (
            _Response(url="https://attacker.example/guide", content_type="text/html", body=b"x"),
            "unreviewed host",
        ),
        (
            _Response(url="https://example.gov/guide", content_type="application/zip", body=b"x"),
            "unsupported application/zip",
        ),
        (
            _Response(
                url="https://example.gov/guide", content_type="application/pdf", body=b"x" * 11
            ),
            "exceeded the byte limit",
        ),
        (
            _Response(url="https://example.gov/guide", content_type="text/html", body=b""),
            "empty body",
        ),
    ],
)
def test_http_fetcher_rejects_unsafe_responses(
    monkeypatch: pytest.MonkeyPatch, response: _Response, message: str
) -> None:
    _serve(monkeypatch, response)

    with pytest.raises(SourceFetchError, match=message):
        HttpSourceFetcher(max_bytes=10).fetch(_source())


@pytest.mark.parametrize(
    "error",
    [
        HTTPError("https://example.gov/guide", 503, "Unavailable", Message(), None),
        URLError("dns failure"),
        TimeoutError("timed out"),
    ],
)
def test_http_fetcher_wraps_transport_failures(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    _serve(monkeypatch, error)

    with pytest.raises(SourceFetchError, match="failed to fetch guide"):
        HttpSourceFetcher().fetch(_source())


def test_fixture_fetcher_reports_missing_fixture() -> None:
    with pytest.raises(SourceFetchError, match="missing fixture for guide"):
        FixtureSourceFetcher({}).fetch(_source())


def _prime_cache(tmp_path: Path) -> tuple[Path, Path]:
    CachedSourceFetcher(FixtureSourceFetcher({"guide": b"<p>cached</p>"}), tmp_path).fetch(
        _source()
    )
    return tmp_path / "guide.json", tmp_path / "guide.bin"


def test_cache_rejects_tampered_body(tmp_path: Path) -> None:
    _, body_path = _prime_cache(tmp_path)
    body_path.write_bytes(b"<p>tampered</p>")

    with pytest.raises(SourceFetchError, match="cache checksum mismatch"):
        CachedSourceFetcher(FixtureSourceFetcher({}), tmp_path).fetch(_source())


def test_cache_rejects_identity_mismatch(tmp_path: Path) -> None:
    metadata_path, _ = _prime_cache(tmp_path)
    metadata = json.loads(metadata_path.read_text())
    metadata["source_id"] = "other"
    metadata_path.write_text(json.dumps(metadata))

    with pytest.raises(SourceFetchError, match="cache identity mismatch"):
        CachedSourceFetcher(FixtureSourceFetcher({}), tmp_path).fetch(_source())


def test_cache_refresh_bypasses_existing_entry(tmp_path: Path) -> None:
    _prime_cache(tmp_path)

    refreshed = CachedSourceFetcher(
        FixtureSourceFetcher({"guide": b"<p>fresh</p>"}), tmp_path, refresh=True
    ).fetch(_source())

    assert refreshed.body == b"<p>fresh</p>"
    assert (tmp_path / "guide.bin").read_bytes() == b"<p>fresh</p>"


def test_registry_round_trip_and_checksum_are_stable(tmp_path: Path) -> None:
    registry = SourceRegistry(reviewed_at=REVIEWED_AT, sources=(_source(),))
    path = tmp_path / "registry.json"
    path.write_text(registry.model_dump_json(indent=2), encoding="utf-8")

    loaded = load_source_registry(path)

    assert loaded == registry
    assert registry_checksum(loaded) == registry_checksum(registry)
    changed = registry.model_copy(update={"reviewed_at": datetime(2026, 10, 28, tzinfo=UTC)})
    assert registry_checksum(changed) != registry_checksum(registry)
