"""Deterministic shared-knowledge snapshot release behavior."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

import httpx
import pytest

from ai_finance_assistant.knowledge.models import (
    ChunkingPolicy,
    CollectionCompatibility,
    CollectionManifest,
    CollectionState,
    EvaluationCase,
    EvaluationReport,
    Evidence,
    LogicalKnowledgeBase,
    RetrievalFilter,
    RetrievalQuery,
    SparseEmbedding,
)
from ai_finance_assistant.knowledge.release import (
    CollectionReleaseContract,
    CredentialSetContract,
    EndpointContract,
    HttpRuntimePermissionProbe,
    HttpSnapshotTransport,
    KnowledgeRelease,
    KnowledgeReleaseContract,
    ProviderBoundaryContract,
    ReleaseKeyRevocationProbe,
    SnapshotDescription,
    _deployed_provider_boundary,
)
from ai_finance_assistant.knowledge.representations import DeterministicTestEncoder
from ai_finance_assistant.knowledge.store import ActivationResult

NOW = datetime(2026, 11, 11, tzinfo=UTC)


class FakeReleaseStore:
    def __init__(self) -> None:
        self.manifests: dict[str, CollectionManifest] = {}
        self.aliases: dict[str, str] = {}
        self.searches: list[str] = []

    def get_manifest(self, collection_name: str) -> CollectionManifest | None:
        return self.manifests.get(collection_name)

    def count_points(self, collection_name: str) -> int:
        manifest = self.manifests.get(collection_name)
        return 0 if manifest is None else manifest.point_count

    def validate_collection(
        self, collection_name: str, expected: CollectionCompatibility
    ) -> tuple[bool, str]:
        manifest = self.manifests.get(collection_name)
        if manifest is None:
            return False, "missing"
        compatible = (
            manifest.logical_kb == expected.logical_kb
            and manifest.dense_model_id == expected.dense_model_id
            and manifest.sparse_model_id == expected.sparse_model_id
            and manifest.ready
        )
        return compatible, f"compatible collection {collection_name}"

    def activate(self, alias: str, collection_name: str) -> ActivationResult:
        manifest = self.manifests[collection_name]
        if not manifest.ready:
            raise ValueError("collection is not ready")
        previous = self.aliases.get(alias)
        self.aliases[alias] = collection_name
        return ActivationResult(alias, collection_name, previous)

    def resolve_alias(self, alias: str) -> str | None:
        return self.aliases.get(alias)

    def search(
        self,
        collection_name: str,
        query: RetrievalQuery,
        dense: Sequence[float],
        sparse: SparseEmbedding,
    ) -> tuple[Evidence, ...]:
        del dense, sparse
        self.searches.append(collection_name)
        manifest = self.manifests[collection_name]
        document_id = f"{manifest.logical_kb.value}-doc"
        return (
            Evidence(
                chunk_id="a" * 64,
                document_id=document_id,
                title="Qualified source",
                publisher="Example Federal Agency",
                canonical_url="https://example.gov/source",
                section_path="Source > Section",
                text="Qualified public educational content.",
                score=1.0,
                rank=1,
                collection_name=collection_name,
                collection_version=manifest.collection_version,
                document_version="b" * 64,
                content_hash="c" * 64,
                fetched_at=NOW,
                tax_years=() if query.filters.tax_year is None else (query.filters.tax_year,),
                jurisdiction=query.filters.jurisdiction or "US-Federal",
            ),
        )


class FakeSourceSnapshots:
    def __init__(self) -> None:
        self.created: list[str] = []
        self.deleted: list[str] = []

    @staticmethod
    def _content(collection_name: str) -> bytes:
        return f"snapshot:{collection_name}".encode()

    def server_version(self) -> str:
        return "1.20.0"

    def create(self, collection_name: str) -> SnapshotDescription:
        self.created.append(collection_name)
        content = self._content(collection_name)
        return SnapshotDescription(
            name=f"{collection_name}.snapshot",
            checksum=sha256(content).hexdigest(),
            size_bytes=len(content),
        )

    def download(self, collection_name: str, snapshot_name: str, destination: Path) -> str:
        assert snapshot_name == f"{collection_name}.snapshot"
        content = self._content(collection_name)
        destination.write_bytes(content)
        return sha256(content).hexdigest()

    def delete(self, collection_name: str, snapshot_name: str) -> None:
        assert snapshot_name == f"{collection_name}.snapshot"
        self.deleted.append(collection_name)

    def upload(self, collection_name: str, snapshot_path: Path, checksum: str) -> None:
        raise AssertionError((collection_name, snapshot_path, checksum))


class FakeTargetSnapshots:
    def __init__(self, source: FakeReleaseStore, target: FakeReleaseStore) -> None:
        self.source = source
        self.target = target
        self.uploaded: list[str] = []

    def server_version(self) -> str:
        return "1.20.0"

    def create(self, collection_name: str) -> SnapshotDescription:
        raise AssertionError(collection_name)

    def download(self, collection_name: str, snapshot_name: str, destination: Path) -> str:
        raise AssertionError((collection_name, snapshot_name, destination))

    def delete(self, collection_name: str, snapshot_name: str) -> None:
        raise AssertionError((collection_name, snapshot_name))

    def upload(self, collection_name: str, snapshot_path: Path, checksum: str) -> None:
        assert checksum == sha256(snapshot_path.read_bytes()).hexdigest()
        self.target.manifests[collection_name] = self.source.manifests[collection_name]
        self.uploaded.append(collection_name)


class PassingPermissionProbe:
    def prove_read_only(self) -> dict[str, Any]:
        return {"read_status": 200, "write_status": 403, "passed": True}


def _manifest(name: str, logical_kb: LogicalKnowledgeBase) -> CollectionManifest:
    return CollectionManifest(
        logical_kb=logical_kb,
        collection_name=name,
        collection_version=name.rsplit("_", maxsplit=1)[-1],
        corpus_checksum=sha256(name.encode()).hexdigest(),
        source_registry_checksum="d" * 64,
        dense_model_id="dense-v1",
        dense_dimensions=4,
        sparse_model_id="sparse-v1",
        chunking_policy=ChunkingPolicy(max_chars=400, overlap_chars=40, min_chars=20),
        point_count=1,
        document_count=1,
        source_ids=(f"{logical_kb.value}-doc",),
        created_at=NOW,
        state=CollectionState.READY,
        ready=True,
        evaluation_artifact="synthetic:passing",
    )


def _write_artifacts(
    root: Path,
    logical_kb: LogicalKnowledgeBase,
    current: CollectionManifest,
    rollback: CollectionManifest,
) -> CollectionReleaseContract:
    directory = root / logical_kb.value
    directory.mkdir(parents=True)
    current_path = directory / "current.manifest.json"
    rollback_path = directory / "rollback.manifest.json"
    qrels_path = directory / "qrels.json"
    evaluation_path = directory / "evaluation.json"
    current_path.write_text(
        json.dumps({"manifest": current.model_dump(mode="json")}), encoding="utf-8"
    )
    rollback_path.write_text(
        json.dumps({"manifest": rollback.model_dump(mode="json")}), encoding="utf-8"
    )
    case = EvaluationCase(
        case_id=f"{logical_kb.value}-case",
        query="qualified education",
        filters=RetrievalFilter(logical_kb=logical_kb),
        expected_document_ids=(f"{logical_kb.value}-doc",),
    )
    qrels_path.write_text(json.dumps([case.model_dump(mode="json")]), encoding="utf-8")
    from ai_finance_assistant.knowledge.evaluation import qrels_checksum

    baseline = EvaluationReport(
        logical_kb=logical_kb,
        collection_name=current.collection_name,
        qrels_checksum=qrels_checksum((case,)),
        qrels_case_count=1,
        metrics=(),
        critical_filters_exact=True,
        citation_integrity=True,
        passed=True,
    )
    evaluation_path.write_text(baseline.model_dump_json(), encoding="utf-8")
    return CollectionReleaseContract(
        logical_kb=logical_kb,
        alias=f"{logical_kb.value}_active",
        current_collection=current.collection_name,
        rollback_collection=rollback.collection_name,
        current_manifest=current_path.relative_to(root),
        rollback_manifest=rollback_path.relative_to(root),
        qrels=qrels_path.relative_to(root),
        baseline_evaluation=evaluation_path.relative_to(root),
        expected_current_points=1,
    )


def _contract(root: Path) -> tuple[KnowledgeReleaseContract, dict[str, CollectionManifest]]:
    manifests: dict[str, CollectionManifest] = {}
    specs: list[CollectionReleaseContract] = []
    for logical_kb in LogicalKnowledgeBase:
        current = _manifest(f"{logical_kb.value}_current", logical_kb)
        rollback = _manifest(f"{logical_kb.value}_rollback", logical_kb)
        manifests[current.collection_name] = current
        manifests[rollback.collection_name] = rollback
        specs.append(_write_artifacts(root, logical_kb, current, rollback))
    credentials = CredentialSetContract.model_validate(
        {
            "runtime": {"secret_id": "runtime", "qdrant_access": "cluster_wide_read_only"},
            "release": {"secret_id": "release", "qdrant_access": "cluster_wide_manage_write"},
            "payloads_allowed_in_repository": False,
            "payloads_allowed_in_github": False,
            "payloads_managed_by_terraform": False,
        }
    )
    return (
        KnowledgeReleaseContract(
            schema_version="1",
            status="defined_not_executed",
            source=EndpointContract(endpoint="http://127.0.0.1:6333", qdrant_version="1.20.0"),
            target=EndpointContract(endpoint="https://qdrant.example", qdrant_version="1.20.0"),
            credentials=credentials,
            collections=tuple(specs),
            provider_boundary=ProviderBoundaryContract(
                provider_mode="credential_free",
                model_mode="credential_free",
                live_provider_secrets_allowed=False,
                live_provider_activation="separate_owner_approval_required",
                viewer_live_provider_access="denied",
            ),
        ),
        manifests,
    )


def test_release_uploads_missing_snapshots_qualifies_and_restores_current_aliases(
    tmp_path: Path,
) -> None:
    contract, manifests = _contract(tmp_path)
    source = FakeReleaseStore()
    source.manifests.update(manifests)
    target = FakeReleaseStore()
    runtime = FakeReleaseStore()
    runtime.manifests = target.manifests
    runtime.aliases = target.aliases
    source_snapshots = FakeSourceSnapshots()
    target_snapshots = FakeTargetSnapshots(source, target)
    release = KnowledgeRelease(
        contract=contract,
        repo_root=tmp_path,
        source_store=source,
        target_release_store=target,
        target_runtime_store=runtime,
        source_snapshots=source_snapshots,
        target_snapshots=target_snapshots,
        permission_probe=PassingPermissionProbe(),
        encoder=DeterministicTestEncoder(),
        clock=lambda: NOW,
    )

    evidence = release.execute(revision="e" * 40, contract_sha256="f" * 64)

    assert evidence["status"] == "qualified_release_key_revocation_pending"
    assert [item["action"] for item in evidence["transfers"]] == [
        "uploaded_snapshot",
        "uploaded_snapshot",
        "uploaded_snapshot",
        "uploaded_snapshot",
    ]
    assert source_snapshots.created == source_snapshots.deleted
    assert target_snapshots.uploaded == source_snapshots.created
    assert all(item["passed"] for item in evidence["evaluations"])
    assert runtime.searches
    assert target.searches == []
    assert all(item["passed"] for item in evidence["rollback_proofs"])
    assert evidence["runtime_permission"] == {
        "read_status": 200,
        "write_status": 403,
        "passed": True,
    }
    assert evidence["secret_payloads_recorded"] is False
    for spec in contract.collections:
        assert target.resolve_alias(spec.alias) == spec.current_collection


def test_release_reuses_exact_remote_collections_without_snapshot_writes(tmp_path: Path) -> None:
    contract, manifests = _contract(tmp_path)
    source = FakeReleaseStore()
    source.manifests.update(manifests)
    target = FakeReleaseStore()
    target.manifests.update(manifests)
    source_snapshots = FakeSourceSnapshots()
    release = KnowledgeRelease(
        contract=contract,
        repo_root=tmp_path,
        source_store=source,
        target_release_store=target,
        target_runtime_store=target,
        source_snapshots=source_snapshots,
        target_snapshots=FakeTargetSnapshots(source, target),
        permission_probe=PassingPermissionProbe(),
        encoder=DeterministicTestEncoder(),
        clock=lambda: NOW,
    )

    evidence = release.execute(revision="e" * 40, contract_sha256="f" * 64)

    assert {item["action"] for item in evidence["transfers"]} == {"validated_existing"}
    assert source_snapshots.created == []
    assert source_snapshots.deleted == []


def test_release_fails_closed_on_conflicting_remote_collection(tmp_path: Path) -> None:
    contract, manifests = _contract(tmp_path)
    source = FakeReleaseStore()
    source.manifests.update(manifests)
    target = FakeReleaseStore()
    first = contract.collections[0].current_collection
    target.manifests[first] = manifests[first].model_copy(update={"corpus_checksum": "0" * 64})
    release = KnowledgeRelease(
        contract=contract,
        repo_root=tmp_path,
        source_store=source,
        target_release_store=target,
        target_runtime_store=target,
        source_snapshots=FakeSourceSnapshots(),
        target_snapshots=FakeTargetSnapshots(source, target),
        permission_probe=PassingPermissionProbe(),
        encoder=DeterministicTestEncoder(),
    )

    with pytest.raises(ValueError, match="manifest conflicts"):
        release.execute(revision="e" * 40, contract_sha256="f" * 64)


def test_release_rejects_any_live_provider_boundary(tmp_path: Path) -> None:
    contract, manifests = _contract(tmp_path)
    source = FakeReleaseStore()
    source.manifests.update(manifests)
    target = FakeReleaseStore()
    live_contract = contract.model_copy(
        update={
            "provider_boundary": contract.provider_boundary.model_copy(
                update={"provider_mode": "live"}
            )
        }
    )
    release = KnowledgeRelease(
        contract=live_contract,
        repo_root=tmp_path,
        source_store=source,
        target_release_store=target,
        target_runtime_store=target,
        source_snapshots=FakeSourceSnapshots(),
        target_snapshots=FakeTargetSnapshots(source, target),
        permission_probe=PassingPermissionProbe(),
        encoder=DeterministicTestEncoder(),
    )

    with pytest.raises(ValueError, match="provider boundary"):
        release.execute(revision="e" * 40, contract_sha256="f" * 64)


def _write_service_description(tmp_path: Path, environment: list[dict[str, Any]]) -> Path:
    path = tmp_path / "service.json"
    path.write_text(
        json.dumps(
            {
                "spec": {
                    "template": {"spec": {"containers": [{"name": "backend", "env": environment}]}}
                }
            }
        ),
        encoding="utf-8",
    )
    return path


def test_deployed_provider_boundary_accepts_only_credential_free_configuration(
    tmp_path: Path,
) -> None:
    path = _write_service_description(
        tmp_path,
        [
            {"name": "AIFA_PROVIDER_MODE", "value": "credential_free"},
            {"name": "AIFA_MODEL_MODE", "value": "credential_free"},
            {
                "name": "AIFA_QDRANT_API_KEY",
                "valueFrom": {"secretKeyRef": {"secret": "runtime", "version": "1"}},
            },
        ],
    )

    assert _deployed_provider_boundary(path) == {
        "service": "aifa-staging-backend",
        "provider_mode": "credential_free",
        "model_mode": "credential_free",
        "forbidden_provider_environment_names_present": False,
        "passed": True,
    }


@pytest.mark.parametrize(
    ("environment", "message"),
    [
        (
            [
                {"name": "AIFA_PROVIDER_MODE", "value": "credential_free"},
                {"name": "AIFA_MODEL_MODE", "value": "credential_free"},
                {"name": "aifa_openai_api_key", "value": "not-recorded-in-evidence"},
            ],
            "forbidden live-provider",
        ),
        (
            [
                {"name": "AIFA_PROVIDER_MODE", "value": "live"},
                {"name": "AIFA_MODEL_MODE", "value": "credential_free"},
            ],
            "provider mode",
        ),
        (
            [
                {"name": "AIFA_PROVIDER_MODE", "value": "credential_free"},
                {"name": "AIFA_MODEL_MODE", "value": "openai_live"},
            ],
            "model mode",
        ),
    ],
)
def test_deployed_provider_boundary_fails_closed_on_live_configuration(
    tmp_path: Path, environment: list[dict[str, Any]], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        _deployed_provider_boundary(_write_service_description(tmp_path, environment))


def test_runtime_permission_probe_requires_read_access_and_http_403_on_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_client = httpx.Client

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["api-key"] == "runtime-key"
        if request.method == "GET":
            return httpx.Response(200, json={"status": "ok", "result": {"collections": []}})
        assert request.method == "PUT"
        assert request.url.path.startswith("/collections/aifa_runtime_permission_probe_")
        return httpx.Response(403, json={"status": {"error": "forbidden"}})

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        "ai_finance_assistant.knowledge.release.httpx.Client",
        lambda **kwargs: original_client(transport=transport, **kwargs),
    )

    result = HttpRuntimePermissionProbe(
        "https://qdrant.example", "runtime-key", "release-key"
    ).prove_read_only()

    assert result == {"read_status": 200, "write_status": 403, "passed": True}


def test_snapshot_transport_uses_authenticated_checksum_verified_qdrant_routes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    original_client = httpx.Client
    snapshot_bytes = b"qualified-snapshot"
    digest = sha256(snapshot_bytes).hexdigest()
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["api-key"] == "release-key"
        encoded_path = request.url.raw_path.decode().split("?", maxsplit=1)[0]
        calls.append((request.method, encoded_path))
        if request.url.path == "/":
            return httpx.Response(200, json={"version": "1.20.0"})
        if request.method == "POST" and request.url.path.endswith("/snapshots"):
            assert request.url.params["wait"] == "true"
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "result": {
                        "name": "snapshot/name",
                        "checksum": digest,
                        "size": len(snapshot_bytes),
                    },
                },
            )
        if request.method == "GET":
            return httpx.Response(200, content=snapshot_bytes)
        if request.method == "DELETE":
            assert request.url.params["wait"] == "true"
            return httpx.Response(200, json={"status": "ok", "result": True})
        assert request.method == "POST" and request.url.path.endswith("/snapshots/upload")
        assert dict(request.url.params) == {
            "wait": "true",
            "priority": "snapshot",
            "checksum": digest,
        }
        assert snapshot_bytes in request.read()
        return httpx.Response(200, json={"status": "ok", "result": True})

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        "ai_finance_assistant.knowledge.release.httpx.Client",
        lambda **kwargs: original_client(transport=transport, **kwargs),
    )
    snapshots = HttpSnapshotTransport("https://qdrant.example", api_key="release-key")

    assert snapshots.server_version() == "1.20.0"
    description = snapshots.create("finance/name")
    assert description == SnapshotDescription(
        name="snapshot/name", checksum=digest, size_bytes=len(snapshot_bytes)
    )
    snapshot_path = tmp_path / "snapshot"
    assert snapshots.download("finance/name", description.name, snapshot_path) == digest
    assert snapshot_path.read_bytes() == snapshot_bytes
    snapshots.delete("finance/name", description.name)
    snapshots.upload("finance/name", snapshot_path, digest)
    assert calls == [
        ("GET", "/"),
        ("POST", "/collections/finance%2Fname/snapshots"),
        ("GET", "/collections/finance%2Fname/snapshots/snapshot%2Fname"),
        ("DELETE", "/collections/finance%2Fname/snapshots/snapshot%2Fname"),
        ("POST", "/collections/finance%2Fname/snapshots/upload"),
    ]


def test_runtime_permission_probe_removes_probe_and_fails_if_runtime_can_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_client = httpx.Client
    deleted: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json={"status": "ok", "result": {"collections": []}})
        if request.method == "PUT":
            assert request.headers["api-key"] == "runtime-key"
            return httpx.Response(200, json={"status": "ok", "result": True})
        assert request.method == "DELETE"
        assert request.headers["api-key"] == "release-key"
        deleted.append(request.url.path)
        return httpx.Response(200, json={"status": "ok", "result": True})

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        "ai_finance_assistant.knowledge.release.httpx.Client",
        lambda **kwargs: original_client(transport=transport, **kwargs),
    )

    with pytest.raises(PermissionError, match="runtime Qdrant key accepted a write"):
        HttpRuntimePermissionProbe(
            "https://qdrant.example", "runtime-key", "release-key"
        ).prove_read_only()

    assert len(deleted) == 1
    assert deleted[0].startswith("/collections/aifa_runtime_permission_probe_")


@pytest.mark.parametrize("status_code", [401, 403])
def test_release_key_revocation_probe_accepts_only_authentication_rejection(
    monkeypatch: pytest.MonkeyPatch, status_code: int
) -> None:
    original_client = httpx.Client
    transport = httpx.MockTransport(lambda request: httpx.Response(status_code, request=request))
    monkeypatch.setattr(
        "ai_finance_assistant.knowledge.release.httpx.Client",
        lambda **kwargs: original_client(transport=transport, **kwargs),
    )

    assert (
        ReleaseKeyRevocationProbe("https://qdrant.example", "revoked-key").verify() == status_code
    )


def test_release_key_revocation_probe_fails_while_key_remains_valid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_client = httpx.Client
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, request=request, json={"status": "ok"})
    )
    monkeypatch.setattr(
        "ai_finance_assistant.knowledge.release.httpx.Client",
        lambda **kwargs: original_client(transport=transport, **kwargs),
    )

    with pytest.raises(PermissionError, match="release key is still accepted"):
        ReleaseKeyRevocationProbe("https://qdrant.example", "valid-key").verify()
