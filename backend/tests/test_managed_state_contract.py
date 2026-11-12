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
    assert manifest["status"] == (
        "active_disposable_runtime_knowledge_rotation_qualified_edge_pending"
    )
    assert manifest["private_demo_mvp"] == {
        "scope": "owner_operated_deployed_feature_parity",
        "target_machine_tier": "db-g1-small",
        "runtime_lifecycle": "on_demand_create_destroy_recreate",
        "store_initialization": "empty_each_create",
        "destroy_discards_principal_owned_state": True,
        "backup_pitr_required": False,
        "recovery_qualification": "deferred_post_mvp",
        "production_readiness_claimed": False,
        "current_provisioned_foundation_matches_target": True,
        "reproducibility_foundation_may_persist": [
            "terraform_state",
            "artifact_registry_images",
            "workload_identity",
            "non_secret_configuration",
            "private_networking",
        ],
    }
    assert manifest["application_state"] == {
        "service": "cloud_sql_postgresql",
        "edition": "enterprise",
        "postgres_major_version": 17,
        "project_id": "comfforts-369117",
        "region": "us-west1",
        "availability": "single_zone",
        "machine_tier": "db-g1-small",
        "provisioned_machine_tier": "db-g1-small",
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
        "external_configuration_status": "active_runnable_readback_2026_11_12",
        "connection": {
            "transport": "direct_vpc_egress_private_ipv4",
            "authentication": "cloud_sql_auth_proxy_automatic_iam",
            "database_password_required": False,
            "dsn_secret_required": False,
            "operator_image_registry": ("us-west1-docker.pkg.dev/comfforts-369117/aifa-containers"),
            "mixed_registry_hosts_allowed": False,
            "operator_jobs": "active_after_qualified_recreate",
        },
    }
    assert manifest["response_cache"] == {
        "deployed_adapter": "disabled",
        "managed_redis_provisioned": False,
        "correctness_requires_cache": False,
    }
    assert manifest["backup_and_recovery"]["automated_backups_enabled"] is False
    assert manifest["backup_and_recovery"]["automated_daily_backups"] == 0
    assert manifest["backup_and_recovery"]["pitr_enabled"] is False
    assert manifest["backup_and_recovery"]["pitr_transaction_log_days"] == 0
    assert manifest["backup_and_recovery"]["qualification_required_for_mvp"] is False
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
    assert manifest["staging"]["networking_foundation_retained"] is True
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
    assert qdrant["release_status"] == "qualified"
    assert qdrant["release_revision"] == "a737f8e9e935f8afc05e16fc7148e3a185b32086"
    assert qdrant["runtime_key_rotation_contract"] == (
        "contracts/deployment/runtime-key-rotation.v1.json"
    )
    assert qdrant["runtime_key_rotation_status"] == "qualified"
    assert qdrant["runtime_rotation_revision"] == "86146b6227285015665b84cbfa3f4ce0395cd618"
    assert qdrant["runtime_key_rotation_evidence"] == (
        "backend/artifacts/knowledge/deployment/"
        "staging-runtime-key-rotation-86146b6227285015665b84cbfa3f4ce0395cd618-"
        "v1-to-v2.json"
    )
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
    secret_policy = manifest["encryption_and_secrets"]
    assert secret_policy["secret_service"] == "standard_secret_manager"
    assert secret_policy["secret_replication"] == "user_managed"
    assert secret_policy["secret_payload_locations"] == ["us-west1"]
    assert secret_policy["cloud_run_native_secret_injection"] is True
    assert secret_policy["runtime_secret_version_reference"] == ("positive_numeric_version_only")
    assert secret_policy["approved_access_pattern"] == ("native_cloud_run_environment_injection")
