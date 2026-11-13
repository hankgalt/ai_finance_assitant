"""Assembled private-demo qualification contracts and operator boundaries."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, cast

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "contracts/deployment/private-demo-qualification.v1.json"
INFRASTRUCTURE_POLICY = REPO_ROOT / "contracts/deployment/infrastructure-policy.v1.json"
WIZARD = REPO_ROOT / "infrastructure/terraform/scripts/qualify-private-demo.sh"
DEPLOYMENT_CONFIG = REPO_ROOT / "frontend/playwright.deployment.config.ts"
DEPLOYMENT_JOURNEY = REPO_ROOT / "frontend/e2e/deployment/private-demo.spec.ts"


def _contract() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(CONTRACT.read_text(encoding="utf-8")))


def test_private_demo_contract_qualifies_only_the_credential_free_owner_mvp() -> None:
    contract = _contract()

    assert contract["schema_version"] == "1"
    assert contract["status"] == "repository_implemented_live_run_pending"
    assert contract["target"] == {
        "origin": "https://apps.comfforts.com",
        "base_path": "/finance_assistant",
        "owner": "vtalwar.w@comfforts.com",
    }
    assert contract["provider_boundary"] == {
        "provider_mode": "credential_free",
        "model_mode": "credential_free",
        "live_provider_secrets_allowed": False,
        "provider_rights_broadened": False,
    }
    assert contract["admission"] == {
        "mode": "owner_only",
        "viewer_admission": "disabled",
        "anonymous": "denied",
        "direct_origin": "denied",
    }
    assert contract["browser"]["interactive_iap_login"] is True
    assert contract["browser"]["credentials_captured"] is False
    assert contract["browser"]["persistent_auth_state_allowed"] is False
    assert contract["synthetic_state"]["cleanup_required"] is True
    assert contract["synthetic_state"]["preexisting_state_may_be_deleted"] is False
    assert contract["qualification"]["live_operator_run"] == "pending"
    assert contract["qualification"]["evidence_pattern"] == (
        "backend/artifacts/release/deployment/private-demo-<revision>.v1.json"
    )


def test_private_demo_contract_aggregates_prior_gates_and_exact_live_journeys() -> None:
    contract = _contract()

    assert contract["required_evidence"] == [
        "backend/artifacts/release/deployment/demo-runtime-lifecycle.v1.json",
        "backend/artifacts/release/deployment/application-workloads.v1.json",
        (
            "backend/artifacts/knowledge/deployment/"
            "staging-release-a737f8e9e935f8afc05e16fc7148e3a185b32086.json"
        ),
        (
            "backend/artifacts/knowledge/deployment/"
            "staging-runtime-key-rotation-86146b6227285015665b84cbfa3f4ce0395cd618-"
            "v1-to-v2.json"
        ),
        (
            "backend/artifacts/release/deployment/"
            "private-edge-3327a231fcc197d4a8032de7b8a30523fecc1eda.v1.json"
        ),
    ]
    assert contract["journeys"] == [
        "owner_iap_identity",
        "managed_readiness_and_active_knowledge",
        "assistant_run_and_sse_replay",
        "portfolio_import_snapshot_and_context",
        "credential_free_market_provenance",
        "goal_projection",
        "history_archive_and_delete",
        "inspector_run_event_reconciliation",
        "accessibility_critical_views",
        "synthetic_state_cleanup",
    ]
    assert contract["deferred"] == [
        "live_model_and_provider_activation",
        "viewer_admission",
        "backup_restore_and_pitr",
        "ha_and_disaster_recovery",
        "load_soak_slo_alert_and_incident_rehearsal",
        "authenticated_public_member_access",
    ]


def test_infrastructure_policy_points_to_pending_integrated_qualification() -> None:
    policy = cast(dict[str, Any], json.loads(INFRASTRUCTURE_POLICY.read_text(encoding="utf-8")))

    assert policy["private_demo_qualification"] == {
        "contract": "contracts/deployment/private-demo-qualification.v1.json",
        "operator_entry_point": ("infrastructure/terraform/scripts/qualify-private-demo.sh"),
        "status": "repository_implemented_live_run_pending",
    }
    assert policy["operational_status"]["integrated_product_journeys"] == (
        "repository_implemented_live_run_pending"
    )


def test_private_demo_operator_is_interactive_fail_closed_and_secret_free() -> None:
    wizard = WIZARD.read_text(encoding="utf-8")
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    default_config = (REPO_ROOT / "frontend/playwright.config.ts").read_text(encoding="utf-8")
    deployment_config = DEPLOYMENT_CONFIG.read_text(encoding="utf-8")
    journey = DEPLOYMENT_JOURNEY.read_text(encoding="utf-8")

    assert "qualify-private-demo:" in makefile
    assert "qualify-private-demo.sh" in makefile
    assert '[[ "$(git branch --show-current)" == "main" ]]' in wizard
    assert '[[ -z "$(git status --porcelain)" ]]' in wizard
    assert "vtalwar.w@comfforts.com" in wizard
    assert "AIFA_PROVIDER_MODE" in wizard and "credential_free" in wizard
    assert "AIFA_MODEL_MODE" in wizard
    assert "allUsers" in wizard and "allAuthenticatedUsers" in wizard
    assert "AIFA_RUN_DEPLOYED_QUALIFICATION=true" in wizard
    assert "private-demo-${REVISION}.v1.json" in wizard
    assert wizard.index('install -m 0644 "$RAW_EVIDENCE" "$EVIDENCE_FILE"') > (
        wizard.index('FINAL_BACKEND=$(gcloud run services describe "$BACKEND_SERVICE"')
    )
    assert "ask_secret" not in wizard.split("# STAGES:", maxsplit=1)[1]
    assert "set_secret " not in wizard.split("# STAGES:", maxsplit=1)[1]

    assert 'testIgnore: ["deployment/**"]' in default_config
    assert 'baseURL: "https://apps.comfforts.com"' in deployment_config
    assert "headless: false" in deployment_config
    assert 'screenshot: "off"' in deployment_config
    assert 'trace: "off"' in deployment_config
    assert "workers: 1" in deployment_config
    assert "webServer" not in deployment_config
    assert "AIFA_RUN_DEPLOYED_QUALIFICATION" in journey
    assert "Complete Google/IAP sign-in" in journey
    assert "finally" in journey
    assert "cleanup" in journey.casefold()
    assert "AxeBuilder" in journey

    syntax = subprocess.run(
        ["bash", "-n", str(WIZARD)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert syntax.returncode == 0, syntax.stderr
