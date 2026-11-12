"""Private HTTPS edge, IAP admission, and direct-origin deployment contracts."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, cast

REPO_ROOT = Path(__file__).resolve().parents[2]
TERRAFORM_ROOT = REPO_ROOT / "infrastructure/terraform"
EDGE_MODULE = TERRAFORM_ROOT / "modules/private_edge"
EDGE_ROOT = TERRAFORM_ROOT / "environments/staging-edge"
EDGE_CONTRACT = REPO_ROOT / "contracts/deployment/private-edge.v1.json"
EDGE_WIZARD = TERRAFORM_ROOT / "scripts/configure-private-edge.sh"
EDGE_EVIDENCE = (
    REPO_ROOT / "backend/artifacts/release/deployment/"
    "private-edge-3327a231fcc197d4a8032de7b8a30523fecc1eda.v1.json"
)


def _contract() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(EDGE_CONTRACT.read_text(encoding="utf-8")))


def test_private_edge_contract_is_owner_only_and_fail_closed() -> None:
    contract = _contract()

    assert contract["schema_version"] == "1"
    assert contract["status"] == "live_edge_qualified_integrated_journeys_pending"
    assert contract["target"] == {
        "origin": "https://apps.comfforts.com",
        "base_path": "/finance_assistant",
        "region": "us-west1",
        "project_id": "comfforts-369117",
        "project_number": "730340912967",
    }
    assert contract["routing"]["http_behavior"] == "permanent_redirect_to_https"
    assert contract["routing"]["unmatched_path_behavior"] == ("iap_protected_frontend_404")
    assert contract["routing"]["path_rewrite"] == {
        "backend_exact": "/finance_assistant/api -> /api",
        "backend_descendants": "/finance_assistant/api/* -> /api/*",
        "frontend": False,
    }
    assert contract["routing"]["cloud_cdn_enabled"] is False
    assert contract["routing"]["routes"] == [
        {
            "paths": ["/finance_assistant/api", "/finance_assistant/api/*"],
            "backend": "aifa-staging-backend-edge",
            "cloud_run_service": "aifa-staging-backend",
        },
        {
            "paths": ["/finance_assistant", "/finance_assistant/*"],
            "backend": "aifa-staging-frontend-edge",
            "cloud_run_service": "aifa-staging-frontend",
        },
    ]
    assert contract["iap"]["placement"] == "both_load_balancer_backend_services"
    assert contract["iap"]["initial_members"] == ["user:vtalwar.w@comfforts.com"]
    assert contract["iap"]["viewer_admission"] == ("disabled_until_separately_approved")
    assert contract["iap"]["broad_members_allowed"] is False
    assert contract["origin_boundary"]["default_cloud_run_url_disabled"] is True
    assert contract["origin_boundary"]["anonymous_invoker_allowed"] is False
    assert contract["provider_boundary"] == {
        "provider_mode": "credential_free",
        "model_mode": "credential_free",
        "provider_rights_broadened": False,
    }
    assert contract["qualification"] == {
        "repository_contract_tests": "required",
        "terraform_fmt_validate_plan": "required",
        "live_iap_tls_dns_no_bypass": "qualified_evidence_recorded",
        "live_evidence": (
            "backend/artifacts/release/deployment/"
            "private-edge-3327a231fcc197d4a8032de7b8a30523fecc1eda.v1.json"
        ),
        "live_revision": "3327a231fcc197d4a8032de7b8a30523fecc1eda",
        "integrated_product_journeys": "next_slice",
    }


def test_private_edge_live_evidence_is_qualified_and_secret_free() -> None:
    evidence = cast(dict[str, Any], json.loads(EDGE_EVIDENCE.read_text(encoding="utf-8")))

    assert evidence["status"] == "qualified"
    assert evidence["revision"] == "3327a231fcc197d4a8032de7b8a30523fecc1eda"
    assert evidence["target"] == "https://apps.comfforts.com/finance_assistant"
    assert evidence["access"] == {
        "members": ["user:vtalwar.w@comfforts.com"],
        "anonymous": "denied",
    }
    assert evidence["controls"] == {
        "tls_certificate": "ACTIVE",
        "http_redirect": "passed",
        "exact_path_routing": "passed",
        "api_prefix_rewrite": "passed",
        "signed_identity_boundary": "passed",
        "direct_origin": "denied",
        "unmatched_path": "authenticated_404",
        "provider_mode": "credential_free",
        "terraform_drift": "none",
    }
    assert evidence["secret_payloads_recorded"] is False
    assert evidence["integrated_product_journeys"] == "pending_next_slice"


def test_private_edge_terraform_owns_exact_routes_tls_iap_and_invocation() -> None:
    module = (EDGE_MODULE / "main.tf").read_text(encoding="utf-8")
    variables = (EDGE_MODULE / "variables.tf").read_text(encoding="utf-8")
    root = (EDGE_ROOT / "main.tf").read_text(encoding="utf-8")
    outputs = (EDGE_MODULE / "outputs.tf").read_text(encoding="utf-8")

    assert module.count('resource "google_compute_region_network_endpoint_group"') == 1
    assert 'network_endpoint_type = "SERVERLESS"' in module
    assert 'resource "google_compute_backend_service" "application"' in module
    assert 'load_balancing_scheme = "EXTERNAL_MANAGED"' in module
    assert "timeout_sec" not in module
    assert "enable_cdn            = false" in module
    assert "oauth2_client_id_wo" in module
    assert "oauth2_client_secret_wo" in module
    assert "oauth2_client_id     =" not in module
    assert "oauth2_client_secret =" not in module
    assert 'resource "google_iap_web_backend_service_iam_member"' in module
    assert 'role                = "roles/iap.httpsResourceAccessor"' in module
    assert 'resource "google_cloud_run_v2_service_iam_member" "iap_invoker"' in module
    assert 'role     = "roles/run.invoker"' in module
    assert "local.iap_service_agent" in module
    assert 'resource "google_compute_global_address" "application"' in module
    assert 'resource "google_compute_managed_ssl_certificate"' in module
    assert "domains = [var.domain]" in module
    assert 'resource "google_compute_target_https_proxy"' in module
    assert 'port_range            = "443"' in module
    assert "https_redirect         = true" in module
    assert 'redirect_response_code = "PERMANENT_REDIRECT"' in module
    assert 'port_range            = "80"' in module
    assert "backend_api_exact_path" in module
    assert "backend_api_prefix_path" in module
    assert 'path_prefix_rewrite = "/api"' in module
    assert 'path_prefix_rewrite = "/api/"' in module
    assert "paths   = local.frontend_application_paths" in module
    assert 'default_service = google_compute_backend_service.application["frontend"].id' in module
    assert '"${var.base_path}/api"' in module
    assert '"${var.base_path}/api/*"' in module
    assert 'var.base_path, "${var.base_path}/*"' in module
    assert "allUsers" not in module
    assert "allAuthenticatedUsers" not in module
    assert "ephemeral   = true" in variables
    assert 'ephemeral "google_secret_manager_secret_version" "iap_oauth"' in root
    assert "version = var.iap_oauth_secret_version" in root
    assert 'iap_members                     = ["user:vtalwar.w@comfforts.com"]' in root
    assert 'domain                          = "apps.comfforts.com"' in root
    assert 'base_path                       = "/finance_assistant"' in root
    assert "generated_id" in outputs
    assert (
        'global/backendServices/${google_compute_backend_service.application["backend"].generated_id}'
        in outputs
    )


def test_iap_oauth_payload_is_ephemeral_write_only_and_not_repository_managed() -> None:
    shared = (TERRAFORM_ROOT / "shared/main.tf").read_text(encoding="utf-8")
    edge = "\n".join(path.read_text(encoding="utf-8") for path in sorted(EDGE_ROOT.glob("*.tf")))
    module = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(EDGE_MODULE.glob("*.tf"))
    )

    assert 'resource "google_secret_manager_secret" "staging_iap_oauth"' in shared
    assert 'secret_id           = "aifa-staging-iap-oauth-client-secret"' in shared
    assert "user_managed" in shared
    assert "location = var.region" in shared
    assert "deletion_protection" in shared
    assert 'role      = "roles/secretmanager.secretAccessor"' in shared
    assert "module.staging_identity.service_account_email" in shared
    assert 'resource "google_secret_manager_secret_version"' not in shared + edge + module
    assert 'ephemeral "google_secret_manager_secret_version"' in edge
    assert "secret_data" in edge
    assert "oauth2_client_secret_wo" in module
    assert "oauth2_client_secret =" not in module


def test_backend_audience_moves_from_explicit_sentinel_to_generated_edge_id() -> None:
    workloads = (TERRAFORM_ROOT / "environments/staging-workloads/main.tf").read_text(
        encoding="utf-8"
    )
    variables = (TERRAFORM_ROOT / "environments/staging-workloads/variables.tf").read_text(
        encoding="utf-8"
    )
    lifecycle = (TERRAFORM_ROOT / "scripts/bootstrap-staging.sh").read_text(encoding="utf-8")

    assert "iap_audience                   = var.iap_audience" in workloads
    assert 'default     = "/projects/730340912967/global/backendServices/0"' in variables
    assert 'EDGE_BACKEND_SERVICE="aifa-staging-backend-edge"' in lifecycle
    assert 'gcloud compute backend-services describe "$EDGE_BACKEND_SERVICE"' in lifecycle
    assert 'export TF_VAR_iap_audience="$RESOLVED_IAP_AUDIENCE"' in lifecycle
    assert 'export TF_VAR_iap_audience="$FAIL_CLOSED_IAP_AUDIENCE"' in lifecycle
    assert "gh variable set GCP_IAP_AUDIENCE" in lifecycle


def test_private_edge_workflow_is_conditional_keyless_plan_only() -> None:
    workflow = (REPO_ROOT / ".github/workflows/terraform.yml").read_text(encoding="utf-8")

    assert "Validate staging private-edge root" in workflow
    assert "Create reviewed staging private-edge plan" in workflow
    assert "prefix=edge" in workflow
    assert "TF_VAR_iap_oauth_client_id: ${{ vars.GCP_IAP_OAUTH_CLIENT_ID }}" in workflow
    assert "TF_VAR_iap_oauth_secret_version: ${{ vars.GCP_IAP_OAUTH_SECRET_VERSION }}" in workflow
    assert "staging-edge.tfplan.json" in workflow
    assert "GCP_IAP_AUDIENCE || '/projects/730340912967/global/backendServices/0'" in workflow
    assert "terraform apply" not in workflow
    assert "secrets." not in workflow
    assert "credentials_json" not in workflow


def test_private_edge_wizard_never_accepts_secret_and_reviews_cutover_teardown() -> None:
    wizard = EDGE_WIZARD.read_text(encoding="utf-8")
    stages = wizard.split("# STAGES:", maxsplit=1)[1]
    up = (TERRAFORM_ROOT / "scripts/private-edge-up.sh").read_text(encoding="utf-8")
    down = (TERRAFORM_ROOT / "scripts/private-edge-down.sh").read_text(encoding="utf-8")

    assert 'configure-private-edge.sh" up' in up
    assert 'configure-private-edge.sh" down' in down
    assert 'ACTION="${1:-}"' in stages
    assert "for tool in gcloud terraform git gh jq curl" in stages
    assert '[[ "$(git branch --show-current)" == "main" ]]' in stages
    assert '[[ -z "$(git status --porcelain)" ]]' in stages
    assert "ask_secret" not in stages
    assert "The secret value must be entered directly in GCP" not in stages
    assert "Do not paste the secret into this terminal" in stages
    assert "add $OWNER_ACCOUNT as the only test user" in stages
    assert "aifa-staging-iap-oauth-client-secret" in stages
    assert "Create or select the Web application client" in stages
    assert "Reuse enabled Secret Manager version" in stages
    assert "Reusing the existing enabled secret version without reading its payload" in stages
    assert "the shared plan contains changes outside the private-edge metadata boundary" in stages
    assert 'read_only_roles[\\"roles/iap.viewer\\"]' in stages
    assert 'terraform -chdir="$EDGE_ROOT" plan' in stages
    assert 'confirm "Apply only this reviewed private-edge plan?"' in stages
    assert 'apply_workload_audience "$IAP_AUDIENCE"' in stages
    assert 'verify_backend_audience "$IAP_AUDIENCE"' in stages
    assert stages.index('apply_workload_audience "$IAP_AUDIENCE"') < stages.index(
        'stage "Point DNS to the reviewed edge"'
    )
    assert "Remove the apps.comfforts.com A record before releasing its global IP" in stages
    assert 'apply_workload_audience "$FAIL_CLOSED_IAP_AUDIENCE"' in stages
    assert "DNS and the workload audience will still be reconciled" in stages
    assert "no workload resources will be recreated during edge teardown" in stages
    assert 'terraform -chdir="$EDGE_ROOT" plan -destroy' in stages
    assert '[[ "$confirmation" == "DESTROY PRIVATE EDGE" ]]' in stages
    assert stages.index('apply_workload_audience "$FAIL_CLOSED_IAP_AUDIENCE"') < (
        stages.index('terraform -chdir="$EDGE_ROOT" plan -destroy')
    )
    assert "allUsers" in stages
    assert "allAuthenticatedUsers" in stages
    assert "TLS_SERVING_TIMEOUT_SECONDS=1800" in stages
    assert "TLS_RETRY_SECONDS=15" in stages
    assert "wait_for_https_iap_challenge" in stages
    assert 'sleep "$TLS_RETRY_SECONDS"' in stages
    assert "HTTPS/IAP readiness did not converge" in stages
    assert "these prove the API prefix rewrite" in stages
    assert 'DIRECT_PATH="/api/health/live"' in stages
    assert 'DIRECT_PATH="/finance_assistant/healthz"' in stages
    assert '(.role != "roles/iap.httpsResourceAccessor" and .role != "roles/run.invoker")' in stages
    assert "] == [$iap_agent]" in stages
    assert "private-edge-${REVISION}.v1.json" in stages
    assert 'integrated_product_journeys: "pending_next_slice"' in stages
    assert "set_secret " not in stages

    for script in (EDGE_WIZARD, *sorted((TERRAFORM_ROOT / "scripts").glob("private-edge-*.sh"))):
        result = subprocess.run(
            ["bash", "-n", str(script)],
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr


def test_https_readiness_retries_transient_tls_failures_and_is_bounded(
    tmp_path: Path,
) -> None:
    wizard = EDGE_WIZARD.read_text(encoding="utf-8")
    function_start = wizard.index("wait_for_https_iap_challenge()")
    function_end = wizard.index("\n}\n\n# ── Stage 1", function_start) + len("\n}")
    readiness_function = wizard[function_start:function_end]

    counter = tmp_path / "curl-attempts"
    fake_curl = tmp_path / "curl"
    fake_curl.write_text(
        """#!/usr/bin/env bash
