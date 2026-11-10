"""GCP staging-foundation, state, and short-lived delivery identity policy."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, cast

REPO_ROOT = Path(__file__).resolve().parents[2]
TERRAFORM_ROOT = REPO_ROOT / "infrastructure/terraform"
INFRASTRUCTURE_CONTRACT = REPO_ROOT / "contracts/deployment/infrastructure-policy.v1.json"
STAGING_EVIDENCE = REPO_ROOT / "backend/artifacts/release/deployment/staging-foundation.v1.json"


def _contract() -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(INFRASTRUCTURE_CONTRACT.read_text(encoding="utf-8")),
    )


def _terraform_text() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(TERRAFORM_ROOT.rglob("*.tf"))
        if ".terraform" not in path.parts
    )


def test_every_terraform_root_bills_api_quota_to_the_target_project() -> None:
    for versions_file in (
        TERRAFORM_ROOT / "bootstrap/versions.tf",
        TERRAFORM_ROOT / "shared/versions.tf",
        TERRAFORM_ROOT / "environments/staging/versions.tf",
    ):
        versions = versions_file.read_text(encoding="utf-8")
        assert "billing_project       = var.project_id" in versions
        assert "user_project_override = true" in versions


def test_infrastructure_contract_matches_owner_approved_staging_boundary() -> None:
    contract = _contract()

    assert contract["schema_version"] == "1"
    assert contract["status"] in {
        "defined_not_provisioned",
        "staging_foundation_provisioned",
    }
    assert contract["project"] == {
        "id": "comfforts-369117",
        "number": "730340912967",
        "region": "us-west1",
    }
    assert contract["github"] == {
        "repository": "hankgalt/ai_finance_assitant",
        "repository_id": "1435001816",
        "owner": "hankgalt",
        "owner_id": "2118128",
        "deployment_branch": "main",
    }
    assert contract["state"]["environment_separation"] is True
    assert contract["state"]["public_access_prevention"] == "enforced"
    assert contract["state"]["uniform_bucket_level_access"] is True
    assert contract["state"]["versioning"] is True
    assert contract["secrets"]["service"] == "regional_secret_manager"
    assert contract["secrets"]["location"] == "us-west1"
    assert contract["secrets"]["payloads_managed_by_terraform"] is False
    assert contract["identity"]["subject_format"] == (
        "repo:OWNER@OWNER-ID/REPO@REPO-ID:environment:ENVIRONMENT"
    )
    assert contract["managed_state"]["database_version"] == "POSTGRES_17"
    assert contract["managed_state"]["tier"] == "db-f1-micro"
    assert contract["managed_state"]["public_ipv4"] is False
    assert contract["managed_state"]["retained_daily_backups"] == 7
    assert contract["managed_state"]["transaction_log_retention_days"] == 3
    assert contract["workload_boundary"]["cloud_run_ingress"] == (
        "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"
    )
    assert contract["workload_boundary"]["default_uri_disabled"] is True
    assert contract["workload_boundary"]["anonymous_invoker_allowed"] is False
    assert contract["operational_status"] == {
        "terraform_foundation": "provisioned",
        "final_drift": "no_changes",
        "github_environments": "configured",
        "oidc_smoke": "staging_and_production_qualified",
        "staging_workload": "not_deployed",
        "no_direct_workload_bypass": "not_yet_testable",
    }


def test_staging_evidence_records_live_foundation_without_claiming_workload_deployment() -> None:
    evidence = json.loads(STAGING_EVIDENCE.read_text(encoding="utf-8"))

    assert evidence["status"] == "foundation_provisioned_identity_smoke_qualified"
    assert evidence["scope"]["cloud_resources_mutated"] is True
    assert evidence["scope"]["github_repository_settings_mutated"] is True
    assert evidence["scope"]["secret_payloads_recorded"] is False
    assert evidence["scope"]["workload_deployed"] is False
    assert evidence["terraform"]["bootstrap"]["final_drift"] == "no changes"
    assert evidence["terraform"]["shared"]["final_drift"] == "no changes"
    assert evidence["terraform"]["staging"]["final_drift"] == "no changes"
    assert evidence["delivery_identity"]["providers_live_state"] == "ACTIVE"
    assert [run["status"] for run in evidence["delivery_identity"]["smoke_runs"]] == [
        "failed_legacy_subject_rejected_by_attribute_condition",
        "passed_short_lived_identity_and_read_only_project_access",
        "passed_short_lived_identity_and_read_only_project_access",
    ]
    assert evidence["managed_state"]["live_state"] == "RUNNABLE"
    assert evidence["managed_state"]["public_ipv4"] is False
    assert evidence["managed_state"]["ssl_mode"] == "ENCRYPTED_ONLY"
    assert evidence["regional_secret_metadata"]["payloads_managed_by_terraform"] is False


def test_remote_state_bootstrap_is_environment_separated_and_fail_closed() -> None:
    bootstrap = (TERRAFORM_ROOT / "bootstrap/main.tf").read_text(encoding="utf-8")
    shared_backend = (TERRAFORM_ROOT / "shared/backend.tf").read_text(encoding="utf-8")
    staging_backend = (TERRAFORM_ROOT / "environments/staging/backend.tf").read_text(
        encoding="utf-8"
    )

    assert "bootstrap  =" in bootstrap
    assert "staging    =" in bootstrap
    assert "production =" in bootstrap
    assert 'public_access_prevention    = "enforced"' in bootstrap
    assert "uniform_bucket_level_access = true" in bootstrap
    assert 'deletion_policy             = "ABANDON"' in bootstrap
    assert "versioning {" in bootstrap
    assert 'backend "gcs"' in shared_backend
    assert 'backend "gcs"' in staging_backend
    assert "prevent_destroy = true" in bootstrap


def test_wif_is_repository_id_branch_and_environment_bound() -> None:
    identity = (TERRAFORM_ROOT / "modules/delivery_identity/main.tf").read_text(encoding="utf-8")
    shared = (TERRAFORM_ROOT / "shared/main.tf").read_text(encoding="utf-8")

    assert "assertion.repository_id" in identity
    assert "assertion.repository_owner_id" in identity
    assert "assertion.sub" in identity
    assert (
        'immutable_repository = "${split("/", var.repository)[0]}@'
        '${var.repository_owner_id}/${split("/", var.repository)[1]}@'
        '${var.repository_id}"'
    ) in identity
    assert (
        "assertion.sub == 'repo:${local.immutable_repository}:environment:${var.environment}'"
    ) in identity
    assert "repo:${var.repository}:environment:${var.environment}" not in identity
    assert "attribute.repository_id" in identity
    assert "roles/iam.workloadIdentityUser" in identity
    assert len(re.findall(r'deletion_policy\s*=\s*"ABANDON"', identity)) == 3
    assert identity.count("prevent_destroy = true") == 3
    assert 'repository_id       = "1435001816"' in shared
    assert 'repository_owner_id = "2118128"' in shared
    assert 'ref                 = "refs/heads/main"' in shared
    assert 'environment         = "staging"' in shared
    assert 'environment         = "production"' in shared
    assert shared.count('"roles/viewer"') == 2
    assert shared.count('"roles/serviceusage.serviceUsageConsumer"') == 2
    assert 'deletion_policy = "ABANDON"' in shared
    assert "billing_account = var.billing_account_id" in shared
    assert 'billing_account = "billingAccounts/' not in shared


def test_staging_cloud_sql_is_private_encrypted_bounded_and_recoverable() -> None:
    managed_state = (TERRAFORM_ROOT / "modules/managed_state/main.tf").read_text(encoding="utf-8")
    staging = (TERRAFORM_ROOT / "environments/staging/main.tf").read_text(encoding="utf-8")

    assert 'database_version    = "POSTGRES_17"' in managed_state
    assert "ipv4_enabled                                  = false" in managed_state
    assert 'ssl_mode                                      = "ENCRYPTED_ONLY"' in managed_state
    assert "point_in_time_recovery_enabled = true" in managed_state
    assert "transaction_log_retention_days  = 3" in staging
    assert "retained_backups                = 7" in staging
    assert 'tier                            = "db-f1-micro"' in staging
    assert "disk_size_gib                   = 10" in staging
    assert "disk_autoresize_limit_gib       = 20" in staging
    assert "deletion_protection             = true" in staging
    assert "retain_backups_on_delete        = true" in staging
    assert managed_state.count("prevent_destroy = true") == 5
    assert len(re.findall(r'deletion_policy\s*=\s*"ABANDON"', managed_state)) == 4
    assert 'google_sql_user" "retention"' in managed_state
    assert "retention_service_account_email" in managed_state


def test_terraform_never_owns_secret_payloads_or_anonymous_workload_access() -> None:
    terraform = _terraform_text()

    assert "google_secret_manager_regional_secret_version" not in terraform
    assert "secret_data" not in terraform
    assert "password =" not in terraform
    assert "roles/run.invoker" not in terraform
    assert "allUsers" not in terraform
    assert "INGRESS_TRAFFIC_ALL" not in terraform


def test_regional_secret_metadata_has_separate_staging_boundaries() -> None:
    staging = (TERRAFORM_ROOT / "environments/staging/main.tf").read_text(encoding="utf-8")

    assert "google_secret_manager_regional_secret" in staging
    assert 'location  = "us-west1"' in staging
    assert '"postgres-runtime-dsn"' in staging
    assert '"postgres-migration-dsn"' in staging
    assert '"postgres-retention-dsn"' in staging
    assert '"qdrant-runtime-api-key"' in staging
    assert "deletion_protection = true" in staging
    assert len(re.findall(r'deletion_policy\s*=\s*"ABANDON"', staging)) == 2
    assert staging.count("prevent_destroy = true") == 2


def test_terraform_workflow_is_manual_keyless_and_staging_only_for_apply() -> None:
    workflow = (REPO_ROOT / ".github/workflows/terraform.yml").read_text(encoding="utf-8")

    assert "pull_request:" in workflow
    assert "workflow_dispatch:" in workflow
    assert "id-token: write" in workflow
    assert "google-github-actions/auth@" in workflow
    assert "vars.GCP_WORKLOAD_IDENTITY_PROVIDER" in workflow
    assert "vars.GCP_DEPLOY_SERVICE_ACCOUNT" in workflow
    assert "terraform plan" in workflow
    assert "terraform apply" not in workflow
    assert "credentials_json" not in workflow
    assert "secrets." not in workflow
