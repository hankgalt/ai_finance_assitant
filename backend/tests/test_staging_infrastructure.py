"""GCP staging-foundation, state, and short-lived delivery identity policy."""

from __future__ import annotations

import json
import os
import re
import subprocess
import textwrap
from pathlib import Path
from typing import Any, cast

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TERRAFORM_ROOT = REPO_ROOT / "infrastructure/terraform"
INFRASTRUCTURE_CONTRACT = REPO_ROOT / "contracts/deployment/infrastructure-policy.v1.json"
RECOVERY_CONTRACT = REPO_ROOT / "contracts/deployment/recovery-policy.v1.json"
STAGING_EVIDENCE = REPO_ROOT / "backend/artifacts/release/deployment/staging-foundation.v1.json"
LIFECYCLE_EVIDENCE = (
    REPO_ROOT / "backend/artifacts/release/deployment/demo-runtime-lifecycle.v1.json"
)
WORKLOAD_EVIDENCE = REPO_ROOT / "backend/artifacts/release/deployment/application-workloads.v1.json"


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
        TERRAFORM_ROOT / "environments/staging-workloads/versions.tf",
    ):
        versions = versions_file.read_text(encoding="utf-8")
        assert "billing_project       = var.project_id" in versions
        assert "user_project_override = true" in versions


