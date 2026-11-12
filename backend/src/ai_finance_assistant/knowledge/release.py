"""Snapshot-based release of qualified knowledge collections to deployed Qdrant."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, Protocol, cast
from urllib.parse import quote

import httpx
from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from ai_finance_assistant.knowledge.evaluation import evaluate_candidate, qrels_checksum
from ai_finance_assistant.knowledge.models import (
    CollectionCompatibility,
    CollectionManifest,
    EvaluationCase,
    EvaluationReport,
    Evidence,
    LogicalKnowledgeBase,
    RetrievalQuery,
    SparseEmbedding,
)
from ai_finance_assistant.knowledge.qdrant_store import QdrantKnowledgeStore
from ai_finance_assistant.knowledge.representations import FastEmbedEncoder, RepresentationEncoder
from ai_finance_assistant.knowledge.retrieval import KnowledgeRetriever
from ai_finance_assistant.knowledge.store import ActivationResult, KnowledgeStore

_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_CONTRACT = _REPO_ROOT / "contracts/deployment/knowledge-release.v1.json"
_DEFAULT_EVIDENCE_DIR = _REPO_ROOT / "backend/artifacts/knowledge/deployment"
_FORBIDDEN_PROVIDER_ENVIRONMENT = frozenset(
    {
        "AIFA_ALPHA_VANTAGE_API_KEY",
        "AIFA_ALPHA_VANTAGE_TERMS_APPROVED",
        "AIFA_MASSIVE_API_KEY",
        "AIFA_MASSIVE_TERMS_APPROVED",
        "AIFA_OPENAI_API_KEY",
        "AIFA_OPENAI_TERMS_APPROVED",
        "AIFA_TAVILY_API_KEY",
        "AIFA_TAVILY_TERMS_APPROVED",
        "OPENAI_API_KEY",
    }
)


class EndpointContract(BaseModel):
    """Non-secret connection metadata for one side of the release."""

    model_config = ConfigDict(extra="allow", frozen=True)

    endpoint: HttpUrl
    qdrant_version: str


class CredentialContract(BaseModel):
    """Secret identifier and intended permission, never the credential payload."""

    model_config = ConfigDict(extra="allow", frozen=True)

    secret_id: str
    qdrant_access: str


class CredentialSetContract(BaseModel):
    """The separate runtime and offline release credential contracts."""

    model_config = ConfigDict(extra="allow", frozen=True)

    runtime: CredentialContract
    release: CredentialContract
    payloads_allowed_in_repository: bool
    payloads_allowed_in_github: bool
    payloads_managed_by_terraform: bool


class CollectionReleaseContract(BaseModel):
    """Exact current and rollback collections for one logical knowledge base."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    logical_kb: LogicalKnowledgeBase
    alias: str
    current_collection: str
    rollback_collection: str
    current_manifest: Path
    rollback_manifest: Path
    qrels: Path
    baseline_evaluation: Path
    expected_current_points: int = Field(gt=0)


