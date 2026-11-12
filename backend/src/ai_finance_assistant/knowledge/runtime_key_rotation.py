"""Qualify and record a focused Qdrant runtime-key rotation."""

from __future__ import annotations

import argparse
import copy
import json
import subprocess
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, Protocol, cast

import httpx
from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from ai_finance_assistant.knowledge.models import (
    CollectionCompatibility,
    CollectionManifest,
    LogicalKnowledgeBase,
)
from ai_finance_assistant.knowledge.qdrant_store import QdrantKnowledgeStore
from ai_finance_assistant.knowledge.release import (
    ReleaseKeyRevocationProbe,
    _compatibility,
    _deployed_provider_boundary,
    _manifest,
    _manifest_match,
    _read_api_key,
    _read_json,
    _write_json,
)

_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_CONTRACT = _REPO_ROOT / "contracts/deployment/runtime-key-rotation.v1.json"
_ANONYMOUS_MEMBERS = frozenset({"allUsers", "allAuthenticatedUsers"})


class TargetContract(BaseModel):
    """Non-secret Qdrant target metadata."""

    model_config = ConfigDict(extra="allow", frozen=True)

    endpoint: HttpUrl
    qdrant_version: str


class CredentialContract(BaseModel):
    """The intended runtime credential boundary."""

    model_config = ConfigDict(extra="allow", frozen=True)

    secret_id: str
    qdrant_access: str


class DeploymentContract(BaseModel):
    """The one deployment resource that a rotation may update."""

    model_config = ConfigDict(extra="allow", frozen=True)

    backend_service: str
    terraform_resource: str
    allowed_plan_actions: tuple[str, ...]
    github_secret_version_variable: str
    ingress: str
    default_url_disabled: bool
    anonymous_invoker_allowed: bool


class CollectionContract(BaseModel):
    """One active shared-knowledge collection expected by the runtime."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    logical_kb: LogicalKnowledgeBase
    alias: str
    current_collection: str
    current_manifest: Path
    expected_current_points: int = Field(gt=0)


class ProviderBoundaryContract(BaseModel):
    """The provider posture that rotation must leave unchanged."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider_mode: str
    model_mode: str
    live_provider_secrets_allowed: bool
    live_provider_activation: str
    viewer_live_provider_access: str


class RuntimeKeyRotationContract(BaseModel):
    """Machine-readable rotation input."""

    model_config = ConfigDict(extra="allow", frozen=True)

    schema_version: str
    status: str
    target: TargetContract
    credential: CredentialContract
    deployment: DeploymentContract
    collections: tuple[CollectionContract, ...]
    provider_boundary: ProviderBoundaryContract


class RotationStore(Protocol):
    """Read operations used to qualify a replacement key."""

    def get_manifest(self, collection_name: str) -> CollectionManifest | None: ...

    def count_points(self, collection_name: str) -> int: ...

    def validate_collection(
        self, collection_name: str, expected: CollectionCompatibility
    ) -> tuple[bool, str]: ...

    def resolve_alias(self, alias: str) -> str | None: ...


class VersionProbe(Protocol):
    """Read the Qdrant server version with the replacement key."""

    def server_version(self) -> str: ...


class PermissionProbe(Protocol):
    """Prove the replacement key reads and cannot mutate Qdrant."""

    def prove_read_only(self) -> dict[str, Any]: ...


class HttpVersionProbe:
    """Read the target Qdrant version through its authenticated root endpoint."""

    def __init__(self, endpoint: str, api_key: str):
        self._client = httpx.Client(
            base_url=endpoint.rstrip("/"), headers={"api-key": api_key}, timeout=30.0
        )

    def server_version(self) -> str:
        response = self._client.get("/")
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("version"), str):
            raise ValueError("Qdrant root response did not include a version")
        return cast(str, payload["version"])


class NonMutatingRuntimePermissionProbe:
    """Prove write denial by deleting a unique collection already proven absent."""

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        *,
        probe_name: str | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self._client = client or httpx.Client(
            base_url=endpoint.rstrip("/"), headers={"api-key": api_key}, timeout=30.0
        )
        self._probe_name = probe_name or f"aifa_runtime_rotation_probe_{uuid.uuid4().hex}"

    def prove_read_only(self) -> dict[str, Any]:
        read_response = self._client.get("/collections")
        read_response.raise_for_status()
        absence_response = self._client.get(f"/collections/{self._probe_name}")
        if absence_response.status_code != 404:
            raise RuntimeError("the non-mutating permission-probe collection was not absent")
        write_response = self._client.delete(f"/collections/{self._probe_name}")
        if write_response.status_code != 403:
            raise PermissionError(
                "replacement runtime key did not deny the non-mutating delete probe with HTTP 403"
            )
        return {
            "read_status": read_response.status_code,
            "absence_status": absence_response.status_code,
            "write_status": write_response.status_code,
            "probe": "delete_unique_confirmed_absent_collection",
            "passed": True,
        }