attempt=0
if [[ -f "$AIFA_CURL_COUNTER" ]]; then
  attempt=$(<"$AIFA_CURL_COUNTER")
fi
attempt=$((attempt + 1))
printf '%s' "$attempt" >"$AIFA_CURL_COUNTER"
if (( attempt < 3 )); then
  exit 35
fi
printf '302'
""",
        encoding="utf-8",
    )
    fake_curl.chmod(0o755)

    harness = f"""set -euo pipefail
say() {{ :; }}
warn() {{ :; }}
TLS_SERVING_TIMEOUT_SECONDS=5
TLS_RETRY_SECONDS=0
{readiness_function}
wait_for_https_iap_challenge 'https://apps.comfforts.com/finance_assistant'
"""
    result = subprocess.run(
        ["bash", "-c", harness],
        text=True,
        capture_output=True,
        check=False,
        env={
            **os.environ,
            "AIFA_CURL_COUNTER": str(counter),
            "PATH": f"{tmp_path}:{os.environ['PATH']}",
        },
    )

    assert result.returncode == 0, result.stderr
    assert counter.read_text(encoding="utf-8") == "3"

    counter.unlink()
    fake_curl.write_text(
        """#!/usr/bin/env bash
printf '1' >"$AIFA_CURL_COUNTER"
exit 35
""",
        encoding="utf-8",
    )
    bounded_harness = f"""set -euo pipefail
say() {{ :; }}
warn() {{ :; }}
TLS_SERVING_TIMEOUT_SECONDS=0
TLS_RETRY_SECONDS=0
{readiness_function}
if wait_for_https_iap_challenge 'https://apps.comfforts.com/finance_assistant'; then
  exit 9
fi
"""
    bounded_result = subprocess.run(
        ["bash", "-c", bounded_harness],
        text=True,
        capture_output=True,
        check=False,
        env={
            **os.environ,
            "AIFA_CURL_COUNTER": str(counter),
            "PATH": f"{tmp_path}:{os.environ['PATH']}",
        },
    )

    assert bounded_result.returncode == 0, bounded_result.stderr
    assert counter.read_text(encoding="utf-8") == "1"