class ProviderBoundaryContract(BaseModel):
    """Provider posture that the deployed knowledge release must not broaden."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider_mode: str
    model_mode: str
    live_provider_secrets_allowed: bool
    live_provider_activation: str
    viewer_live_provider_access: str


class KnowledgeReleaseContract(BaseModel):
    """Machine-readable input for a deployed shared-knowledge release."""

    model_config = ConfigDict(extra="allow", frozen=True)

    schema_version: str
    status: str
    source: EndpointContract
    target: EndpointContract
    credentials: CredentialSetContract
    collections: tuple[CollectionReleaseContract, ...]
    provider_boundary: ProviderBoundaryContract


@dataclass(frozen=True)
class SnapshotDescription:
    """Metadata returned by Qdrant after creating a collection snapshot."""

    name: str
    checksum: str | None
    size_bytes: int | None


class ReleaseStore(Protocol):
    """Qdrant operations needed by the release orchestrator."""

    def get_manifest(self, collection_name: str) -> CollectionManifest | None: ...

    def count_points(self, collection_name: str) -> int: ...

    def validate_collection(
        self, collection_name: str, expected: CollectionCompatibility
    ) -> tuple[bool, str]: ...

    def activate(self, alias: str, collection_name: str) -> ActivationResult: ...

    def resolve_alias(self, alias: str) -> str | None: ...

    def search(
        self,
        collection_name: str,
        query: RetrievalQuery,
        dense: Sequence[float],
        sparse: SparseEmbedding,
    ) -> tuple[Evidence, ...]: ...


class SnapshotTransport(Protocol):
    """Snapshot transport boundary used by real HTTP and deterministic fakes."""

    def server_version(self) -> str: ...

    def create(self, collection_name: str) -> SnapshotDescription: ...

    def download(self, collection_name: str, snapshot_name: str, destination: Path) -> str: ...

    def delete(self, collection_name: str, snapshot_name: str) -> None: ...

    def upload(self, collection_name: str, snapshot_path: Path, checksum: str) -> None: ...


class RuntimePermissionProbe(Protocol):
    """Proves that the runtime credential reads but cannot mutate Qdrant."""

    def prove_read_only(self) -> dict[str, Any]: ...


def _json_result(response: httpx.Response) -> Any:
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or payload.get("status") != "ok":
        raise ValueError("Qdrant returned a malformed or unsuccessful response")
    return payload.get("result")


class HttpSnapshotTransport:
    """Transfer collection snapshots through Qdrant's authenticated HTTP API."""

    def __init__(self, endpoint: str, *, api_key: str | None = None, timeout: float = 300.0):
        headers = {} if api_key is None else {"api-key": api_key}
        self._client = httpx.Client(base_url=endpoint.rstrip("/"), headers=headers, timeout=timeout)

    @staticmethod
    def _collection_path(collection_name: str) -> str:
        return f"/collections/{quote(collection_name, safe='')}"

    def server_version(self) -> str:
        response = self._client.get("/")
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("version"), str):
            raise ValueError("Qdrant root response did not include a version")
        return cast(str, payload["version"])

    def create(self, collection_name: str) -> SnapshotDescription:
        result = _json_result(
            self._client.post(
                f"{self._collection_path(collection_name)}/snapshots", params={"wait": "true"}
            )
        )
        if not isinstance(result, dict) or not isinstance(result.get("name"), str):
            raise ValueError("Qdrant snapshot response did not include a name")
        checksum = result.get("checksum")
        size = result.get("size")
        return SnapshotDescription(
            name=cast(str, result["name"]),
            checksum=checksum if isinstance(checksum, str) else None,
            size_bytes=size if isinstance(size, int) else None,
        )

    def download(self, collection_name: str, snapshot_name: str, destination: Path) -> str:
        digest = sha256()
        path = f"{self._collection_path(collection_name)}/snapshots/{quote(snapshot_name, safe='')}"
        with self._client.stream("GET", path) as response:
            response.raise_for_status()
            with destination.open("wb") as snapshot_file:
                for chunk in response.iter_bytes():
                    snapshot_file.write(chunk)
                    digest.update(chunk)
        return digest.hexdigest()

    def delete(self, collection_name: str, snapshot_name: str) -> None:
        result = _json_result(
            self._client.delete(
                f"{self._collection_path(collection_name)}/snapshots/"
                f"{quote(snapshot_name, safe='')}",
                params={"wait": "true"},
            )
        )
        if result is not True:
            raise ValueError("Qdrant did not confirm snapshot deletion")

    def upload(self, collection_name: str, snapshot_path: Path, checksum: str) -> None:
        with snapshot_path.open("rb") as snapshot_file:
            result = _json_result(
                self._client.post(
                    f"{self._collection_path(collection_name)}/snapshots/upload",
                    params={"wait": "true", "priority": "snapshot", "checksum": checksum},
                    files={
                        "snapshot": (
                            snapshot_path.name,
                            snapshot_file,
                            "application/octet-stream",
                        )
                    },
                )
            )
        if result is not True:
            raise ValueError("Qdrant did not confirm snapshot recovery")