def test_infrastructure_contract_matches_owner_approved_staging_boundary() -> None:
    contract = _contract()

    assert contract["schema_version"] == "1"
    assert contract["status"] == "runtime_absent_networking_foundation_retained"
    assert contract["private_demo_mvp"] == {
        "target_database_tier": "db-g1-small",
        "runtime_lifecycle": "on_demand_create_destroy_recreate",
        "empty_store_on_create": True,
        "data_preservation_on_destroy": False,
        "backup_restore_gate": "deferred_post_mvp",
        "current_provisioned_foundation_requires_replacement": False,
        "persistent_private_networking_foundation": True,
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
    assert contract["state"]["persistent_staging_networking"] == [
        "vpc_network",
        "private_service_allocated_range",
        "service_networking_connection",
    ]
    assert contract["secrets"]["service"] == "standard_secret_manager"
    assert contract["secrets"]["replication"] == "user_managed"
    assert contract["secrets"]["payload_locations"] == ["us-west1"]
    assert contract["secrets"]["cloud_run_injection"] == ("native_environment_numeric_version")
    assert contract["secrets"]["payloads_managed_by_terraform"] is False
    assert contract["identity"]["subject_format"] == (
        "repo:OWNER@OWNER-ID/REPO@REPO-ID:environment:ENVIRONMENT"
    )
    assert contract["managed_state"]["database_version"] == "POSTGRES_17"
    assert contract["managed_state"]["tier"] == "db-g1-small"
    assert contract["managed_state"]["public_ipv4"] is False
    assert contract["managed_state"]["automated_backups_enabled"] is False
    assert contract["managed_state"]["retained_daily_backups"] == 0
    assert contract["managed_state"]["point_in_time_recovery_enabled"] is False
    assert contract["managed_state"]["transaction_log_retention_days"] == 0
    assert contract["managed_state"]["retain_backups_on_delete"] is False
    assert contract["managed_state"]["deletion_protection"] is False
    assert contract["managed_state"]["external_configuration_status"] == "runtime_absent"
    assert contract["managed_state_operator_jobs"] == {
        "operations": ["migration", "qualification", "retention"],
        "execution": "cloud_run_v2_jobs",
        "network": "direct_vpc_private_ranges_only",
        "database_authentication": "cloud_sql_auth_proxy_automatic_iam",
        "image_policy": "immutable_digest_required",
        "image_registry": "us-west1-docker.pkg.dev/comfforts-369117/aifa-containers",
        "mixed_registry_hosts_allowed": False,
        "http_endpoint": False,
        "status": "removed_after_qualified_execution",
        "execution_status": {
            "migration": "passed",
            "qualification_prepare": "passed",
            "retention": "passed_and_synthetic_state_deleted",
        },
    }
    assert contract["workload_boundary"]["cloud_run_ingress"] == (
        "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"
    )
    assert contract["workload_boundary"]["default_uri_disabled"] is True
    assert contract["workload_boundary"]["anonymous_invoker_allowed"] is False
    assert contract["workload_boundary"]["services"] == [
        "aifa-staging-backend",
        "aifa-staging-frontend",
    ]
    assert contract["workload_boundary"]["terraform_state_prefix"] == "workloads"
    assert contract["workload_boundary"]["pre_edge_iap_audience_status"] == (
        "intentional_fail_closed_sentinel"
    )
    assert contract["workload_boundary"]["status"] == "terraform_defined_not_applied"
    assert contract["operational_status"] == {
        "terraform_foundation": "networking_only",
        "final_drift": "runtime_absent_expected_networking_residue",
        "github_environments": "configured",
        "oidc_smoke": "staging_and_production_qualified",
        "staging_workload": "terraform_defined_not_deployed",
        "no_direct_workload_bypass": "controls_defined_not_qualified",
        "mvp_lifecycle_code": "foundation_migration_workload_order_defined_not_applied",
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
    operator_jobs = evidence["managed_state_operator_jobs"]
    assert operator_jobs["status"] == "migration_prepare_retention_executed_recovery_pending"
    assert operator_jobs["migration"]["status"] == "passed"
    assert operator_jobs["qualification_prepare"]["status"] == "passed"
    assert operator_jobs["retention"]["status"] == "passed_and_synthetic_state_deleted"
    assert operator_jobs["recovery_attempt"]["temporary_instances_created"] is True
    assert operator_jobs["recovery_attempt"]["temporary_instances_cleanup"] == (
        "deleted_after_explicit_operator_confirmation"
    )
    assert operator_jobs["recovery_attempt"]["qualification_backup_cleanup"] == (
        "deleted_after_explicit_operator_confirmation"
    )
    assert operator_jobs["recovery_attempt"]["source_synthetic_state_cleanup"] == (
        "deleted_by_retention_verification"
    )
    assert evidence["regional_secret_metadata"]["payloads_managed_by_terraform"] is False


def test_demo_runtime_lifecycle_evidence_records_runtime_absence_and_networking() -> None:
    evidence = json.loads(LIFECYCLE_EVIDENCE.read_text(encoding="utf-8"))

    assert evidence["schema_version"] == "1"
    assert evidence["status"] == "runtime_absent_networking_acceptance_defined_not_applied"
    assert evidence["scope"]["cloud_resources_mutated"] is True
    assert evidence["scope"]["terraform_applied"] is True
    assert evidence["target"]["database_tier"] == "db-g1-small"
    assert evidence["target"]["automated_backups_enabled"] is False
    assert evidence["target"]["point_in_time_recovery_enabled"] is False
    assert evidence["target"]["destroy_discards_application_state"] is True
    assert evidence["operator_entry_points"] == {
        "up": "infrastructure/terraform/scripts/demo-runtime-up.sh",
        "down": "infrastructure/terraform/scripts/demo-runtime-down.sh",
        "destroy_confirmation": "DESTROY EMPTY-DEMO-RUNTIME",
    }
    assert evidence["live_attempt"]["result"] == "runtime_destroyed_networking_foundation_retained"
    assert evidence["live_attempt"]["application_database_present"] is False
    assert evidence["live_attempt"]["source_instance_present"] is False
    assert evidence["live_attempt"]["iam_database_users_present"] == []
    assert evidence["live_attempt"]["networking_foundation_retained"] is True
    assert evidence["live_attempt"]["networking_acceptance_fix_applied"] is False
    assert "private_networking" in evidence["persistent_foundation"]
    assert "private_networking" not in evidence["destroyed_staging_scope"]
    assert evidence["deferred"]["cloud_sql_recovery_qualification"] == "post_mvp"
    assert evidence["security"]["secrets_committed"] is False


def test_application_workload_evidence_is_truthful_about_unapplied_controls() -> None:
    evidence = json.loads(WORKLOAD_EVIDENCE.read_text(encoding="utf-8"))

    assert evidence["schema_version"] == "1"
    assert evidence["status"] == "terraform_and_lifecycle_defined_not_applied"
    assert evidence["scope"]["cloud_resources_mutated"] is False
    assert evidence["scope"]["terraform_applied"] is False
    assert evidence["scope"]["secret_payloads_recorded"] is False
    assert evidence["terraform"]["foundation_state_prefix"] == "foundation"
    assert evidence["terraform"]["workload_state_prefix"] == "workloads"
    assert evidence["terraform"]["destroy_order"] == [
        "application_workloads",
        "managed_state_and_operator_jobs",
    ]
    assert evidence["workload_policy"]["default_uri_disabled"] is True
    assert evidence["workload_policy"]["anonymous_invoker_allowed"] is False
    assert evidence["secret_policy"]["payload_owned_by_terraform"] is False
    assert evidence["secret_policy"]["latest_version_allowed"] is False
    assert evidence["qualification"]["live_workload_apply"] == "pending_after_merge"


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


def test_staging_cloud_sql_is_private_encrypted_and_disposable_on_demand() -> None:
    managed_state = (TERRAFORM_ROOT / "modules/managed_state/main.tf").read_text(encoding="utf-8")
    staging = (TERRAFORM_ROOT / "environments/staging/main.tf").read_text(encoding="utf-8")
    variables = (TERRAFORM_ROOT / "environments/staging/variables.tf").read_text(encoding="utf-8")

    assert 'database_version    = "POSTGRES_17"' in managed_state
    assert "ipv4_enabled                                  = false" in managed_state
    assert 'ssl_mode                                      = "ENCRYPTED_ONLY"' in managed_state
    assert "enabled                        = false" in managed_state
    assert "point_in_time_recovery_enabled = false" in managed_state
    assert "final_backup_config" in managed_state
    assert "tier                            = var.database_tier" in staging
    assert 'default     = "db-g1-small"' in variables
    assert "disk_size_gib                   = 10" in staging
    assert "disk_autoresize_limit_gib       = 20" in staging
    assert "deletion_protection             = false" in staging
    assert "retain_backups_on_delete        = false" in staging
    assert "prevent_destroy" not in managed_state
    assert 'deletion_policy = "ABANDON"' not in managed_state
    assert 'google_sql_user" "retention"' in managed_state
    assert "retention_service_account_email" in managed_state


def test_cloud_sql_destroy_drops_application_database_before_iam_users() -> None:
    managed_state = (TERRAFORM_ROOT / "modules/managed_state/main.tf").read_text(encoding="utf-8")
    database = managed_state.split('resource "google_sql_database" "application"', maxsplit=1)[
        1
    ].split('resource "google_sql_user" "runtime"', maxsplit=1)[0]

    assert "depends_on = [" in database
    assert "google_sql_user.runtime" in database
    assert "google_sql_user.migration" in database
    assert "google_sql_user.retention" in database


def test_terraform_never_owns_secret_payloads_or_anonymous_workload_access() -> None:
    terraform = _terraform_text()

    assert "google_secret_manager_regional_secret_version" not in terraform
    assert "google_secret_manager_secret_version" not in terraform
    assert "secret_data" not in terraform
    assert "password =" not in terraform
    assert "roles/run.invoker" not in terraform
    assert "allUsers" not in terraform
    assert "INGRESS_TRAFFIC_ALL" not in terraform


def test_standard_qdrant_secret_has_us_west1_replication_and_runtime_only_access() -> None:
    staging = (TERRAFORM_ROOT / "environments/staging/main.tf").read_text(encoding="utf-8")

    assert 'resource "google_secret_manager_secret" "qdrant_runtime"' in staging
    assert "google_secret_manager_regional_secret" not in staging
    assert "user_managed" in staging
    assert "location = var.region" in staging
    assert 'secret_id           = "aifa-staging-qdrant-runtime-api-key"' in staging
    assert "postgres-runtime-dsn" not in staging
    assert "postgres-migration-dsn" not in staging
    assert "postgres-retention-dsn" not in staging
    assert staging.count('role      = "roles/secretmanager.secretAccessor"') == 1
    assert 'workload["runtime"].email' in staging
    assert "deletion_protection = false" in staging
    assert len(re.findall(r'deletion_policy\s*=\s*"DELETE"', staging)) == 1
    assert "prevent_destroy" not in staging


def test_private_demo_runtime_resources_are_deleted_instead_of_abandoned() -> None:
    staging = (TERRAFORM_ROOT / "environments/staging/main.tf").read_text(encoding="utf-8")
    jobs = (TERRAFORM_ROOT / "modules/managed_state_jobs/main.tf").read_text(encoding="utf-8")

    assert "prevent_destroy" not in staging
    assert len(re.findall(r'deletion_policy\s*=\s*"DELETE"', staging)) == 1
    assert staging.count("deletion_protection = false") == 1
    assert 'deletion_policy = "ABANDON"' not in staging
    assert "deletion_protection = false" in jobs
    assert "prevent_destroy" not in jobs


def test_application_workloads_are_private_pinned_bounded_and_separate_state() -> None:
    workloads = (TERRAFORM_ROOT / "modules/application_workloads/main.tf").read_text(
        encoding="utf-8"
    )
    variables = (TERRAFORM_ROOT / "modules/application_workloads/variables.tf").read_text(
        encoding="utf-8"
    )
    root = (TERRAFORM_ROOT / "environments/staging-workloads/main.tf").read_text(encoding="utf-8")
    root_variables = (TERRAFORM_ROOT / "environments/staging-workloads/variables.tf").read_text(
        encoding="utf-8"
    )

    assert workloads.count('resource "google_cloud_run_v2_service"') == 2
    assert 'resource "google_cloud_run_v2_service" "backend"' in workloads
    assert 'resource "google_cloud_run_v2_service" "frontend"' in workloads
    assert workloads.count('ingress              = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"') == 2
    assert workloads.count("default_uri_disabled = true") == 2
    assert workloads.count('launch_stage         = "BETA"') == 2
    assert workloads.count("deletion_protection  = false") == 2
    assert workloads.count("min_instance_count = 0") == 2
    assert workloads.count("max_instance_count = 1") == 2
    assert "max_instance_request_concurrency = 4" in workloads
    assert "max_instance_request_concurrency = 40" in workloads
    assert 'path = "/api/health/live"' in workloads
    assert 'path = "/finance_assistant/healthz"' in workloads
    assert re.search(r'name\s*=\s*"cloud-sql-proxy"', workloads)
    assert 'depends_on = ["cloud-sql-proxy"]' in workloads
    assert '"--private-ip"' in workloads
    assert '"--auto-iam-authn"' in workloads
    assert 'egress = "PRIVATE_RANGES_ONLY"' in workloads
    assert "secret_key_ref {" in workloads
    assert "version = var.qdrant_secret_version" in workloads
    assert 'AIFA_PROVIDER_MODE                   = "credential_free"' in workloads
    assert 'AIFA_MODEL_MODE                      = "credential_free"' in workloads
    assert 'AIFA_STORAGE_MIGRATION_MODE          = "verify_only"' in workloads
    assert 'AIFA_RETENTION_EXECUTION_MODE        = "scheduled"' in workloads
    assert 'AIFA_RESPONSE_CACHE_ADAPTER          = "disabled"' in workloads
    assert 'AIFA_IDENTITY_MODE                   = "iap"' in workloads
    assert 'AIFA_BASE_PATH                       = "/finance_assistant"' in workloads
    assert 'strcontains(var.backend_image, "@sha256:")' in variables
    assert 'strcontains(var.frontend_image, "@sha256:")' in variables
    assert 'regex("^[1-9][0-9]*$", var.qdrant_secret_version)' in variables
    assert 'module "application_workloads"' in root
    assert (
        'iap_audience                   = "/projects/730340912967/global/backendServices/0"' in root
    )
    assert 'qdrant_secret_id               = "aifa-staging-qdrant-runtime-api-key"' in root
    assert "terraform_remote_state" not in root
    assert 'strcontains(var.backend_image, "@sha256:")' in root_variables
    assert 'strcontains(var.frontend_image, "@sha256:")' in root_variables
    frontend = workloads.split('resource "google_cloud_run_v2_service" "frontend"', maxsplit=1)[1]
    assert "var.frontend_service_account_email" in frontend
    assert "secret_key_ref" not in frontend
    assert "vpc_access" not in frontend
    staging = (TERRAFORM_ROOT / "environments/staging/main.tf").read_text(encoding="utf-8")
    identity_roles = staging.split("identity_roles = {", maxsplit=1)[1].split("\n  }", maxsplit=1)[
        0
    ]
    assert 'identity = "frontend"' not in identity_roles


def test_lifecycle_migrates_before_workloads_and_verifies_no_direct_origin() -> None:
    wizard = (TERRAFORM_ROOT / "scripts/bootstrap-staging.sh").read_text(encoding="utf-8")

    migration = wizard.index('gcloud run jobs execute "$MIGRATION_JOB"')
    workload_apply = wizard.index('terraform -chdir="$WORKLOAD_ROOT" apply "$WORKLOAD_PLAN"')
    assert migration < workload_apply
    assert 'open_url "https://console.cloud.google.com/security/secret-manager/secret/' in wizard
    assert "The secret value must be entered directly in GCP" in wizard
    assert "ask_secret" not in wizard.split("# STAGES:", maxsplit=1)[1]
    assert "--filter='state=enabled'" in wizard
    assert 'export TF_VAR_qdrant_secret_version="$QDRANT_SECRET_VERSION"' in wizard
    assert 'gcloud sql users delete "$OWNER_DATABASE_USER"' in wizard
    assert "--data-api-access=ALLOW_DATA_API" in wizard
    assert "--data-api-access=DISALLOW_DATA_API" in wizard
    assert '.metadata.annotations["run.googleapis.com/ingress"]' in wizard
    assert '.metadata.annotations["run.googleapis.com/default-url-disabled"]' in wizard
    assert "curl --silent --show-error --fail --max-time 15" in wizard
    assert "accepted anonymous direct-origin traffic" in wizard
    assert "allUsers" in wizard
    assert "allAuthenticatedUsers" in wizard
    assert "gh variable set GCP_FRONTEND_IMAGE" in wizard
    assert "gh variable set GCP_QDRANT_SECRET_VERSION" in wizard


def test_demo_runtime_entry_points_review_exact_staging_plans_and_data_loss() -> None:
    up = (TERRAFORM_ROOT / "scripts/demo-runtime-up.sh").read_text(encoding="utf-8")
    down = (TERRAFORM_ROOT / "scripts/demo-runtime-down.sh").read_text(encoding="utf-8")
    wizard = (TERRAFORM_ROOT / "scripts/bootstrap-staging.sh").read_text(encoding="utf-8")
    staging = (TERRAFORM_ROOT / "environments/staging/main.tf").read_text(encoding="utf-8")
    variables = (TERRAFORM_ROOT / "environments/staging/variables.tf").read_text(encoding="utf-8")

    assert 'bootstrap-staging.sh" up' in up
    assert 'bootstrap-staging.sh" down' in down
    assert 'ACTION="${1:-}"' in wizard
    assert "for tool in gcloud terraform git jq" in wizard
    assert "CURRENT_BRANCH=$(git branch --show-current)" in wizard
    assert '[[ "$CURRENT_BRANCH" == "main" ]]' in wizard
    assert '[[ -z "$(git status --porcelain)" ]]' in wizard
    assert '[[ "$(git rev-parse HEAD)" == "$(git rev-parse origin/main)" ]]' in wizard
    assert 'DESTROY_CONFIRMATION="DESTROY EMPTY-DEMO-RUNTIME"' in wizard
    assert '[[ "$confirmation" == "$DESTROY_CONFIRMATION" ]]' in wizard
    assert 'CURRENT_DATABASE_TIER=$(gcloud sql instances describe "$SOURCE_INSTANCE"' in wizard
    assert 'export TF_VAR_database_tier="$CURRENT_DATABASE_TIER"' in wizard
    assert 'terraform -chdir="$STAGING_ROOT" apply "$LIFECYCLE_PLAN"' in wizard
    assert 'HAS_CREATE_OR_DELETE=$(terraform -chdir="$STAGING_ROOT" show -json' in wizard
    assert "SQL_GUARDS_ACTIVE=$(jq -r" in wizard
    assert 'if [[ "$HAS_CREATE_OR_DELETE" == "true" ]]' in wizard
    assert "Skipping the transition apply so deleted resources are not recreated" in wizard
    assert "runtime_is_absent_with_networking_foundation" in wizard
    assert "Retaining the approved private networking foundation" in wizard
    assert 'terraform -chdir="$STAGING_ROOT" plan -destroy' in wizard
    assert 'terraform -chdir="$STAGING_ROOT" apply "$DESTROY_PLAN"' in wizard
    assert "All deployed Sessions, Portfolios, Goals, Runs, History, and Inspector data" in wizard
    assert "Qdrant Secret Manager payload" in wizard
    assert 'terraform -chdir="$WORKLOAD_ROOT" plan -destroy' in wizard
    assert 'terraform -chdir="$WORKLOAD_ROOT" apply "$WORKLOAD_DESTROY_PLAN"' in wizard
    assert wizard.index('terraform -chdir="$WORKLOAD_ROOT" apply "$WORKLOAD_DESTROY_PLAN"') < (
        wizard.index('terraform -chdir="$STAGING_ROOT" apply "$DESTROY_PLAN"')
    )
    assert "terraform destroy" not in wizard
    assert "qualify-cloud-sql-recovery.sh" not in wizard
    assert "tier                            = var.database_tier" in staging
    assert 'variable "database_tier"' in variables
    assert 'default     = "db-g1-small"' in variables


@pytest.mark.parametrize(
    ("residual_before_run", "unexpected_residue", "expected_returncode", "state_checks"),
    [
        (True, "", 0, 3),
        (False, "", 0, 6),
        (
            False,
            "google_secret_manager_secret.unexpected",
            1,
            5,
        ),
    ],
)
def test_demo_runtime_down_accepts_only_networking_residue_after_provider_delay(
    tmp_path: Path,
    residual_before_run: bool,
    unexpected_residue: str,
    expected_returncode: int,
    state_checks: int,
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    log = tmp_path / "commands.log"
    destroy_attempted = tmp_path / "destroy-attempted"

    commands = {
        "git": """
            case "$*" in
              "branch --show-current") printf 'main\\n' ;;
              "status --porcelain") ;;
              "rev-parse origin/main"|"rev-parse HEAD") printf 'approved-main\\n' ;;
              *) exit 1 ;;
            esac
        """,
        "gcloud": """
            case "$*" in
              "auth list --filter=status:ACTIVE --format=value(account)")
                printf 'vtalwar.w@comfforts.com\\n'
                ;;
              "config get-value project") printf 'comfforts-369117\\n' ;;
              *"sql instances describe aifa-staging-postgres"*)
                if [[ -f "$DESTROY_ATTEMPTED" ]]; then exit 1; fi
                if [[ "$*" == *"--format=json"* ]]; then
                  printf '%s' '{"settings":{"tier":"db-f1-micro",'
                  printf '%s' '"deletionProtectionEnabled":false,"backupConfiguration":{'
                  printf '%s' '"enabled":false,"pointInTimeRecoveryEnabled":false},'
                  printf '%s' '"retainBackupsOnDelete":false,'
                  printf '%s\\n' '"finalBackupConfig":{"enabled":false}}}'
                else
                  printf 'db-f1-micro\\n'
                fi
                ;;
              *"sql instances list"*)
                if [[ ! -f "$DESTROY_ATTEMPTED" ]]; then
                  printf 'aifa-staging-postgres\\n'
                fi
                ;;
              *) exit 1 ;;
            esac
        """,
        "terraform": """
            printf '%s\\n' "$*" >> "$FAKE_COMMAND_LOG"
            case "$*" in
              "version") printf 'Terraform v1.17.1\\n' ;;
              *" state list")
                if [[ "$*" == *"staging-workloads"* ]]; then exit 0; fi
                printf '%s\\n' \\
                  'module.managed_state.google_compute_global_address.private_services' \\
                  'module.managed_state.google_compute_network.private' \\
                  'module.managed_state.google_service_networking_connection.private_services'
                if [[ ! -f "$DESTROY_ATTEMPTED" ]]; then
                  printf '%s\\n' 'module.managed_state.google_sql_database_instance.postgres'
                elif [[ -n "$UNEXPECTED_RESIDUE" ]]; then
                  printf '%s\\n' "$UNEXPECTED_RESIDUE"
                fi
                ;;
              *" show -json "*)
                printf '%s\\n' '{"resource_changes":[{"change":{"actions":["update"]}}]}'
                ;;
              *" show -no-color "*) printf 'reviewed plan\\n' ;;
              *" apply "*"aifa-demo-destroy"*)
                : > "$DESTROY_ATTEMPTED"
                printf '%s%s\\n' 'Failed to delete connection; ' \\
                  'Producer services are still using this connection.' >&2
                exit 1
                ;;
              *" init "*|*" plan "*|*" apply "*) ;;
              *) exit 1 ;;
            esac
        """,
    }
    for name, body in commands.items():
        executable = fake_bin / name
        executable.write_text(
            "#!/usr/bin/env bash\nset -euo pipefail\n" + textwrap.dedent(body),
            encoding="utf-8",
        )
        executable.chmod(0o755)

    environment = os.environ.copy()
    environment.update(
        {
            "PATH": f"{fake_bin}:{environment['PATH']}",
            "TMPDIR": str(tmp_path),
            "FAKE_COMMAND_LOG": str(log),
            "DESTROY_ATTEMPTED": str(destroy_attempted),
            "UNEXPECTED_RESIDUE": unexpected_residue,
            "GCP_BACKEND_IMAGE": (
                "us-west1-docker.pkg.dev/comfforts-369117/aifa-containers/"
                f"finance-assistant-backend@sha256:{'0' * 64}"
            ),
            "GCP_FRONTEND_IMAGE": (
                "us-west1-docker.pkg.dev/comfforts-369117/aifa-containers/"
                f"finance-assistant-frontend@sha256:{'1' * 64}"
            ),
        }
    )
    if residual_before_run:
        destroy_attempted.touch()
    result = subprocess.run(
        [str(TERRAFORM_ROOT / "scripts/demo-runtime-down.sh")],
        cwd=REPO_ROOT,
        env=environment,
        input="\n\ny\nDESTROY EMPTY-DEMO-RUNTIME\n",
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == expected_returncode, result.stdout + result.stderr
    if expected_returncode == 0:
        assert "Retaining the approved private networking foundation." in result.stdout
        assert "The billable demo runtime is absent." in result.stdout
    else:
        assert "resources outside the approved networking foundation remain" in result.stdout
    assert log.read_text(encoding="utf-8").count(" state list") == state_checks


def test_demo_runtime_up_migrates_before_applying_private_workloads(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    log = tmp_path / "commands.log"
    backend_image = (
        "us-west1-docker.pkg.dev/comfforts-369117/aifa-containers/"
        f"finance-assistant-backend@sha256:{'0' * 64}"
    )
    frontend_image = (
        "us-west1-docker.pkg.dev/comfforts-369117/aifa-containers/"
        f"finance-assistant-frontend@sha256:{'1' * 64}"
    )
    commands = {
        "git": """
            case "$*" in
              "branch --show-current") printf 'main\\n' ;;
              "status --porcelain") ;;
              "rev-parse origin/main"|"rev-parse HEAD") printf 'approved-main\\n' ;;
              *) exit 1 ;;
            esac
        """,
        "gcloud": """
            printf 'gcloud %s\\n' "$*" >> "$FAKE_COMMAND_LOG"
            case "$*" in
              "auth list --filter=status:ACTIVE --format=value(account)")
                printf 'vtalwar.w@comfforts.com\\n'
                ;;
              "config get-value project") printf 'comfforts-369117\\n' ;;
              *"billing projects describe"*) printf 'billingAccounts/123456\\n' ;;
              *"secrets versions list"*)
                printf 'projects/comfforts-369117/secrets/'
                printf 'aifa-staging-qdrant-runtime-api-key/versions/1\\n'
                ;;
              *"sql users list"*) ;;
              *"run services describe aifa-staging-backend"*)
                printf '%s' '{"metadata":{"annotations":{"run.googleapis.com/ingress":'
                printf '%s' '"internal-and-cloud-load-balancing",'
                printf '%s' '"run.googleapis.com/default-url-disabled":"true"}},'
                printf '%s' '"status":{"conditions":[{"type":"Ready","status":"True"}]},'
                printf '%s' '"spec":{"template":{"spec":{"containers":['
                printf '{"name":"backend","image":"%s"}]}}}}\\n' "$GCP_BACKEND_IMAGE"
                ;;
              *"run services describe aifa-staging-frontend"*)
                printf '%s' '{"metadata":{"annotations":{"run.googleapis.com/ingress":'
                printf '%s' '"internal-and-cloud-load-balancing",'
                printf '%s' '"run.googleapis.com/default-url-disabled":"true"}},'
                printf '%s' '"status":{"conditions":[{"type":"Ready","status":"True"}]},'
                printf '%s' '"spec":{"template":{"spec":{"containers":['
                printf '{"name":"frontend","image":"%s"}]}}}}\\n' "$GCP_FRONTEND_IMAGE"
                ;;
              *"run services get-iam-policy"*) printf '{}\\n' ;;
              *"artifacts docker images describe"*|*"storage buckets describe"*|\\
              *"storage buckets create"*|*"storage buckets update"*|\\
              *"sql instances patch"*|*"sql users create"*|*"sql users delete"*|\\
              *"sql instances execute-sql"*|*"run jobs execute"*) ;;
              *) exit 1 ;;
            esac
        """,
        "terraform": """
            printf 'terraform %s\\n' "$*" >> "$FAKE_COMMAND_LOG"
            case "$*" in
              "version") printf 'Terraform v1.17.1\\n' ;;
              *"output -raw staging_workload_identity_provider"*) printf 'staging-provider\\n' ;;
              *"output -raw staging_deploy_service_account"*)
                printf 'staging-sa@example.invalid\\n'
                ;;
              *"output -raw production_workload_identity_provider"*)
                printf 'production-provider\\n'
                ;;
              *"output -raw production_deploy_service_account"*)
                printf 'production-sa@example.invalid\\n'
                ;;
              *"state show "*|*" init "*|*" import "*|*" plan "*|*" apply "*) ;;
              *"show -no-color "*) printf 'reviewed workload plan\\n' ;;
              *) exit 1 ;;
            esac
        """,
        "gh": """
            printf 'gh %s\\n' "$*" >> "$FAKE_COMMAND_LOG"
            case "$*" in
              "auth status") ;;
              *"deployment-branch-policies --jq"*) printf 'main\\n' ;;
              "api "*|"variable set "*) ;;
              *) exit 1 ;;
            esac
        """,
    }
    for name, body in commands.items():
        executable = fake_bin / name
        executable.write_text(
            "#!/usr/bin/env bash\nset -euo pipefail\n" + textwrap.dedent(body),
            encoding="utf-8",
        )
        executable.chmod(0o755)

    environment = os.environ.copy()
    environment.update(
        {
            "PATH": f"{fake_bin}:{environment['PATH']}",
            "TMPDIR": str(tmp_path),
            "FAKE_COMMAND_LOG": str(log),
            "GCP_BACKEND_IMAGE": backend_image,
            "GCP_FRONTEND_IMAGE": frontend_image,
        }
    )
    result = subprocess.run(
        [str(TERRAFORM_ROOT / "scripts/demo-runtime-up.sh")],
        cwd=REPO_ROOT,
        env=environment,
        input="\n\ny\ny\ny\ny\ny\ny\ny\n",
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    command_log = log.read_text(encoding="utf-8")
    migration = command_log.index("gcloud run jobs execute aifa-staging-migrate")
    workload_apply = command_log.index("staging-workloads apply")
    assert migration < workload_apply
    assert "Pinned Qdrant secret version 1 without reading its payload." in result.stdout
    assert "Both services are Ready, digest pinned" in result.stdout
    assert "GCP_FRONTEND_IMAGE" in command_log
    assert "GCP_QDRANT_SECRET_VERSION" in command_log


def test_cloud_sql_operator_jobs_are_iam_only_digest_pinned_and_vpc_scoped() -> None:
    jobs = (TERRAFORM_ROOT / "modules/managed_state_jobs/main.tf").read_text(encoding="utf-8")
    variables = (TERRAFORM_ROOT / "modules/managed_state_jobs/variables.tf").read_text(
        encoding="utf-8"
    )
    staging_variables = (TERRAFORM_ROOT / "environments/staging/variables.tf").read_text(
        encoding="utf-8"
    )
    staging = (TERRAFORM_ROOT / "environments/staging/main.tf").read_text(encoding="utf-8")
    workflow = (REPO_ROOT / ".github/workflows/terraform.yml").read_text(encoding="utf-8")
    artifact_registry_prefix = "us-west1-docker.pkg.dev/comfforts-369117/aifa-containers/"

    assert 'resource "google_cloud_run_v2_job" "operator"' in jobs
    assert "migration = {" in jobs
    assert "qualification = {" in jobs
    assert "retention = {" in jobs
    assert re.search(
        r'name\s*=\s*"aifa-\$\{var\.environment\}-\$\{each\.value\.name\}"',
        jobs,
    )
    assert re.search(
        r"service_account\s*=\s*var\.service_account_emails\[each\.value\.identity\]",
        jobs,
    )
    assert re.search(r'name\s*=\s*"cloud-sql-proxy"', jobs)
    assert '"--private-ip"' in jobs
    assert '"--auto-iam-authn"' in jobs
    assert '"--address=0.0.0.0"' in jobs
    assert '"--port=5432"' in jobs
    assert '"prepare"' in jobs
    assert '"--qualification-id"' in jobs
    assert '"staging-cloud-sql-v1"' in jobs
    assert 'depends_on = ["cloud-sql-proxy"]' in jobs
    assert 'egress = "PRIVATE_RANGES_ONLY"' in jobs
    assert "network    = var.network_id" in jobs
    assert "subnetwork = var.subnetwork_id" in jobs
    assert re.search(r'name\s*=\s*"AIFA_STORAGE_BACKEND"', jobs)
    assert re.search(r'value\s*=\s*"postgres"', jobs)
    assert re.search(r'name\s*=\s*"AIFA_POSTGRES_DSN"', jobs)
    assert re.search(r'name\s*=\s*"AIFA_STORAGE_EXPECTED_SCHEMA_VERSION"', jobs)
    assert re.search(r'name\s*=\s*"AIFA_POSTGRES_RUNTIME_ROLE"', jobs)
    assert re.search(r'name\s*=\s*"AIFA_POSTGRES_RETENTION_ROLE"', jobs)
    assert "value_source" not in jobs
    assert "secret_key_ref" not in jobs
    assert "password" not in jobs.lower()
    assert 'strcontains(var.backend_image, "@sha256:")' in variables
    assert 'strcontains(var.cloud_sql_proxy_image, "@sha256:")' in variables
    assert 'module "managed_state_jobs"' in staging
    for attribute in (
        "network_id",
        "subnetwork_id",
        "instance_connection_name",
        "database_name",
    ):
        assert re.search(
            rf"{attribute}\s*=\s*module\.managed_state\.{attribute}",
            staging,
        )
    assert re.search(r"backend_image\s*=\s*var\.backend_image", staging)
    assert 'strcontains(var.backend_image, "@sha256:")' in staging_variables
    assert artifact_registry_prefix in staging_variables
    assert "TF_VAR_backend_image: ${{ vars.GCP_BACKEND_IMAGE }}" in workflow
    assert "TF_VAR_frontend_image: ${{ vars.GCP_FRONTEND_IMAGE }}" in workflow
    assert "TF_VAR_qdrant_secret_version: ${{ vars.GCP_QDRANT_SECRET_VERSION }}" in workflow
    assert f'cloud_sql_proxy_image    = "{artifact_registry_prefix}' in staging
    assert "gcr.io/cloud-sql-connectors/cloud-sql-proxy@sha256:" not in staging


def test_cloud_sql_recovery_contract_requires_two_temporary_validated_targets() -> None:
    contract = json.loads(RECOVERY_CONTRACT.read_text(encoding="utf-8"))

    assert contract["schema_version"] == "1"
    assert contract["status"] == "prepare_and_retention_executed_recovery_pending"
    assert contract["private_demo_mvp_gate"] is False
    assert contract["execution_priority"] == "deferred_post_mvp"
    assert contract["source"] == {
        "project_id": "comfforts-369117",
        "region": "us-west1",
        "instance": "aifa-staging-postgres",
        "database": "aifa",
    }
    assert contract["objectives"] == {
        "rpo_target_minutes": 5,
        "rto_target_hours": 4,
        "rto_measurement": (
            "start_of_backup_restore_through_sequential_validation_of_both_targets"
        ),
        "regional_disaster_recovery_claimed": False,
    }
    assert contract["qualification"]["synthetic_data_only"] is True
    assert contract["qualification"]["qualification_id"] == "staging-cloud-sql-v1"
    assert contract["qualification"]["provider_calls_allowed"] is False
    assert contract["qualification"]["operator_image_registry"] == (
        "us-west1-docker.pkg.dev/comfforts-369117/aifa-containers"
    )
    assert contract["qualification"]["mixed_registry_hosts_allowed"] is False
    assert contract["privilege_bootstrap"]["temporary_owner"] == ("vtalwar.w@comfforts.com")
    assert contract["privilege_bootstrap"]["database_role"] == "cloudsqlsuperuser"
    assert contract["privilege_bootstrap"]["data_api_access"] == ("temporarily_allow_then_disallow")
    assert contract["privilege_bootstrap"]["remove_after_bootstrap"] is True
    assert [target["method"] for target in contract["targets"]] == [
        "on_demand_backup_restore",
        "point_in_time_recovery",
    ]
    assert all(target["temporary_instance"] for target in contract["targets"])
    assert all(not target["retained_backups_after_delete"] for target in contract["targets"])
    assert all(target["validate_before_delete"] for target in contract["targets"])
    assert all(target["delete_after_validation"] for target in contract["targets"])
    assert contract["evidence"]["artifact"] == (
        "backend/artifacts/release/deployment/cloud-sql-recovery.v1.json"
    )
    assert "backup_name" in contract["evidence"]["required_fields"]
    assert contract["evidence"]["must_record_secret_values"] is False


def test_cloud_sql_recovery_wizard_removes_elevation_and_temporary_instances() -> None:
    wizard = (TERRAFORM_ROOT / "scripts/qualify-cloud-sql-recovery.sh").read_text(encoding="utf-8")

    assert "TOTAL_STAGES=7" in wizard
    assert 'ask BACKEND_IMAGE "Paste the Artifact Registry backend image' in wizard
    assert "gcloud artifacts docker images describe" in wizard
    assert 'gcloud sql users create "$OWNER_DATABASE_USER"' in wizard
    assert 'gcloud sql instances execute-sql "$SOURCE_INSTANCE"' in wizard
    assert 'gcloud sql users delete "$OWNER_DATABASE_USER"' in wizard
    owner_delete_commands = wizard.split('gcloud sql users delete "$OWNER_DATABASE_USER"')[1:]
    assert len(owner_delete_commands) == 2
    assert all(
        "--type=" not in command.partition("--quiet")[0] for command in owner_delete_commands
    )
    assert "--data-api-access=ALLOW_DATA_API" in wizard
    assert "--data-api-access=DISALLOW_DATA_API" in wizard
    assert 'gcloud run jobs execute "$MIGRATION_JOB"' in wizard
    assert 'gcloud run jobs execute "$RETENTION_JOB"' in wizard
    assert "jq -er" in wizard
    assert ".spec.template.spec.template.spec.containers[]" in wizard
    assert ".template.template.containers[]" not in wizard
    assert "ai_finance_assistant.persistence.qualification" in wizard
    assert '--description="$BACKUP_DESCRIPTION"' in wizard
    assert "BACKUP_ID=$(gcloud sql backups create" not in wizard
    assert "--format='none'" in wizard
    assert "--filter=\"description='$BACKUP_DESCRIPTION'\"" in wizard
    assert '--format="value(name)"' in wizard
    assert 'BACKUP_RUN=$(gcloud sql backups describe "$BACKUP_NAME"' in wizard
    assert 'BACKUP_ID="${BACKUP_RUN##*/}"' in wizard
    assert 'gcloud sql backups restore "$BACKUP_NAME"' in wizard
    restore_command = wizard.split('gcloud sql backups restore "$BACKUP_NAME"', maxsplit=1)[1]
    restore_command = restore_command.partition("--quiet")[0]
    assert "--backup-instance=" not in restore_command
    assert "wait_for_sql_operation()" in wizard
    assert "SQL_OPERATION_TIMEOUT_SECONDS=$((4 * 60 * 60))" in wizard
    assert 'BACKUP_RESTORE_OPERATION=$(gcloud sql backups restore "$BACKUP_NAME"' in wizard
    assert (
        'PITR_OPERATION=$(gcloud sql instances clone "$SOURCE_INSTANCE" "$PITR_INSTANCE"' in wizard
    )
    assert 'wait_for_sql_operation "$BACKUP_RESTORE_OPERATION" "Backup restore"' in wizard
    assert 'wait_for_sql_operation "$PITR_OPERATION" "Point-in-time clone"' in wizard
    assert "is $status; continuing to wait" in wizard
    assert wizard.count("--async") >= 2
    assert wizard.count("--no-deletion-protection") >= 3
    assert "--no-enable-point-in-time-recovery" in wizard
    assert "--database-flags=cloudsql.iam_authentication=on" in wizard
    assert ".settings.deletionProtectionEnabled == false" in wizard
    assert ".settings.backupConfiguration.enabled == false" in wizard
    assert ".settings.retainBackupsOnDelete == false" in wizard
    assert 'gcloud sql instances clone "$SOURCE_INSTANCE" "$PITR_INSTANCE"' in wizard
    assert 'gcloud sql instances delete "$BACKUP_RESTORE_INSTANCE"' in wizard
    assert 'gcloud sql instances delete "$PITR_INSTANCE"' in wizard
    assert 'gcloud sql backups delete "$BACKUP_NAME"' in wizard
    assert '--arg backup_name "$BACKUP_NAME"' in wizard
    assert 'status: "qualified"' in wizard
    assert "cloud-sql-recovery.v1.json" in wizard
    assert "ask_secret" not in wizard.split("# STAGES:", maxsplit=1)[1]
    assert "password=" not in wizard.lower()


def test_terraform_workflow_is_manual_keyless_and_staging_only_for_apply() -> None:
    workflow = (REPO_ROOT / ".github/workflows/terraform.yml").read_text(encoding="utf-8")

    assert "pull_request:" in workflow
    assert "workflow_dispatch:" in workflow
    assert "id-token: write" in workflow
    assert "google-github-actions/auth@" in workflow
    assert "vars.GCP_WORKLOAD_IDENTITY_PROVIDER" in workflow
    assert "vars.GCP_DEPLOY_SERVICE_ACCOUNT" in workflow
    assert "terraform plan" in workflow
    assert "Validate staging workload root" in workflow
    assert "Create reviewed staging workload plan" in workflow
    assert "staging-workloads.tfplan.json" in workflow
    assert "terraform apply" not in workflow
    assert "credentials_json" not in workflow
    assert "secrets." not in workflow
