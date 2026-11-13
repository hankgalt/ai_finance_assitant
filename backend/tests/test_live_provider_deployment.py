"""Owner-only live-provider deployment contract and operator safety."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = REPO_ROOT / "contracts/providers/live-mode.v1.json"
TERRAFORM_ROOT = REPO_ROOT / "infrastructure/terraform"
OPERATOR = TERRAFORM_ROOT / "scripts/configure-live-providers.sh"


def _contract() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(CONTRACT_PATH.read_text(encoding="utf-8")))


def test_live_mode_contract_records_the_owner_approved_boundary() -> None:
    contract = _contract()

    assert contract["schema_version"] == "1"
    assert contract["status"] == "repository_implemented_live_run_pending"
    assert contract["target"]["audience"] == "owner_only"
    assert contract["target"]["viewer_admission"] == "disabled"
    assert contract["selection"] == {
        "provider_mode": "live",
        "model_mode": "openai_live",
        "model": "gpt-6.1-sol",
        "market_provider": "massive",
        "news_provider": "tavily",
        "credential_free_remains_default": True,
        "automatic_fallback_allowed": False,
        "openai_behavior_change": False,
    }
    assert contract["rights"]["massive"]["plan"] == "Stocks Basic"
    assert contract["rights"]["massive"]["viewer_display_allowed"] is False
    assert contract["rights"]["massive"]["durable_provider_cache_allowed"] is False
    assert contract["rights"]["tavily"]["plan"] == "Researcher"
    assert contract["rights"]["tavily"]["personal_financial_context_allowed"] is False
    assert contract["rights"]["tavily"]["monthly_credits"] == 1000
    assert contract["rights"]["tavily"]["durable_cache_allowed"] is False
    assert contract["rights"]["openai"]["store"] is False
    assert contract["rights"]["openai"]["real_application_prompts_allowed"] is True
    assert contract["rights"]["openai"]["api_training_opt_in_approved"] is False
    assert contract["operational_limits"] == {
        "model_requests_per_run": 10,
        "market_requests_per_operation": 5,
        "market_requests_per_minute": 5,
        "news_requests_per_run": 5,
        "news_requests_per_minute": 10,
        "run_deadline_seconds": 180,
        "openai_monthly_usd_hard_limit": 20,
        "openai_monthly_usd_hard_limit_enforcement": ("provider_account_control_owner_attestation"),
        "application_monetary_cost_calculator": "not_implemented",
        "gcp_budget_is_separate": True,
    }
    assert contract["runtime_configuration"]["new_application_environment_names"] == []


def test_live_mode_terraform_is_secret_version_pinned_and_credential_free_by_default() -> None:
    module = (TERRAFORM_ROOT / "modules/application_workloads/main.tf").read_text(encoding="utf-8")
    module_variables = (TERRAFORM_ROOT / "modules/application_workloads/variables.tf").read_text(
        encoding="utf-8"
    )
    foundation = (TERRAFORM_ROOT / "environments/staging/main.tf").read_text(encoding="utf-8")
    workloads = (TERRAFORM_ROOT / "environments/staging-workloads/main.tf").read_text(
        encoding="utf-8"
    )

    assert 'default     = "credential_free"' in module_variables
    assert 'AIFA_MODEL_MODE                      = "credential_free"' in module
    assert 'AIFA_PROVIDER_MODE                   = "credential_free"' in module
    for setting, value in _contract()["runtime_configuration"]["settings"].items():
        assert setting in module
        assert f'= "{value}"' in module
    for secret_id in _contract()["secrets"]["ids"].values():
        assert secret_id in foundation or secret_id in workloads
    assert "google_secret_manager_secret_version" not in foundation
    assert "google_secret_manager_secret.live_provider" in foundation
    assert 'role      = "roles/secretmanager.secretAccessor"' in foundation
    assert "var.openai_secret_version" in module
    assert "var.massive_secret_version" in module
    assert "var.tavily_secret_version" in module
    assert "latest" not in module
    assert "AIFA_ALPHA_VANTAGE_API_KEY" not in module


def test_live_provider_operator_never_reads_or_persists_secret_payloads() -> None:
    operator = OPERATOR.read_text(encoding="utf-8")

    assert "gcloud secrets versions access" not in operator
    assert "--data-file" not in operator
    assert "ask_secret" not in operator.split("# STAGES", maxsplit=1)[-1]
    assert "AIFA_OPENAI_API_KEY" in operator
    assert "AIFA_MASSIVE_API_KEY" in operator
    assert "AIFA_TAVILY_API_KEY" in operator
    assert "GCP_OPENAI_SECRET_VERSION" in operator
    assert "GCP_MASSIVE_SECRET_VERSION" in operator
    assert "GCP_TAVILY_SECRET_VERSION" in operator
    assert "finance-assistant-backend:$REVISION" in operator
    assert "finance-assistant-frontend:$REVISION" in operator
    assert "make mirror-merged-main-images and make set-deployment-image-variables" in operator
    assert '"run.googleapis.com/default-url-disabled"' in operator
    assert '"roles/iap.httpsResourceAccessor"' in operator
    assert 'EDGE_BACKEND_SERVICES=("aifa-staging-backend-edge"' in operator
    assert "DISABLE LIVE PROVIDERS" in operator
    assert "provider response" in operator
    assert "raw prompt" in operator


def test_demo_runtime_lifecycle_resets_destroyed_live_secret_selectors() -> None:
    lifecycle = (TERRAFORM_ROOT / "scripts/bootstrap-staging.sh").read_text(encoding="utf-8")

    assert "reset_live_provider_github_variables" in lifecycle
    assert "GCP_LIVE_PROVIDER_MODE" in lifecycle
    assert "GCP_OPENAI_SECRET_VERSION" in lifecycle
    assert "GCP_MASSIVE_SECRET_VERSION" in lifecycle
    assert "GCP_TAVILY_SECRET_VERSION" in lifecycle
    assert lifecycle.index('reset_live_provider_github_variables\n    say "The demo runtime') < (
        lifecycle.index(
            "finish\n    return",
            lifecycle.index('reset_live_provider_github_variables\n    say "The demo runtime'),
        )
    )