class HttpRuntimePermissionProbe:
    """Use a disposable collection name to prove that runtime writes are forbidden."""

    def __init__(self, endpoint: str, runtime_api_key: str, release_api_key: str):
        base_url = endpoint.rstrip("/")
        self._runtime = httpx.Client(
            base_url=base_url, headers={"api-key": runtime_api_key}, timeout=30.0
        )
        self._release = httpx.Client(
            base_url=base_url, headers={"api-key": release_api_key}, timeout=30.0
        )

    def prove_read_only(self) -> dict[str, Any]:
        read_response = self._runtime.get("/collections")
        read_response.raise_for_status()
        probe_suffix = sha256(str(datetime.now(UTC)).encode()).hexdigest()[:12]
        probe_name = f"aifa_runtime_permission_probe_{probe_suffix}"
        write_response = self._runtime.put(
            f"/collections/{probe_name}",
            params={"wait": "true"},
            json={"vectors": {"size": 2, "distance": "Cosine"}},
        )
        if write_response.status_code == 403:
            return {"read_status": read_response.status_code, "write_status": 403, "passed": True}
        if write_response.is_success:
            cleanup_response = self._release.delete(
                f"/collections/{probe_name}", params={"wait": "true"}
            )
            cleanup_response.raise_for_status()
            raise PermissionError(
                "runtime Qdrant key accepted a write; the probe collection was removed"
            )
        write_response.raise_for_status()
        raise AssertionError("unreachable")


class ReleaseKeyRevocationProbe:
    """Verify that Qdrant rejects the formerly valid release key."""

    def __init__(self, endpoint: str, release_api_key: str):
        self._client = httpx.Client(
            base_url=endpoint.rstrip("/"), headers={"api-key": release_api_key}, timeout=30.0
        )

    def verify(self) -> int:
        response = self._client.get("/collections")
        if response.status_code not in {401, 403}:
            raise PermissionError(
                "release key is still accepted by Qdrant; revoke it before continuing"
            )
        return response.status_code


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _read_api_key(path: Path) -> str:
    value = path.read_text(encoding="utf-8").strip()
    if not value or any(character.isspace() for character in value):
        raise ValueError("Qdrant API key input must contain one non-empty token")
    return value


