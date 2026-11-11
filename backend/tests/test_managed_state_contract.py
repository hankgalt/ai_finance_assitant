"""Managed deployment-state contract tests."""

import json
from pathlib import Path
from typing import Any, cast


def _manifest() -> dict[str, Any]:
    root = Path(__file__).parents[2]
    return cast(
        dict[str, Any],
        json.loads(
            (root / "contracts/deployment/managed-state.v1.json").read_text(encoding="utf-8")
        ),
    )


def test_owner_approved_managed_state_selection_is_exact() -> None:
    manifest = _manifest()

    assert manifest["schema_version"] == "1"
    assert manifest["status"] == ("staging_foundation_provisioned_recovery_qualification_pending")
    assert manifest["application_state"] == {
        "service": "cloud_sql_postgresql",
        "edition": "enterprise",
        "postgres_major_version": 17,
        "project_id": "comfforts-369117",
        "region": "us-west1",
        "availability": "single_zone",
        "machine_tier": "db-f1-micro",
        "storage": {"type": "ssd", "capacity_gib": 10, "service_minimum": True},
        "connection_pools": {
            "application_max": 2,
            "checkpoint_max": 2,
            "aggregate_per_container_max": 4,
        },
        "application_schema_version": 4,
        "deployed_store_initialization": "empty",
        "local_development_backend": "sqlite",
        "staging_instance": "aifa-staging-postgres",
        "external_configuration_status": "provisioned_recovery_qualification_pending",
        "connection": {
            "transport": "direct_vpc_egress_private_ipv4",
            "authentication": "cloud_sql_auth_proxy_automatic_iam",
            "database_password_required": False,
            "dsn_secret_required": False,
            "operator_image_registry": ("us-west1-docker.pkg.dev/comfforts-369117/aifa-containers"),
            "mixed_registry_hosts_allowed": False,
            "operator_jobs": "migration_and_prepare_executed_recovery_pending",
        },
    }
    assert manifest["response_cache"] == {
        "deployed_adapter": "disabled",
        "managed_redis_provisioned": False,
        "correctness_requires_cache": False,
    }
    assert manifest["backup_and_recovery"]["automated_daily_backups"] == 7
    assert manifest["backup_and_recovery"]["pitr_transaction_log_days"] == 3
    assert manifest["run_recovery"] == {
        "stale_running_cutoff": "api_run_deadline_seconds",
        "terminal_status": "failed",
        "error_code": "RUN_INTERRUPTED",
        "fresh_running_rows_preserved": True,
        "terminal_results_immutable": True,
        "whole_run_atomicity_claimed": False,
    }
    assert manifest["staging"]["separation"] == "same_project"
    assert manifest["staging"]["foundation_provisioned"] is True
    assert manifest["staging"]["recovery_policy"] == (
        "contracts/deployment/recovery-policy.v1.json"
    )


def test_qdrant_exception_and_single_operator_boundary_are_explicit() -> None:
    manifest = _manifest()
    qdrant = manifest["qdrant"]
    approval = manifest["delivery_approval"]

    assert qdrant["region"] == "us-central1"
    assert qdrant["private_demo_cross_region_exception"] is True
    assert qdrant["principal_owned_data_allowed"] is False
    assert qdrant["production_sla_claimed"] is False
    assert approval["repository"] == "hankgalt/ai_finance_assitant"
    assert approval["repository_visibility"] == "public"
    assert approval["github_plan"] == "pro"
    assert approval["production_approvers"] == ["hankgalt"]
    assert approval["independent_backup_approver"] is None
    assert approval["prevent_self_review"] is False
    assert approval["single_operator_limitation_accepted"] is True


def test_managed_state_contract_contains_no_secret_payloads() -> None:
    manifest = _manifest()
    serialized = json.dumps(manifest, sort_keys=True).casefold()

    forbidden = (
        "authorization: bearer",
        "postgresql://",
        "private_key_id",
        "service_account_key",
    )
    assert all(name not in serialized for name in forbidden)
    assert manifest["qdrant"]["api_key_committed"] is False
    assert manifest["encryption_and_secrets"]["secret_payloads_in_terraform"] is False
    assert manifest["encryption_and_secrets"]["long_lived_gcp_keys_in_github"] is False
    assert manifest["encryption_and_secrets"]["cloud_run_native_regional_secret_injection"] is False
    assert manifest["encryption_and_secrets"]["later_provider_secret_access_pattern"] == (
        "unresolved_stop_gate"
    )