@dataclass(frozen=True)
class TerraformPlanScope:
    """Reduced, non-secret statement of the accepted Terraform change."""

    resource: str
    actions: tuple[str, ...]
    old_secret_version: str
    new_secret_version: str


def _load_contract(path: Path) -> RuntimeKeyRotationContract:
    return RuntimeKeyRotationContract.model_validate(_read_json(path))


def _positive_version(value: str, *, label: str) -> str:
    if not value.isdecimal() or int(value) < 1:
        raise ValueError(f"{label} must be a positive numeric Secret Manager version")
    return value


def _secret_reference(environment: Any) -> tuple[str, str]:
    if not isinstance(environment, list):
        raise ValueError("backend environment is invalid")
    matches = [
        item
        for item in environment
        if isinstance(item, dict) and item.get("name") == "AIFA_QDRANT_API_KEY"
    ]
    if len(matches) != 1:
        raise ValueError("backend must have exactly one AIFA_QDRANT_API_KEY reference")
    reference = matches[0].get("valueFrom", {}).get("secretKeyRef", {})
    if not isinstance(reference, dict):
        raise ValueError("backend Qdrant credential is not a Secret Manager reference")
    secret = reference.get("secret", reference.get("name"))
    version = reference.get("version", reference.get("key"))
    if not isinstance(secret, str) or not isinstance(version, str):
        raise ValueError("backend Qdrant Secret Manager reference is incomplete")
    return secret, version