def _resolve(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def _manifest(path: Path) -> CollectionManifest:
    payload = _read_json(path)
    if not isinstance(payload, dict) or not isinstance(payload.get("manifest"), dict):
        raise ValueError(f"manifest artifact is invalid: {path}")
    return CollectionManifest.model_validate(payload["manifest"])


def _qrels(path: Path) -> tuple[EvaluationCase, ...]:
    payload = _read_json(path)
    if not isinstance(payload, list):
        raise ValueError(f"qrels artifact is invalid: {path}")
    return tuple(EvaluationCase.model_validate(item) for item in payload)


def _compatibility(manifest: CollectionManifest) -> CollectionCompatibility:
    return CollectionCompatibility(
        schema_version=manifest.schema_version,
        logical_kb=manifest.logical_kb,
        dense_model_id=manifest.dense_model_id,
        dense_model_revision=manifest.dense_model_revision,
        dense_artifact_sha256=manifest.dense_artifact_sha256,
        dense_dimensions=manifest.dense_dimensions,
        dense_vector_name=manifest.dense_vector_name,
        sparse_model_id=manifest.sparse_model_id,
        sparse_model_revision=manifest.sparse_model_revision,
        sparse_artifact_sha256=manifest.sparse_artifact_sha256,
        sparse_vector_name=manifest.sparse_vector_name,
        chunking_policy_version=manifest.chunking_policy.version,
    )


def _manifest_match(actual: CollectionManifest, expected: CollectionManifest) -> tuple[bool, str]:
    """Match collection identity while recognizing one Git-confirmed artifact relocation."""

    if actual == expected:
        return True, "exact"

    evaluation_name = f"{expected.collection_name}.evaluation.json"
    expected_capability_path = (
        f"artifacts/knowledge/{expected.logical_kb.value.replace('_', '-')}/{evaluation_name}"
    )
    approved_legacy_path = f"artifacts/m1/{evaluation_name}"
    if (
        expected.evaluation_artifact != expected_capability_path
        or actual.evaluation_artifact != approved_legacy_path
    ):
        return False, "conflict"
    relocated = actual.model_copy(update={"evaluation_artifact": expected.evaluation_artifact})
    if relocated != expected:
        return False, "conflict"
    return (
        True,
        "approved_evaluation_artifact_path_relocation"
        f"({approved_legacy_path}->{expected_capability_path})",
    )


def _git_revision(repo_root: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _deployed_provider_boundary(path: Path) -> dict[str, Any]:
    """Validate the non-secret Cloud Run environment against the approved provider posture."""

    payload = _read_json(path)
    try:
        containers = payload["spec"]["template"]["spec"]["containers"]
    except (KeyError, TypeError) as error:
        raise ValueError("Cloud Run description has no container specification") from error
    if not isinstance(containers, list):
        raise ValueError("Cloud Run container specification is invalid")
    backend = [
        item for item in containers if isinstance(item, dict) and item.get("name") == "backend"
    ]
    if len(backend) != 1:
        raise ValueError("Cloud Run description must contain exactly one backend container")
    environment = backend[0].get("env", [])
    if not isinstance(environment, list):
        raise ValueError("Cloud Run backend environment is invalid")
    names = {
        cast(str, item["name"]).upper()
        for item in environment
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    forbidden = sorted(names & _FORBIDDEN_PROVIDER_ENVIRONMENT)
    if forbidden:
        raise ValueError(
            "deployed backend contains forbidden live-provider environment names: "
            + ", ".join(forbidden)
        )
    values = {
        cast(str, item["name"]): item.get("value")
        for item in environment
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    if values.get("AIFA_PROVIDER_MODE") != "credential_free":
        raise ValueError("deployed provider mode is not credential_free")
    if values.get("AIFA_MODEL_MODE") != "credential_free":
        raise ValueError("deployed model mode is not credential_free")
    return {
        "service": "aifa-staging-backend",
        "provider_mode": "credential_free",
        "model_mode": "credential_free",
        "forbidden_provider_environment_names_present": False,
        "passed": True,
    }


class KnowledgeRelease:
    """Validate, transfer, evaluate, activate, and rollback shared knowledge."""

    def __init__(
        self,
        *,
        contract: KnowledgeReleaseContract,
        repo_root: Path,
        source_store: ReleaseStore,
        target_release_store: ReleaseStore,
        target_runtime_store: ReleaseStore,
        source_snapshots: SnapshotTransport,
        target_snapshots: SnapshotTransport,
        permission_probe: RuntimePermissionProbe,
        encoder: RepresentationEncoder,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._contract = contract
        self._repo_root = repo_root
        self._source_store = source_store
        self._target_release_store = target_release_store
        self._target_runtime_store = target_runtime_store
        self._source_snapshots = source_snapshots
        self._target_snapshots = target_snapshots
        self._permission_probe = permission_probe
        self._encoder = encoder
        self._clock = clock

    def _validate_provider_boundary(self) -> None:
        boundary = self._contract.provider_boundary
        if (
            boundary.provider_mode != "credential_free"
            or boundary.model_mode != "credential_free"
            or boundary.live_provider_secrets_allowed
            or boundary.viewer_live_provider_access != "denied"
        ):
            raise ValueError("knowledge release cannot broaden the approved provider boundary")

    @staticmethod
    def _validate_collection(
        store: ReleaseStore, collection_name: str, expected: CollectionManifest
    ) -> str:
        actual = store.get_manifest(collection_name)
        if actual is None:
            raise ValueError(f"collection is missing: {collection_name}")
        manifest_matches, manifest_detail = _manifest_match(actual, expected)
        if not manifest_matches:
            raise ValueError(f"collection manifest conflicts with artifact: {collection_name}")
        actual_points = store.count_points(collection_name)
        if actual_points != expected.point_count:
            raise ValueError(
                f"collection point count mismatch for {collection_name}: "
                f"expected {expected.point_count}, got {actual_points}"
            )
        compatible, detail = store.validate_collection(collection_name, _compatibility(expected))
        if not compatible:
            raise ValueError(detail)
        return f"{detail}; manifest_match={manifest_detail}"

    def _transfer_one(
        self, collection_name: str, expected: CollectionManifest, temporary_dir: Path
    ) -> dict[str, Any]:
        source_detail = self._validate_collection(self._source_store, collection_name, expected)
        if self._target_release_store.get_manifest(collection_name) is not None:
            target_detail = self._validate_collection(
                self._target_release_store, collection_name, expected
            )
            return {
                "collection": collection_name,
                "action": "validated_existing",
                "source_validation": source_detail,
                "target_validation": target_detail,
                "point_count": expected.point_count,
            }

        snapshot = self._source_snapshots.create(collection_name)
        snapshot_path = temporary_dir / snapshot.name
        try:
            checksum = self._source_snapshots.download(
                collection_name, snapshot.name, snapshot_path
            )
            if snapshot.checksum is not None and snapshot.checksum != checksum:
                raise ValueError(f"snapshot checksum mismatch for {collection_name}")
            self._target_snapshots.upload(collection_name, snapshot_path, checksum)
        finally:
            self._source_snapshots.delete(collection_name, snapshot.name)
        target_detail = self._validate_collection(
            self._target_release_store, collection_name, expected
        )
        return {
            "collection": collection_name,
            "action": "uploaded_snapshot",
            "snapshot_sha256": checksum,
            "snapshot_size_bytes": snapshot_path.stat().st_size,
            "source_validation": source_detail,
            "target_validation": target_detail,
            "point_count": expected.point_count,
        }

    def _evaluate(self, spec: CollectionReleaseContract) -> EvaluationReport:
        qrels_path = _resolve(self._repo_root, spec.qrels)
        baseline_path = _resolve(self._repo_root, spec.baseline_evaluation)
        cases = _qrels(qrels_path)
        baseline = EvaluationReport.model_validate(_read_json(baseline_path))
        if qrels_checksum(cases) != baseline.qrels_checksum or not baseline.passed:
            raise ValueError(f"baseline evaluation is not current and passing: {baseline_path}")
        retriever = KnowledgeRetriever(
            store=cast(KnowledgeStore, self._target_runtime_store), encoder=self._encoder
        )
        report = evaluate_candidate(
            logical_kb=spec.logical_kb,
            collection_name=spec.current_collection,
            cases=cases,
            retriever=retriever,
            minimum_hybrid_recall_at_5=baseline.minimum_hybrid_recall_at_5,
        )
        if not report.passed or report.qrels_checksum != baseline.qrels_checksum:
            raise ValueError(f"remote retrieval evaluation failed: {spec.logical_kb.value}")
        return report

    def execute(self, *, revision: str, contract_sha256: str) -> dict[str, Any]:
        self._validate_provider_boundary()
        source_version = self._source_snapshots.server_version()
        target_version = self._target_snapshots.server_version()
        if source_version != self._contract.source.qdrant_version:
            raise ValueError("local Qdrant version does not match the release contract")
        if target_version != self._contract.target.qdrant_version:
            raise ValueError("target Qdrant version does not match the release contract")
        manifests: dict[str, CollectionManifest] = {}
        for spec in self._contract.collections:
            current = _manifest(_resolve(self._repo_root, spec.current_manifest))
            rollback = _manifest(_resolve(self._repo_root, spec.rollback_manifest))
            if current.collection_name != spec.current_collection:
                raise ValueError("current manifest path does not match the release contract")
            if rollback.collection_name != spec.rollback_collection:
                raise ValueError("rollback manifest path does not match the release contract")
            if current.point_count != spec.expected_current_points:
                raise ValueError("current point count does not match the release contract")
            manifests[current.collection_name] = current
            manifests[rollback.collection_name] = rollback

        transfers: list[dict[str, Any]] = []
        with tempfile.TemporaryDirectory(prefix="aifa-knowledge-release-") as temporary:
            temporary_dir = Path(temporary)
            for spec in self._contract.collections:
                for collection_name in (spec.current_collection, spec.rollback_collection):
                    transfers.append(
                        self._transfer_one(
                            collection_name, manifests[collection_name], temporary_dir
                        )
                    )

        evaluations = [
            self._evaluate(spec).model_dump(mode="json") for spec in self._contract.collections
        ]

        activations: list[dict[str, Any]] = []
        for spec in self._contract.collections:
            result = self._target_release_store.activate(spec.alias, spec.current_collection)
            if self._target_release_store.resolve_alias(spec.alias) != spec.current_collection:
                raise ValueError(f"current alias activation failed: {spec.alias}")
            activations.append(
                {
                    "alias": result.alias,
                    "active_collection": result.active_collection,
                    "previous_collection": result.previous_collection,
                }
            )

        rollback_proofs: list[dict[str, Any]] = []
        for spec in self._contract.collections:
            rollback_result = self._target_release_store.activate(
                spec.alias, spec.rollback_collection
            )
            if self._target_release_store.resolve_alias(spec.alias) != spec.rollback_collection:
                raise ValueError(f"rollback alias activation failed: {spec.alias}")
            restore_result = self._target_release_store.activate(
                spec.alias, spec.current_collection
            )
            if self._target_release_store.resolve_alias(spec.alias) != spec.current_collection:
                raise ValueError(f"current alias restoration failed: {spec.alias}")
            rollback_proofs.append(
                {
                    "alias": spec.alias,
                    "rollback_collection": rollback_result.active_collection,
                    "restored_collection": restore_result.active_collection,
                    "passed": True,
                }
            )

        runtime_validation: list[dict[str, Any]] = []
        for spec in self._contract.collections:
            compatible, detail = self._target_runtime_store.validate_collection(
                spec.current_collection, _compatibility(manifests[spec.current_collection])
            )
            if (
                not compatible
                or self._target_runtime_store.resolve_alias(spec.alias) != spec.current_collection
            ):
                raise ValueError(f"runtime collection validation failed: {detail}")
            runtime_validation.append(
                {"alias": spec.alias, "collection": spec.current_collection, "detail": detail}
            )
        runtime_permission = self._permission_probe.prove_read_only()
        if not runtime_permission.get("passed"):
            raise PermissionError("runtime Qdrant credential is not read-only")

        recorded_at = self._clock()
        return {
            "schema_version": "1",
            "status": "qualified_release_key_revocation_pending",
            "recorded_at": recorded_at.isoformat(),
            "revision": revision,
            "contract_sha256": contract_sha256,
            "target": {
                "endpoint": str(self._contract.target.endpoint),
                "qdrant_version": target_version,
            },
            "source_qdrant_version": source_version,
            "transfers": transfers,
            "evaluations": evaluations,
            "activations": activations,
            "rollback_proofs": rollback_proofs,
            "runtime_validation": runtime_validation,
            "runtime_permission": runtime_permission,
            "release_key": {"qdrant_revoked": False, "secret_version_destroyed": False},
            "provider_boundary": self._contract.provider_boundary.model_dump(mode="json"),
            "secret_payloads_recorded": False,
        }


def _load_contract(path: Path) -> KnowledgeReleaseContract:
    contract = KnowledgeReleaseContract.model_validate(_read_json(path))
    if (
        contract.schema_version != "1"
        or contract.status != "defined_not_executed"
        or len(contract.collections) != 2
    ):
        raise ValueError("unsupported or incomplete knowledge-release contract")
    return contract


def _execute(args: argparse.Namespace) -> int:
    contract_path = args.contract.resolve()
    contract = _load_contract(contract_path)
    deployed_boundary = _deployed_provider_boundary(args.backend_service_description)
    release_key = _read_api_key(args.release_api_key_file)
    runtime_key = _read_api_key(args.runtime_api_key_file)
    target_endpoint = str(contract.target.endpoint)
    release_store = QdrantKnowledgeStore(target_endpoint, api_key=release_key, timeout_seconds=30)
    runtime_store = QdrantKnowledgeStore(target_endpoint, api_key=runtime_key, timeout_seconds=30)
    release = KnowledgeRelease(
        contract=contract,
        repo_root=args.repo_root.resolve(),
        source_store=QdrantKnowledgeStore(str(contract.source.endpoint), timeout_seconds=30),
        target_release_store=release_store,
        target_runtime_store=runtime_store,
        source_snapshots=HttpSnapshotTransport(str(contract.source.endpoint)),
        target_snapshots=HttpSnapshotTransport(target_endpoint, api_key=release_key),
        permission_probe=HttpRuntimePermissionProbe(target_endpoint, runtime_key, release_key),
        encoder=FastEmbedEncoder(),
    )
    evidence = release.execute(
        revision=_git_revision(args.repo_root),
        contract_sha256=sha256(contract_path.read_bytes()).hexdigest(),
    )
    evidence["deployed_provider_boundary"] = deployed_boundary
    evidence_path = args.evidence_path.resolve()
    _write_json(evidence_path, evidence)
    print(json.dumps({"evidence_path": str(evidence_path), "status": evidence["status"]}))
    return 0


def _finalize_revocation(args: argparse.Namespace) -> int:
    evidence_path = args.evidence_path.resolve()
    evidence = _read_json(evidence_path)
    if not isinstance(evidence, dict) or evidence.get("status") != (
        "qualified_release_key_revocation_pending"
    ):
        raise ValueError("release evidence is not awaiting key revocation")
    contract = _load_contract(args.contract.resolve())
    status_code = ReleaseKeyRevocationProbe(
        str(contract.target.endpoint), _read_api_key(args.release_api_key_file)
    ).verify()
    evidence["release_key"] = {
        "qdrant_revoked": True,
        "qdrant_rejection_status": status_code,
        "secret_version_destroyed": False,
    }
    evidence["status"] = "qualified_release_secret_cleanup_pending"
    _write_json(evidence_path, evidence)
    print(json.dumps({"evidence_path": str(evidence_path), "status": evidence["status"]}))
    return 0


def _record_secret_destroyed(args: argparse.Namespace) -> int:
    evidence_path = args.evidence_path.resolve()
    evidence = _read_json(evidence_path)
    if not isinstance(evidence, dict) or evidence.get("status") != (
        "qualified_release_secret_cleanup_pending"
    ):
        raise ValueError("release evidence is not awaiting Secret Manager cleanup")
    release_key = evidence.get("release_key")
    if not isinstance(release_key, dict) or release_key.get("qdrant_revoked") is not True:
        raise ValueError("Qdrant release-key revocation has not been verified")
    release_key["secret_version_destroyed"] = True
    evidence["status"] = "qualified"
    _write_json(evidence_path, evidence)
    print(json.dumps({"evidence_path": str(evidence_path), "status": evidence["status"]}))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=_REPO_ROOT)
    parser.add_argument("--contract", type=Path, default=_DEFAULT_CONTRACT)
    subparsers = parser.add_subparsers(dest="command", required=True)

    execute = subparsers.add_parser(
        "execute", help="transfer, qualify, activate, and prove rollback"
    )
    execute.add_argument("--release-api-key-file", type=Path, required=True)
    execute.add_argument("--runtime-api-key-file", type=Path, required=True)
    execute.add_argument("--backend-service-description", type=Path, required=True)
    execute.add_argument(
        "--evidence-path",
        type=Path,
        default=_DEFAULT_EVIDENCE_DIR / "staging-release.json",
    )
    execute.set_defaults(handler=_execute)

    finalize = subparsers.add_parser(
        "finalize-revocation", help="verify Qdrant rejects the release key"
    )
    finalize.add_argument("--release-api-key-file", type=Path, required=True)
    finalize.add_argument("--evidence-path", type=Path, required=True)
    finalize.set_defaults(handler=_finalize_revocation)

    cleanup = subparsers.add_parser(
        "record-secret-destroyed", help="complete evidence after Secret Manager cleanup"
    )
    cleanup.add_argument("--evidence-path", type=Path, required=True)
    cleanup.set_defaults(handler=_record_secret_destroyed)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
