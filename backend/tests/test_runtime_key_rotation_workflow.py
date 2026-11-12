"""Repository contracts for the focused Qdrant runtime-key rotation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
CONTRACT = REPO_ROOT / "contracts/deployment/runtime-key-rotation.v1.json"
SCRIPT = REPO_ROOT / "infrastructure/terraform/scripts/rotate-qdrant-runtime-key.sh"
RELEASE_SCRIPT = REPO_ROOT / "infrastructure/terraform/scripts/release-shared-knowledge.sh"
MAKEFILE = REPO_ROOT / "Makefile"
INFRASTRUCTURE_POLICY = REPO_ROOT / "contracts/deployment/infrastructure-policy.v1.json"
MANAGED_STATE = REPO_ROOT / "contracts/deployment/managed-state.v1.json"
QUALIFIED_EVIDENCE = (
    REPO_ROOT / "backend/artifacts/knowledge/deployment/"
    "staging-runtime-key-rotation-86146b6227285015665b84cbfa3f4ce0395cd618-v1-to-v2.json"
)


def test_rotation_contract_pins_scope_order_and_provider_boundary() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))

    assert contract["schema_version"] == "1"
    assert contract["status"] == "defined_not_executed"
    assert contract["credential"] == {
        "secret_id": "aifa-staging-qdrant-runtime-api-key",
        "qdrant_access": "cluster_wide_read_only",
        "recommended_expiration_days": 90,
        "old_key_retained_until_verified_cutover": True,
        "payloads_allowed_in_repository": False,
        "payloads_allowed_in_github": False,
        "payloads_managed_by_terraform": False,
    }
    assert contract["deployment"]["terraform_state_prefix"] == "workloads"
    assert contract["deployment"]["terraform_resource"] == (
        "module.application_workloads.google_cloud_run_v2_service.backend"
    )
    assert contract["deployment"]["allowed_plan_actions"] == ["update"]
    assert contract["deployment"]["github_secret_version_variable"] == ("GCP_QDRANT_SECRET_VERSION")
    assert contract["qualification"]["write_probe"] == ("delete_unique_confirmed_absent_collection")
    assert contract["qualification"]["old_key_revocation_required"] is True
    assert contract["qualification"]["old_secret_version_destruction_required"] is True
    assert contract["provider_boundary"] == {
        "provider_mode": "credential_free",
        "model_mode": "credential_free",
        "live_provider_secrets_allowed": False,
        "live_provider_activation": "separate_owner_approval_required",
        "viewer_live_provider_access": "denied",
    }


def test_qualified_rotation_evidence_matches_operational_contracts() -> None:
    evidence = json.loads(QUALIFIED_EVIDENCE.read_text(encoding="utf-8"))
    policy = json.loads(INFRASTRUCTURE_POLICY.read_text(encoding="utf-8"))
    managed_state = json.loads(MANAGED_STATE.read_text(encoding="utf-8"))
    relative_evidence = str(QUALIFIED_EVIDENCE.relative_to(REPO_ROOT))

    assert evidence["schema_version"] == "1"
    assert evidence["status"] == "qualified"
    assert evidence["revision"] == "86146b6227285015665b84cbfa3f4ce0395cd618"
    assert evidence["contract_sha256"] == hashlib.sha256(CONTRACT.read_bytes()).hexdigest()
    assert evidence["rotation"] == {"old_secret_version": "1", "new_secret_version": "2"}
    assert evidence["new_runtime_permission"] == {
        "absence_status": 404,
        "passed": True,
        "probe": "delete_unique_confirmed_absent_collection",
        "read_status": 200,
        "write_status": 403,
    }
    assert evidence["terraform_plan"]["resource"] == (
        "module.application_workloads.google_cloud_run_v2_service.backend"
    )
    assert evidence["terraform_plan"]["only_qdrant_secret_version_changed"] is True
    assert evidence["deployed_backend"]["passed"] is True
    assert evidence["deployed_backend"]["anonymous_invoker_absent"] is True
    assert evidence["deployed_backend"]["default_url_disabled"] is True
    assert evidence["deployed_backend"]["provider_boundary"]["passed"] is True
    assert evidence["github_variable"]["readback_matches"] is True
    assert evidence["old_runtime_key"] == {
        "qdrant_rejection_status": 403,
        "qdrant_revoked": True,
        "secret_version_destroyed": True,
    }
    assert evidence["secret_payloads_recorded"] is False

    operational = policy["operational_status"]
    assert operational["runtime_key_rotation"] == "qualified"
    assert operational["runtime_rotation_revision"] == evidence["revision"]
    assert operational["runtime_key_rotation_evidence"] == relative_evidence
    qdrant = managed_state["qdrant"]
    assert qdrant["runtime_key_rotation_status"] == "qualified"
    assert qdrant["runtime_rotation_revision"] == evidence["revision"]
    assert qdrant["runtime_key_rotation_evidence"] == relative_evidence


def test_rotation_wizard_uses_the_shared_library_and_seven_reviewed_stages() -> None:
    script = SCRIPT.read_text(encoding="utf-8")
    release = RELEASE_SCRIPT.read_text(encoding="utf-8")
    library, stages = script.split("# STAGES:", maxsplit=1)
    release_library = release.split("# STAGES:", maxsplit=1)[0]

    assert library == release_library
    assert "TOTAL_STAGES=7" in stages
    assert stages.count('stage "') == 7
    assert "ask_secret" not in stages
    assert "demo-runtime-up.sh" not in stages
    assert 'WORKLOAD_ROOT="$REPO_ROOT/infrastructure/terraform/environments/staging-workloads"' in (
        stages
    )
    assert '-backend-config="prefix=workloads"' in stages
    assert 'environments/staging"' not in stages
    assert "cloud sql" not in stages.lower()


def test_rotation_wizard_fails_closed_on_scope_and_keeps_old_key_for_rollback() -> None:
    stages = SCRIPT.read_text(encoding="utf-8").split("# STAGES:", maxsplit=1)[1]

    assert "validate-plan" in stages
    assert "record-plan" in stages
    assert "only the numeric Qdrant version changes" in stages
    assert 'prepare_rotation_plan "$NEW_VERSION" "$OLD_VERSION"' in stages
    assert "the old Qdrant key remains active" in stages
    assert 'curl --silent --show-error --fail --max-time 15 "$direct_url/api/health/live"' in (
        stages
    )
    assert "backend accepted anonymous direct-origin traffic" in stages
    assert stages.index("record-cutover") < stages.index("revoke only the prior")
    assert stages.index("finalize-old-key-revocation") < stages.index(
        "gcloud secrets versions destroy"
    )
    assert "Permanently destroy old runtime secret version" in stages


def test_rotation_wizard_never_accepts_or_persists_a_secret_payload() -> None:
    stages = SCRIPT.read_text(encoding="utf-8").split("# STAGES:", maxsplit=1)[1]

    assert "ask_secret" not in stages
    assert "write_env" not in stages
    assert "gh secret set" not in stages
    assert "gcloud secrets versions add" not in stages
    assert stages.count("gcloud secrets versions access") == 2
    assert "--runtime-api-key-file <(" in stages
    assert "--old-runtime-api-key-file <(" in stages
    assert ".secret_payloads_recorded == false" in stages


def test_rotation_has_a_capability_owned_make_entry_point() -> None:
    makefile = MAKEFILE.read_text(encoding="utf-8")

    assert "rotate-qdrant-runtime-key-staging:" in makefile
    assert "./infrastructure/terraform/scripts/rotate-qdrant-runtime-key.sh" in makefile
