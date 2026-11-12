"""Deployed shared-knowledge release and provider-boundary contracts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
CONTRACT = REPO_ROOT / "contracts/deployment/knowledge-release.v1.json"
STAGING = REPO_ROOT / "infrastructure/terraform/environments/staging/main.tf"
WORKLOADS = REPO_ROOT / "infrastructure/terraform/modules/application_workloads/main.tf"
RELEASE_SCRIPT = REPO_ROOT / "infrastructure/terraform/scripts/release-shared-knowledge.sh"
LIFECYCLE_SCRIPT = REPO_ROOT / "infrastructure/terraform/scripts/bootstrap-staging.sh"
INFRASTRUCTURE_POLICY = REPO_ROOT / "contracts/deployment/infrastructure-policy.v1.json"


def test_release_contract_pins_exact_collections_credentials_and_provider_boundary() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))

    assert contract["schema_version"] == "1"
    assert contract["status"] == "defined_not_executed"
    assert contract["target"] == {
        "cluster_name": "finance-assistant-demo",
        "cluster_id": "57c4d676-360a-4f1a-aad3-92d775292673",
        "endpoint": (
            "https://57c4d676-360a-4f1a-aad3-92d775292673.us-central1-0.gcp.cloud.qdrant.io"
        ),
        "qdrant_version": "1.20.0",
        "shared_knowledge_only": True,
        "application_principal_data_allowed": False,
    }
    collections = contract["collections"]
    assert [
        (item["current_collection"], item["expected_current_points"]) for item in collections
    ] == [
        ("finance_education_v1_755be30b6a2d", 106),
        ("tax_education_v1_9b31ab2354ea", 6295),
    ]
    assert [item["rollback_collection"] for item in collections] == [
        "finance_education_v1_fcecb8c15493",
        "tax_education_v1_f2fef46b0f88",
    ]
    assert contract["credentials"]["runtime"]["qdrant_access"] == ("cluster_wide_read_only")
    assert contract["credentials"]["release"]["qdrant_access"] == ("cluster_wide_manage_write")
    assert contract["credentials"]["release"]["revoke_after_qualification"] is True
    assert contract["credentials"]["payloads_allowed_in_repository"] is False
    assert contract["credentials"]["payloads_allowed_in_github"] is False
    assert contract["qualification"]["manifest_match"] == (
        "exact_except_approved_evaluation_artifact_path_relocation"
    )
    assert contract["qualification"]["deployed_provider_environment_readback_required"] is True
    assert contract["provider_boundary"] == {
        "provider_mode": "credential_free",
        "model_mode": "credential_free",
        "live_provider_secrets_allowed": False,
        "live_provider_activation": "separate_owner_approval_required",
        "viewer_live_provider_access": "denied",
    }


def test_qualified_staging_release_evidence_matches_policy_and_contract() -> None:
    policy = json.loads(INFRASTRUCTURE_POLICY.read_text(encoding="utf-8"))
    evidence_path = REPO_ROOT / policy["operational_status"]["knowledge_release_evidence"]
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))

    assert policy["operational_status"]["knowledge_release"] == "qualified"
    assert evidence["schema_version"] == "1"
    assert evidence["status"] == "qualified"
    assert evidence["revision"] == policy["operational_status"]["knowledge_release_revision"]
    assert evidence["contract_sha256"] == hashlib.sha256(CONTRACT.read_bytes()).hexdigest()
    assert [
        (item["collection"], item["action"], item["point_count"]) for item in evidence["transfers"]
    ] == [
        ("finance_education_v1_755be30b6a2d", "uploaded_snapshot", 106),
        ("finance_education_v1_fcecb8c15493", "uploaded_snapshot", 30),
        ("tax_education_v1_9b31ab2354ea", "uploaded_snapshot", 6295),
        ("tax_education_v1_f2fef46b0f88", "uploaded_snapshot", 4735),
    ]
    assert [
        (item["logical_kb"], item["qrels_case_count"], item["passed"])
        for item in evidence["evaluations"]
    ] == [
        ("finance_education", 17, True),
        ("tax_education", 32, True),
    ]
    assert all(item["passed"] for item in evidence["rollback_proofs"])
    assert evidence["runtime_permission"] == {
        "passed": True,
        "read_status": 200,
        "write_status": 403,
    }
    assert evidence["deployed_provider_boundary"]["passed"] is True
    assert evidence["deployed_provider_boundary"]["provider_mode"] == "credential_free"
    assert evidence["deployed_provider_boundary"]["model_mode"] == "credential_free"
    assert evidence["release_key"] == {
        "qdrant_rejection_status": 403,
        "qdrant_revoked": True,
        "secret_version_destroyed": True,
    }
    assert evidence["secret_payloads_recorded"] is False


def test_release_secret_is_separate_and_never_available_to_the_runtime_service() -> None:
    staging = STAGING.read_text(encoding="utf-8")
    workloads = WORKLOADS.read_text(encoding="utf-8")

    assert 'resource "google_secret_manager_secret" "qdrant_runtime"' in staging
    assert 'resource "google_secret_manager_secret" "qdrant_release"' in staging
    assert 'secret_id           = "aifa-staging-qdrant-runtime-api-key"' in staging
    assert 'secret_id           = "aifa-staging-qdrant-release-api-key"' in staging
    assert staging.count("deletion_protection = false") == 2
    assert staging.count('role      = "roles/secretmanager.secretAccessor"') == 1
    assert "qdrant_release.secret_id" not in workloads
    assert "aifa-staging-qdrant-release-api-key" not in workloads
    assert 'AIFA_PROVIDER_MODE                   = "credential_free"' in workloads
    assert 'AIFA_MODEL_MODE                      = "credential_free"' in workloads


def test_release_wizard_reads_secret_manager_versions_without_accepting_payloads() -> None:
    script = RELEASE_SCRIPT.read_text(encoding="utf-8")
    stages = script.split("# STAGES:", maxsplit=1)[1]

    assert "TOTAL_STAGES=6" in stages
    assert "ask_secret" not in stages
    assert "gcloud secrets versions access" in stages
    assert 'gcloud run services describe "$BACKEND_SERVICE"' in stages
    assert 'any($env[]; .name == "AIFA_PROVIDER_MODE"' in stages
    assert '"AIFA_OPENAI_API_KEY"' in stages
    assert '--backend-service-description "$SERVICE_DESCRIPTION_FILE"' in stages
    assert "--release-api-key-file <(" in stages
    assert "--runtime-api-key-file <(" in stages
    assert "finalize-revocation" in stages
    assert "gcloud secrets versions destroy" in stages
    assert "record-secret-destroyed" in stages
    assert '.provider_boundary.provider_mode == "credential_free"' in stages
    assert "make qdrant-up" in stages
    assert "the worktree must be clean before releasing" in stages


def test_launch_stage_normalization_is_ignored_without_ignoring_security_controls() -> None:
    workloads = WORKLOADS.read_text(encoding="utf-8")

    assert workloads.count("ignore_changes = [launch_stage]") == 2
    assert workloads.count("default_uri_disabled = true") == 2
    assert "ignore_changes = [default_uri_disabled]" not in workloads
    assert "ignore_changes = [ingress]" not in workloads


def test_teardown_reports_exact_network_residue_as_success_without_invalid_filter() -> None:
    script = LIFECYCLE_SCRIPT.read_text(encoding="utf-8")

    assert '--filter="name=$SOURCE_INSTANCE"' not in script
    assert "'all(.[]; .name != $instance)'" in script
    assert "The exact accepted networking residue was verified; teardown succeeded." in script
    assert (
        "Google may temporarily reject deletion of the private Service Networking connection."
        in script
    )
