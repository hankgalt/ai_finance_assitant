"""Focused Qdrant runtime-key rotation qualification."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from ai_finance_assistant.knowledge.models import CollectionCompatibility, CollectionManifest
from ai_finance_assistant.knowledge.runtime_key_rotation import (
    NonMutatingRuntimePermissionProbe,
    RuntimeKeyQualifier,
    RuntimeKeyRotationContract,
    _deployed_backend,
    _finalize_old_key_revocation,
    _record_cutover,
    _record_old_secret_destroyed,
    _record_plan,
    validate_terraform_plan,
)

REPO_ROOT = Path(__file__).parents[2]
CONTRACT_PATH = REPO_ROOT / "contracts/deployment/runtime-key-rotation.v1.json"


def _contract() -> RuntimeKeyRotationContract:
    return RuntimeKeyRotationContract.model_validate_json(CONTRACT_PATH.read_text(encoding="utf-8"))


def _manifest(path: Path) -> CollectionManifest:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return CollectionManifest.model_validate(payload["manifest"])


class FakeStore:
    def __init__(self, contract: RuntimeKeyRotationContract) -> None:
        self.manifests = {
            item.current_collection: _manifest(REPO_ROOT / item.current_manifest)
            for item in contract.collections
        }
        self.counts = {
            item.current_collection: item.expected_current_points for item in contract.collections
        }
        self.aliases = {item.alias: item.current_collection for item in contract.collections}

    def get_manifest(self, collection_name: str) -> CollectionManifest | None:
        return self.manifests.get(collection_name)

    def count_points(self, collection_name: str) -> int:
        return self.counts[collection_name]

    def validate_collection(
        self, collection_name: str, expected: CollectionCompatibility
    ) -> tuple[bool, str]:
        del collection_name, expected
        return True, "compatible"

    def resolve_alias(self, alias: str) -> str | None:
        return self.aliases.get(alias)


class FakeVersionProbe:
    def __init__(self, version: str = "1.20.0") -> None:
        self.version = version

    def server_version(self) -> str:
        return self.version


class FakePermissionProbe:
    def prove_read_only(self) -> dict[str, Any]:
        return {
            "read_status": 200,
            "absence_status": 404,
            "write_status": 403,
            "probe": "delete_unique_confirmed_absent_collection",
            "passed": True,
        }


def _qualifier(store: FakeStore | None = None) -> RuntimeKeyQualifier:
    contract = _contract()
    return RuntimeKeyQualifier(
        contract=contract,
        repo_root=REPO_ROOT,
        store=store or FakeStore(contract),
        version_probe=FakeVersionProbe(),
        permission_probe=FakePermissionProbe(),
        clock=lambda: datetime(2026, 11, 12, 12, 0, tzinfo=UTC),
    )


def _terraform_backend(version: str) -> dict[str, Any]:
    return {
        "name": "aifa-staging-backend",
        "template": [
            {
                "containers": [
                    {
                        "name": "backend",
                        "image": "backend@sha256:abc",
                        "env": [
                            {
                                "name": "AIFA_QDRANT_API_KEY",
                                "value_source": [
                                    {
                                        "secret_key_ref": [
                                            {
                                                "secret": "aifa-staging-qdrant-runtime-api-key",
                                                "version": version,
                                            }
                                        ]
                                    }
                                ],
                            }
                        ],
                    }
                ]
            }
        ],
    }


def _plan(old_version: str = "1", new_version: str = "2") -> dict[str, Any]:
    before = _terraform_backend(old_version)
    before["etag"] = "old-computed-value"
    after = _terraform_backend(new_version)
    after["etag"] = None
    return {
        "resource_changes": [
            {
                "address": ("module.application_workloads.google_cloud_run_v2_service.backend"),
                "change": {
                    "actions": ["update"],
                    "before": before,
                    "after": after,
                    "after_unknown": {"etag": True},
                },
            },
            {
                "address": ("module.application_workloads.google_cloud_run_v2_service.frontend"),
                "change": {"actions": ["no-op"], "before": {}, "after": {}},
            },
        ]
    }


def _service_description(version: str = "2") -> dict[str, Any]:
    return {
        "metadata": {
            "name": "aifa-staging-backend",
            "annotations": {
                "run.googleapis.com/ingress": "internal-and-cloud-load-balancing",
                "run.googleapis.com/default-url-disabled": "true",
            },
        },
        "spec": {
            "template": {
                "spec": {
                    "containers": [
                        {
                            "name": "backend",
                            "image": "backend@sha256:abc",
                            "env": [
                                {"name": "AIFA_PROVIDER_MODE", "value": "credential_free"},
                                {"name": "AIFA_MODEL_MODE", "value": "credential_free"},
                                {
                                    "name": "AIFA_QDRANT_API_KEY",
                                    "valueFrom": {
                                        "secretKeyRef": {
                                            "secret": "aifa-staging-qdrant-runtime-api-key",
                                            "version": version,
                                        }
                                    },
                                },
                            ],
                        }
                    ]
                }
            }
        },
        "status": {"conditions": [{"type": "Ready", "status": "True"}]},
    }


def test_qualifier_records_secret_free_read_only_evidence() -> None:
    evidence = _qualifier().qualify(
        revision="a" * 40,
        contract_sha256="b" * 64,
        old_version="1",
        new_version="2",
    )

    assert evidence["status"] == "qualified_cutover_pending"
    assert evidence["rotation"] == {"old_secret_version": "1", "new_secret_version": "2"}
    assert [(item["alias"], item["point_count"]) for item in evidence["collections"]] == [
        ("finance_education_active", 106),
        ("tax_education_active", 6295),
    ]
    assert evidence["new_runtime_permission"] == {
        "read_status": 200,
        "absence_status": 404,
        "write_status": 403,
        "probe": "delete_unique_confirmed_absent_collection",
        "passed": True,
    }
    assert evidence["secret_payloads_recorded"] is False
    assert "api_key" not in json.dumps(evidence).lower()


def test_qualifier_fails_when_an_active_alias_changed() -> None:
    contract = _contract()
    store = FakeStore(contract)
    store.aliases["finance_education_active"] = "unexpected"

    with pytest.raises(ValueError, match="alias is not active"):
        _qualifier(store).qualify(
            revision="a" * 40,
            contract_sha256="b" * 64,
            old_version="1",
            new_version="2",
        )


def test_non_mutating_probe_requires_absence_then_http_403() -> None:
    requests: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, request.url.path))
        if request.url.path == "/collections":
            return httpx.Response(200, json={"status": "ok", "result": {"collections": []}})
        if request.method == "GET":
            return httpx.Response(404, json={"status": {"error": "missing"}})
        return httpx.Response(403, json={"status": {"error": "forbidden"}})

    client = httpx.Client(base_url="https://qdrant.invalid", transport=httpx.MockTransport(handler))
    result = NonMutatingRuntimePermissionProbe(
        "https://qdrant.invalid",
        "replacement-key",
        probe_name="aifa_runtime_rotation_probe_test",
        client=client,
    ).prove_read_only()

    assert result["passed"] is True
    assert result["write_status"] == 403
    assert requests == [
        ("GET", "/collections"),
        ("GET", "/collections/aifa_runtime_rotation_probe_test"),
        ("DELETE", "/collections/aifa_runtime_rotation_probe_test"),
    ]
    assert all(method != "PUT" for method, _ in requests)


def test_non_mutating_probe_rejects_an_overprivileged_key_without_creating_data() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/collections":
            return httpx.Response(200, json={"status": "ok", "result": {"collections": []}})
        return httpx.Response(404, json={"status": {"error": "missing"}})

    client = httpx.Client(base_url="https://qdrant.invalid", transport=httpx.MockTransport(handler))
    probe = NonMutatingRuntimePermissionProbe(
        "https://qdrant.invalid", "write-key", probe_name="absent", client=client
    )

    with pytest.raises(PermissionError, match="HTTP 403"):
        probe.prove_read_only()


def test_terraform_plan_allows_only_the_secret_version_update(tmp_path: Path) -> None:
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(_plan()), encoding="utf-8")

    scope = validate_terraform_plan(plan_path, _contract(), old_version="1", new_version="2")

    assert scope.resource.endswith("google_cloud_run_v2_service.backend")
    assert scope.actions == ("update",)
    assert scope.old_secret_version == "1"
    assert scope.new_secret_version == "2"


def test_terraform_plan_rejects_an_unrelated_backend_change(tmp_path: Path) -> None:
    plan = _plan()
    plan["resource_changes"][0]["change"]["after"]["template"][0]["containers"][0]["image"] = (
        "backend@sha256:changed"
    )
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    with pytest.raises(ValueError, match="fields other than"):
        validate_terraform_plan(plan_path, _contract(), old_version="1", new_version="2")


def test_deployed_backend_requires_private_ready_exact_version_and_no_anonymous_iam(
    tmp_path: Path,
) -> None:
    service_path = tmp_path / "service.json"
    policy_path = tmp_path / "policy.json"
    service_path.write_text(json.dumps(_service_description()), encoding="utf-8")
    policy_path.write_text(json.dumps({"bindings": []}), encoding="utf-8")

    result = _deployed_backend(
        service_path,
        policy_path,
        _contract(),
        expected_image="backend@sha256:abc",
        new_version="2",
    )

    assert result["secret_version"] == "2"
    assert result["default_url_disabled"] is True
    assert result["anonymous_invoker_absent"] is True
    assert result["provider_boundary"]["provider_mode"] == "credential_free"


def test_deployed_backend_rejects_anonymous_invoker(tmp_path: Path) -> None:
    service_path = tmp_path / "service.json"
    policy_path = tmp_path / "policy.json"
    service_path.write_text(json.dumps(_service_description()), encoding="utf-8")
    policy_path.write_text(
        json.dumps({"bindings": [{"role": "roles/run.invoker", "members": ["allUsers"]}]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="anonymous"):
        _deployed_backend(
            service_path,
            policy_path,
            _contract(),
            expected_image="backend@sha256:abc",
            new_version="2",
        )


def test_evidence_state_machine_records_cutover_revocation_and_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    evidence_path = tmp_path / "rotation.json"
    plan_path = tmp_path / "plan.json"
    service_path = tmp_path / "service.json"
    policy_path = tmp_path / "policy.json"
    old_key_path = tmp_path / "old-key"
    evidence_path.write_text(
        json.dumps(
            _qualifier().qualify(
                revision="a" * 40,
                contract_sha256="b" * 64,
                old_version="1",
                new_version="2",
            )
        ),
        encoding="utf-8",
    )
    plan_path.write_text(json.dumps(_plan()), encoding="utf-8")
    service_path.write_text(json.dumps(_service_description()), encoding="utf-8")
    policy_path.write_text(json.dumps({"bindings": []}), encoding="utf-8")
    old_key_path.write_text("old-key", encoding="utf-8")

    assert (
        _record_plan(
            argparse.Namespace(
                evidence_path=evidence_path,
                plan_json=plan_path,
                contract=CONTRACT_PATH,
            )
        )
        == 0
    )
    assert json.loads(evidence_path.read_text(encoding="utf-8"))["status"] == (
        "qualified_apply_pending"
    )
    assert (
        _record_cutover(
            argparse.Namespace(
                evidence_path=evidence_path,
                contract=CONTRACT_PATH,
                backend_service_description=service_path,
                backend_iam_policy=policy_path,
                expected_backend_image="backend@sha256:abc",
                github_secret_version="2",
            )
        )
        == 0
    )

    class RevokedProbe:
        def __init__(self, endpoint: str, api_key: str) -> None:
            assert endpoint.startswith("https://")
            assert api_key == "old-key"

        def verify(self) -> int:
            return 403

    monkeypatch.setattr(
        "ai_finance_assistant.knowledge.runtime_key_rotation.ReleaseKeyRevocationProbe",
        RevokedProbe,
    )
    assert (
        _finalize_old_key_revocation(
            argparse.Namespace(
                evidence_path=evidence_path,
                contract=CONTRACT_PATH,
                old_runtime_api_key_file=old_key_path,
            )
        )
        == 0
    )
    assert _record_old_secret_destroyed(argparse.Namespace(evidence_path=evidence_path)) == 0

    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["status"] == "qualified"
    assert evidence["terraform_plan"] == {
        "resource": "module.application_workloads.google_cloud_run_v2_service.backend",
        "actions": ["update"],
        "only_qdrant_secret_version_changed": True,
        "passed": True,
    }
    assert evidence["github_variable"]["value"] == "2"
    assert evidence["old_runtime_key"] == {
        "qdrant_revoked": True,
        "qdrant_rejection_status": 403,
        "secret_version_destroyed": True,
    }
    assert "old-key" not in evidence_path.read_text(encoding="utf-8")