def _terraform_secret_reference(resource: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    try:
        containers = resource["template"][0]["containers"]
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError("Terraform backend plan has no container specification") from error
    matches: list[dict[str, Any]] = []
    for container in containers:
        if not isinstance(container, dict):
            continue
        environment = container.get("env", [])
        if not isinstance(environment, list):
            continue
        matches.extend(
            item
            for item in environment
            if isinstance(item, dict) and item.get("name") == "AIFA_QDRANT_API_KEY"
        )
    if len(matches) != 1:
        raise ValueError("Terraform backend plan must contain one Qdrant secret reference")
    value_sources = matches[0].get("value_source")
    if not isinstance(value_sources, list) or len(value_sources) != 1:
        raise ValueError("Terraform backend Qdrant value_source is invalid")
    references = value_sources[0].get("secret_key_ref")
    if not isinstance(references, list) or len(references) != 1:
        raise ValueError("Terraform backend Qdrant secret_key_ref is invalid")
    reference = references[0]
    secret = reference.get("secret")
    version = reference.get("version")
    if not isinstance(secret, str) or not isinstance(version, str):
        raise ValueError("Terraform backend Qdrant secret reference is incomplete")
    return secret, version, reference


def _remove_unknown_values(before: Any, after: Any, unknown: Any) -> tuple[Any, Any]:
    """Remove provider-computed after-values before comparing managed configuration."""

    if unknown is True:
        return None, None
    if isinstance(unknown, dict) and isinstance(before, dict) and isinstance(after, dict):
        before_copy = copy.deepcopy(before)
        after_copy = copy.deepcopy(after)
        for key, marker in unknown.items():
            if marker is True:
                before_copy.pop(key, None)
                after_copy.pop(key, None)
            elif key in before_copy and key in after_copy:
                before_copy[key], after_copy[key] = _remove_unknown_values(
                    before_copy[key], after_copy[key], marker
                )
        return before_copy, after_copy
    if isinstance(unknown, list) and isinstance(before, list) and isinstance(after, list):
        if len(unknown) != len(before) or len(unknown) != len(after):
            raise ValueError("Terraform unknown-value shape does not match the backend resource")
        before_items: list[Any] = []
        after_items: list[Any] = []
        for before_item, after_item, marker in zip(before, after, unknown, strict=True):
            if marker is True:
                continue
            normalized_before, normalized_after = _remove_unknown_values(
                before_item, after_item, marker
            )
            before_items.append(normalized_before)
            after_items.append(normalized_after)
        return before_items, after_items
    return copy.deepcopy(before), copy.deepcopy(after)


def validate_terraform_plan(
    plan_path: Path,
    contract: RuntimeKeyRotationContract,
    *,
    old_version: str,
    new_version: str,
) -> TerraformPlanScope:
    """Require one in-place backend update whose only managed change is the secret version."""

    old_version = _positive_version(old_version, label="old version")
    new_version = _positive_version(new_version, label="new version")
    if old_version == new_version:
        raise ValueError("replacement secret version must differ from the deployed version")
    payload = _read_json(plan_path)
    if not isinstance(payload, dict):
        raise ValueError("Terraform plan JSON is invalid")
    changes = []
    for item in payload.get("resource_changes", []):
        if not isinstance(item, dict) or not isinstance(item.get("change"), dict):
            continue
        actions = item["change"].get("actions")
        if actions not in (["no-op"], ["read"]):
            changes.append(item)
    if len(changes) != 1:
        raise ValueError("rotation plan must contain exactly one managed resource change")
    change = changes[0]
    actions = change["change"].get("actions")
    if change.get("address") != contract.deployment.terraform_resource:
        raise ValueError("rotation plan changes a resource outside the backend service")
    if actions != list(contract.deployment.allowed_plan_actions):
        raise ValueError("rotation plan is not the approved in-place backend update")
    before = change["change"].get("before")
    after = change["change"].get("after")
    if not isinstance(before, dict) or not isinstance(after, dict):
        raise ValueError("rotation plan must have concrete before and after values")
    before_copy, after_copy = _remove_unknown_values(
        before, after, change["change"].get("after_unknown", {})
    )
    if not isinstance(before_copy, dict) or not isinstance(after_copy, dict):
        raise ValueError("Terraform backend plan normalization failed")
    before_secret, before_version, _ = _terraform_secret_reference(before_copy)
    after_secret, after_version, after_reference = _terraform_secret_reference(after_copy)
    if before_secret != contract.credential.secret_id or after_secret != before_secret:
        raise ValueError("rotation plan changes the approved Secret Manager resource")
    if before_version != old_version or after_version != new_version:
        raise ValueError("rotation plan does not contain the reviewed secret-version transition")
    after_reference["version"] = old_version
    if after_copy != before_copy:
        raise ValueError(
            "rotation plan changes backend fields other than the Qdrant secret version"
        )
    return TerraformPlanScope(
        resource=cast(str, change["address"]),
        actions=tuple(cast(list[str], actions)),
        old_secret_version=old_version,
        new_secret_version=new_version,
    )


class RuntimeKeyQualifier:
    """Validate a replacement runtime key before the backend consumes it."""

    def __init__(
        self,
        *,
        contract: RuntimeKeyRotationContract,
        repo_root: Path,
        store: RotationStore,
        version_probe: VersionProbe,
        permission_probe: PermissionProbe,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._contract = contract
        self._repo_root = repo_root
        self._store = store
        self._version_probe = version_probe
        self._permission_probe = permission_probe
        self._clock = clock

    def qualify(
        self,
        *,
        revision: str,
        contract_sha256: str,
        old_version: str,
        new_version: str,
    ) -> dict[str, Any]:
        old_version = _positive_version(old_version, label="old version")
        new_version = _positive_version(new_version, label="new version")
        if old_version == new_version:
            raise ValueError("replacement secret version must differ from the deployed version")
        target_version = self._version_probe.server_version()
        if target_version != self._contract.target.qdrant_version:
            raise ValueError(
                f"target Qdrant version mismatch: expected "
                f"{self._contract.target.qdrant_version}, got {target_version}"
            )
        collection_results: list[dict[str, Any]] = []
        for spec in self._contract.collections:
            expected = _manifest(self._repo_root / spec.current_manifest)
            actual = self._store.get_manifest(spec.current_collection)
            if actual is None:
                raise ValueError(f"runtime collection is missing: {spec.current_collection}")
            manifest_matches, manifest_detail = _manifest_match(actual, expected)
            compatible, compatibility_detail = self._store.validate_collection(
                spec.current_collection, _compatibility(expected)
            )
            point_count = self._store.count_points(spec.current_collection)
            active_collection = self._store.resolve_alias(spec.alias)
            if not manifest_matches or not compatible:
                raise ValueError(f"runtime collection is incompatible: {spec.current_collection}")
            if point_count != spec.expected_current_points:
                raise ValueError(
                    f"runtime collection point count changed: {spec.current_collection}"
                )
            if active_collection != spec.current_collection:
                raise ValueError(f"runtime alias is not active: {spec.alias}")
            collection_results.append(
                {
                    "alias": spec.alias,
                    "collection": spec.current_collection,
                    "point_count": point_count,
                    "manifest": manifest_detail,
                    "compatibility": compatibility_detail,
                    "passed": True,
                }
            )
        permission = self._permission_probe.prove_read_only()
        if not permission.get("passed") or permission.get("write_status") != 403:
            raise PermissionError("replacement Qdrant credential is not read-only")
        return {
            "schema_version": "1",
            "status": "qualified_cutover_pending",
            "recorded_at": self._clock().isoformat(),
            "revision": revision,
            "contract_sha256": contract_sha256,
            "rotation": {
                "old_secret_version": old_version,
                "new_secret_version": new_version,
            },
            "target": {
                "endpoint": str(self._contract.target.endpoint).rstrip("/"),
                "qdrant_version": target_version,
            },
            "collections": collection_results,
            "new_runtime_permission": permission,
            "terraform_plan": None,
            "deployed_backend": None,
            "github_variable": None,
            "old_runtime_key": {
                "qdrant_revoked": False,
                "secret_version_destroyed": False,
            },
            "provider_boundary": self._contract.provider_boundary.model_dump(mode="json"),
            "secret_payloads_recorded": False,
        }


def _deployed_backend(
    service_path: Path,
    iam_path: Path,
    contract: RuntimeKeyRotationContract,
    *,
    expected_image: str,
    new_version: str,
) -> dict[str, Any]:
    payload = _read_json(service_path)
    if not isinstance(payload, dict):
        raise ValueError("Cloud Run service description is invalid")
    metadata = payload.get("metadata", {})
    if (
        not isinstance(metadata, dict)
        or metadata.get("name") != contract.deployment.backend_service
    ):
        raise ValueError("Cloud Run description is not the contracted backend service")
    annotations = metadata.get("annotations", {})
    if not isinstance(annotations, dict):
        raise ValueError("Cloud Run service annotations are invalid")
    if annotations.get("run.googleapis.com/ingress") != contract.deployment.ingress:
        raise ValueError("backend ingress is not internal/load-balancer only")
    expected_disabled = "true" if contract.deployment.default_url_disabled else "false"
    if annotations.get("run.googleapis.com/default-url-disabled") != expected_disabled:
        raise ValueError("backend default Cloud Run URL is not disabled")
    status = payload.get("status", {})
    conditions = status.get("conditions", []) if isinstance(status, dict) else []
    if not any(
        isinstance(item, dict) and item.get("type") == "Ready" and item.get("status") == "True"
        for item in conditions
    ):
        raise ValueError("backend Cloud Run service is not Ready")
    try:
        containers = payload["spec"]["template"]["spec"]["containers"]
    except (KeyError, TypeError) as error:
        raise ValueError("Cloud Run description has no container specification") from error
    backend = [
        item for item in containers if isinstance(item, dict) and item.get("name") == "backend"
    ]
    if len(backend) != 1 or backend[0].get("image") != expected_image:
        raise ValueError("deployed backend image does not match the approved immutable image")
    secret, version = _secret_reference(backend[0].get("env"))
    if secret != contract.credential.secret_id or version != new_version:
        raise ValueError("deployed backend does not reference the replacement secret version")
    policy = _read_json(iam_path)
    if not isinstance(policy, dict):
        raise ValueError("Cloud Run IAM policy is invalid")
    members = {
        member
        for binding in policy.get("bindings", [])
        if isinstance(binding, dict)
        for member in binding.get("members", [])
        if isinstance(member, str)
    }
    anonymous = sorted(members & _ANONYMOUS_MEMBERS)
    if anonymous or contract.deployment.anonymous_invoker_allowed:
        raise ValueError("backend Cloud Run service permits anonymous invocation")
    provider = _deployed_provider_boundary(service_path)
    return {
        "service": contract.deployment.backend_service,
        "image": expected_image,
        "secret_id": secret,
        "secret_version": version,
        "ready": True,
        "ingress": contract.deployment.ingress,
        "default_url_disabled": True,
        "anonymous_invoker_absent": True,
        "provider_boundary": provider,
        "passed": True,
    }


def _git_revision(repo_root: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _qualify_new_key(args: argparse.Namespace) -> int:
    contract_path = args.contract.resolve()
    contract = _load_contract(contract_path)
    api_key = _read_api_key(args.runtime_api_key_file)
    endpoint = str(contract.target.endpoint).rstrip("/")
    qualifier = RuntimeKeyQualifier(
        contract=contract,
        repo_root=args.repo_root.resolve(),
        store=QdrantKnowledgeStore(endpoint, api_key=api_key, timeout_seconds=30),
        version_probe=HttpVersionProbe(endpoint, api_key),
        permission_probe=NonMutatingRuntimePermissionProbe(endpoint, api_key),
    )
    evidence_path = args.evidence_path.resolve()
    if evidence_path.exists():
        raise FileExistsError(f"rotation evidence already exists: {evidence_path}")
    evidence = qualifier.qualify(
        revision=_git_revision(args.repo_root),
        contract_sha256=sha256(contract_path.read_bytes()).hexdigest(),
        old_version=args.old_version,
        new_version=args.new_version,
    )
    _write_json(evidence_path, evidence)
    print(json.dumps({"evidence_path": str(evidence_path), "status": evidence["status"]}))
    return 0


def _validate_plan(args: argparse.Namespace) -> int:
    scope = validate_terraform_plan(
        args.plan_json.resolve(),
        _load_contract(args.contract.resolve()),
        old_version=args.old_version,
        new_version=args.new_version,
    )
    print(
        json.dumps(
            {
                "resource": scope.resource,
                "actions": list(scope.actions),
                "passed": True,
            },
            sort_keys=True,
        )
    )
    return 0


def _record_plan(args: argparse.Namespace) -> int:
    evidence_path = args.evidence_path.resolve()
    evidence = _read_json(evidence_path)
    if not isinstance(evidence, dict) or evidence.get("status") != "qualified_cutover_pending":
        raise ValueError("rotation evidence is not awaiting a cutover plan")
    rotation = evidence.get("rotation")
    if not isinstance(rotation, dict):
        raise ValueError("rotation evidence has no version transition")
    old_version = rotation.get("old_secret_version")
    new_version = rotation.get("new_secret_version")
    if not isinstance(old_version, str) or not isinstance(new_version, str):
        raise ValueError("rotation evidence has invalid secret versions")
    plan = validate_terraform_plan(
        args.plan_json.resolve(),
        _load_contract(args.contract.resolve()),
        old_version=old_version,
        new_version=new_version,
    )
    evidence["terraform_plan"] = {
        "resource": plan.resource,
        "actions": list(plan.actions),
        "only_qdrant_secret_version_changed": True,
        "passed": True,
    }
    evidence["status"] = "qualified_apply_pending"
    _write_json(evidence_path, evidence)
    print(json.dumps({"evidence_path": str(evidence_path), "status": evidence["status"]}))
    return 0


def _record_cutover(args: argparse.Namespace) -> int:
    evidence_path = args.evidence_path.resolve()
    evidence = _read_json(evidence_path)
    if not isinstance(evidence, dict) or evidence.get("status") != "qualified_apply_pending":
        raise ValueError("rotation evidence is not awaiting cutover")
    contract = _load_contract(args.contract.resolve())
    rotation = evidence.get("rotation")
    if not isinstance(rotation, dict):
        raise ValueError("rotation evidence has no version transition")
    old_version = rotation.get("old_secret_version")
    new_version = rotation.get("new_secret_version")
    if not isinstance(old_version, str) or not isinstance(new_version, str):
        raise ValueError("rotation evidence has invalid secret versions")
    plan = evidence.get("terraform_plan")
    if not isinstance(plan, dict) or plan.get("passed") is not True:
        raise ValueError("rotation evidence has no qualified Terraform plan")
    github_version = _positive_version(args.github_secret_version, label="GitHub variable")
    if github_version != new_version:
        raise ValueError("GitHub environment variable does not match the deployed secret version")
    deployed = _deployed_backend(
        args.backend_service_description.resolve(),
        args.backend_iam_policy.resolve(),
        contract,
        expected_image=args.expected_backend_image,
        new_version=new_version,
    )
    evidence["deployed_backend"] = deployed
    evidence["github_variable"] = {
        "name": contract.deployment.github_secret_version_variable,
        "value": github_version,
        "readback_matches": True,
    }
    evidence["status"] = "qualified_old_key_revocation_pending"
    _write_json(evidence_path, evidence)
    print(json.dumps({"evidence_path": str(evidence_path), "status": evidence["status"]}))
    return 0


def _finalize_old_key_revocation(args: argparse.Namespace) -> int:
    evidence_path = args.evidence_path.resolve()
    evidence = _read_json(evidence_path)
    if not isinstance(evidence, dict) or evidence.get("status") != (
        "qualified_old_key_revocation_pending"
    ):
        raise ValueError("rotation evidence is not awaiting old-key revocation")
    contract = _load_contract(args.contract.resolve())
    status_code = ReleaseKeyRevocationProbe(
        str(contract.target.endpoint), _read_api_key(args.old_runtime_api_key_file)
    ).verify()
    evidence["old_runtime_key"] = {
        "qdrant_revoked": True,
        "qdrant_rejection_status": status_code,
        "secret_version_destroyed": False,
    }
    evidence["status"] = "qualified_old_secret_cleanup_pending"
    _write_json(evidence_path, evidence)
    print(json.dumps({"evidence_path": str(evidence_path), "status": evidence["status"]}))
    return 0


def _record_old_secret_destroyed(args: argparse.Namespace) -> int:
    evidence_path = args.evidence_path.resolve()
    evidence = _read_json(evidence_path)
    if not isinstance(evidence, dict) or evidence.get("status") != (
        "qualified_old_secret_cleanup_pending"
    ):
        raise ValueError("rotation evidence is not awaiting old secret-version destruction")
    old_key = evidence.get("old_runtime_key")
    if not isinstance(old_key, dict) or old_key.get("qdrant_revoked") is not True:
        raise ValueError("old Qdrant runtime-key revocation has not been verified")
    old_key["secret_version_destroyed"] = True
    evidence["status"] = "qualified"
    _write_json(evidence_path, evidence)
    print(json.dumps({"evidence_path": str(evidence_path), "status": evidence["status"]}))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=_REPO_ROOT)
    parser.add_argument("--contract", type=Path, default=_DEFAULT_CONTRACT)
    subparsers = parser.add_subparsers(dest="command", required=True)

    qualify = subparsers.add_parser(
        "qualify-new-key", help="prove replacement runtime-key read-only access"
    )
    qualify.add_argument("--runtime-api-key-file", type=Path, required=True)
    qualify.add_argument("--old-version", required=True)
    qualify.add_argument("--new-version", required=True)
    qualify.add_argument("--evidence-path", type=Path, required=True)
    qualify.set_defaults(handler=_qualify_new_key)

    plan = subparsers.add_parser(
        "validate-plan", help="require a secret-version-only backend Terraform update"
    )
    plan.add_argument("--plan-json", type=Path, required=True)
    plan.add_argument("--old-version", required=True)
    plan.add_argument("--new-version", required=True)
    plan.set_defaults(handler=_validate_plan)

    record_plan = subparsers.add_parser(
        "record-plan", help="record the qualified secret-version-only Terraform plan"
    )
    record_plan.add_argument("--evidence-path", type=Path, required=True)
    record_plan.add_argument("--plan-json", type=Path, required=True)
    record_plan.set_defaults(handler=_record_plan)

    cutover = subparsers.add_parser(
        "record-cutover", help="record the verified backend and GitHub version cutover"
    )
    cutover.add_argument("--evidence-path", type=Path, required=True)
    cutover.add_argument("--backend-service-description", type=Path, required=True)
    cutover.add_argument("--backend-iam-policy", type=Path, required=True)
    cutover.add_argument("--expected-backend-image", required=True)
    cutover.add_argument("--github-secret-version", required=True)
    cutover.set_defaults(handler=_record_cutover)

    revoke = subparsers.add_parser(
        "finalize-old-key-revocation", help="verify Qdrant rejects the retired runtime key"
    )
    revoke.add_argument("--evidence-path", type=Path, required=True)
    revoke.add_argument("--old-runtime-api-key-file", type=Path, required=True)
    revoke.set_defaults(handler=_finalize_old_key_revocation)

    cleanup = subparsers.add_parser(
        "record-old-secret-destroyed", help="complete evidence after old-version destruction"
    )
    cleanup.add_argument("--evidence-path", type=Path, required=True)
    cleanup.set_defaults(handler=_record_old_secret_destroyed)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
