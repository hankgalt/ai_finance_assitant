"""Repository-owned delivery, provenance, and short-lived identity controls."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, cast

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_ROOT = REPO_ROOT / ".github/workflows"
DELIVERY_CONTRACT = REPO_ROOT / "contracts/deployment/delivery-policy.v1.json"
DELIVERY_EVIDENCE = REPO_ROOT / "backend/artifacts/release/deployment/delivery-controls.v1.json"
ACTION_REF = re.compile(r"^\s*-?\s*uses:\s*([^\s#]+)(?:\s+#.*)?$", re.MULTILINE)
IMMUTABLE_ACTION_REF = re.compile(r"^[^@]+@[0-9a-f]{40}$")
PINNED_PNPM_SETUP = re.compile(
    r"- uses: pnpm/action-setup@ea17c68df8912ef543352723c149a84f56e3d413 # v6\.1\.0\n"
    r"\s+with:\n"
    r"\s+version: 11\.25\.0(?:\n|$)"
)
GITLEAKS_WITH_AUTOMATIC_TOKEN = re.compile(
    r"- uses: gitleaks/gitleaks-action@[0-9a-f]{40}[^\n]*\n"
    r"\s+env:\n"
    r"\s+GITHUB_TOKEN: \$\{\{ github\.token \}\}(?:\n|$)"
)
PINNED_TRIVY_ACTION = "aquasecurity/trivy-action@ed142fd0673e97e23eac54620cfb913e5ce36c25 # v0.36.0"
PINNED_TRIVY_VERSION = "version: v0.76.2"


def _contract() -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(DELIVERY_CONTRACT.read_text(encoding="utf-8")),
    )


def _workflow(name: str) -> str:
    return (WORKFLOW_ROOT / name).read_text(encoding="utf-8")


def _pinned_stage_image(dockerfile: str, image_pattern: str, stage: str) -> str:
    images: list[str] = re.findall(
        rf"^FROM ({image_pattern}@sha256:[0-9a-f]{{64}}) AS {stage}$",
        dockerfile,
        re.MULTILINE,
    )
    assert len(images) == 1, f"expected one digest-pinned {stage} stage on {image_pattern}"
    return images[0]


def _assert_container_image_policy(backend: str, frontend: str) -> None:
    backend_builder = _pinned_stage_image(
        backend,
        r"python:3\.12\.\d+-slim-bookworm",
        "builder",
    )
    backend_runtime = _pinned_stage_image(
        backend,
        r"python:3\.12\.\d+-slim-bookworm",
        "runtime",
    )
    assert backend_builder == backend_runtime
    assert len(re.findall(r"^FROM ", backend, re.MULTILINE)) == 2
    assert re.search(r"^ARG UV_VERSION=\d+\.\d+\.\d+$", backend, re.MULTILINE)
    runtime_stage = backend.split(f"FROM {backend_runtime} AS runtime", maxsplit=1)[1]
    assert "pip install" not in runtime_stage
    assert "uv sync" not in runtime_stage
    assert "COPY --from=builder --chown=10001:10001 /app /app" in runtime_stage
    assert (
        "COPY --from=builder --chown=10001:10001 /opt/fastembed-cache "
        "/opt/fastembed-cache" in runtime_stage
    )
    assert "USER 10001:10001" in backend
    assert "HF_HUB_OFFLINE=1" in backend
    assert "FastEmbedEncoder" in backend

    _pinned_stage_image(
        frontend,
        r"node:24\.\d+\.\d+-alpine3\.24",
        "build",
    )
    _pinned_stage_image(
        frontend,
        r"nginx/nginx-unprivileged:1\.30\.\d+-alpine3\.24-slim",
        "runtime",
    )
    assert "nginxinc/nginx-unprivileged" not in frontend
    assert len(re.findall(r"^FROM [^\n]+@sha256:[0-9a-f]{64}", frontend, re.MULTILINE)) == 2
    assert "USER 101:101" in frontend
    assert "COPY contracts/ /workspace/contracts/" in frontend


def test_delivery_contract_records_activated_identity_and_remaining_gates() -> None:
    contract = _contract()

    assert contract["schema_version"] == "1"
    assert contract["status"] == (
        "identity_and_environment_controls_activated_staging_foundation_provisioned"
    )
    assert contract["repository"] == "hankgalt/ai_finance_assitant"
    assert contract["automated_cloud_deployment_enabled"] is False
    assert contract["long_lived_gcp_credentials_allowed"] is False
    assert contract["identity"]["method"] == "github_oidc_workload_identity_federation"
    assert contract["identity"]["credential_payload_in_github"] is False
    assert contract["identity"]["credential_payload_in_repository"] is False
    assert contract["identity"]["subject_format"] == (
        "repo:OWNER@OWNER-ID/REPO@REPO-ID:environment:ENVIRONMENT"
    )
    assert contract["identity"]["external_configuration_status"] == (
        "provisioned_and_identity_smoke_qualified"
    )
    assert contract["environments"] == {
        "staging": {
            "required_reviewer": "hankgalt",
            "prevent_self_review": False,
            "deployment_branch": "main",
            "external_configuration_status": "configured_smoke_passed",
        },
        "production": {
            "required_reviewer": "hankgalt",
            "prevent_self_review": False,
            "deployment_branch": "main",
            "external_configuration_status": "configured_smoke_passed",
        },
    }


def test_delivery_evidence_is_capability_owned_and_truthful_about_activated_controls() -> None:
    evidence = json.loads(DELIVERY_EVIDENCE.read_text(encoding="utf-8"))

    assert evidence["schema_version"] == "1"
    assert evidence["status"] == "repository_controls_and_cloud_identity_qualified"
    assert evidence["secret_payloads_recorded"] is False
    assert evidence["cloud_resources_mutated"] is True
    assert evidence["github_repository_settings_mutated"] is True
    assert [item["run_id"] for item in evidence["github_qualification"]] == [
        42887806884,
        42887806684,
        42887435575,
        42887806753,
    ]
    assert all(item["result"].startswith("passed") for item in evidence["github_qualification"])
    assert [item["run_id"] for item in evidence["identity_smoke_qualification"]] == [
        42903648350,
        42906846762,
        42903653548,
    ]
    assert evidence["external_qualification_pending"] == [
        "Terraform workflow qualification after this branch is merged",
        "Cloud SQL real-service migration, retention, backup/restore, and recovery qualification",
        "staging workload, IAP/load-balancer, no-direct-bypass, deployment, and "
        "rollback qualification",
    ]


def test_workflows_are_known_and_third_party_actions_are_immutable() -> None:
    expected = {
        "ci.yml",
        "cloud-identity-smoke.yml",
        "images.yml",
        "security.yml",
        "terraform.yml",
    }
    observed = {path.name for path in WORKFLOW_ROOT.glob("*.yml")}
    assert observed == expected

    for path in WORKFLOW_ROOT.glob("*.yml"):
        content = path.read_text(encoding="utf-8")
        assert "pull_request_target:" not in content
        assert "runs-on: self-hosted" not in content
        references = ACTION_REF.findall(content)
        assert references
        assert all(IMMUTABLE_ACTION_REF.fullmatch(reference) for reference in references)


def test_ci_runs_credential_free_checks_and_real_postgres_qualification() -> None:
    workflow = _workflow("ci.yml")

    assert "permissions:\n  contents: read" in workflow
    assert "uv sync --frozen" in workflow
    assert "pnpm install --frozen-lockfile" in workflow
    assert "ruff format --check" in workflow
    assert "ruff check" in workflow
    assert "mypy" in workflow
    assert "python -m pytest -q" in workflow
    assert "AIFA_TEST_POSTGRES_DSN" in workflow
    assert "pytest -q -m postgres tests/test_managed_persistence.py" in workflow
    assert "pnpm format:check" in workflow
    assert "pnpm lint" in workflow
    assert "pnpm typecheck" in workflow
    assert "pnpm test" in workflow
    assert "pnpm build" in workflow
    assert "postgres:17.11-alpine3.23@sha256:" in workflow


def test_pnpm_setup_is_explicit_when_package_manifest_is_not_at_repo_root() -> None:
    for workflow_name in ("ci.yml", "security.yml"):
        workflow = _workflow(workflow_name)
        assert PINNED_PNPM_SETUP.search(workflow), workflow_name


def test_security_pipeline_covers_dependencies_secrets_code_and_images() -> None:
    security = _workflow("security.yml")
    images = _workflow("images.yml")

    assert "dependency-review-action" in security
    assert "pip-audit==" in security
    assert "pnpm audit --prod" in security
    assert "gitleaks-action" in security
    assert "github/codeql-action/init" in security
    assert "github/codeql-action/analyze" in security
    assert "aquasecurity/trivy-action" in security
    assert "scan-type: fs" in security
    assert "aquasecurity/trivy-action" in images
    assert "scan-type: image" in images
    assert "actions/attest-build-provenance" in images
    assert "push-to-registry: true" in images
    assert "packages: write" in images
    assert "attestations: write" in images
    assert "id-token: write" in images


def test_gitleaks_receives_only_the_automatic_read_only_pull_request_token() -> None:
    security = _workflow("security.yml")

    assert GITLEAKS_WITH_AUTOMATIC_TOKEN.search(security)
    assert "pull-requests: read" in security
    assert 'GITLEAKS_ENABLE_COMMENTS: "false"' in security


def test_trivy_scans_pin_a_supported_action_and_scanner_version() -> None:
    security = _workflow("security.yml")
    images = _workflow("images.yml")

    assert security.count(PINNED_TRIVY_ACTION) == 1
    assert security.count(PINNED_TRIVY_VERSION) == 1
    assert images.count(PINNED_TRIVY_ACTION) == 2
    assert images.count(PINNED_TRIVY_VERSION) == 2


def test_cloud_identity_smoke_is_manual_environment_gated_and_keyless() -> None:
    workflow = _workflow("cloud-identity-smoke.yml")

    assert "workflow_dispatch:" in workflow
    assert "environment: ${{ inputs.environment }}" in workflow
    assert "id-token: write" in workflow
    assert "google-github-actions/auth" in workflow
    assert "vars.GCP_WORKLOAD_IDENTITY_PROVIDER" in workflow
    assert "vars.GCP_DEPLOY_SERVICE_ACCOUNT" in workflow
    assert "vars.GCP_PROJECT_ID" in workflow
    assert "gcloud projects describe" in workflow
    assert "credentials_json" not in workflow
    assert "secrets." not in workflow


def test_container_builds_are_non_root_pinned_and_base_path_scoped() -> None:
    backend = (REPO_ROOT / "infrastructure/container/backend/Dockerfile").read_text(
        encoding="utf-8"
    )
    frontend = (REPO_ROOT / "infrastructure/container/frontend/Dockerfile").read_text(
        encoding="utf-8"
    )
    nginx = (REPO_ROOT / "infrastructure/container/frontend/nginx.conf").read_text(encoding="utf-8")

    _assert_container_image_policy(backend, frontend)
    assert "location = /finance_assistant/api" in nginx
    assert "location /finance_assistant/api/" in nginx
    assert "location /finance_assistant/" in nginx
    assert "location / {" in nginx
    assert "return 404" in nginx

    compose = (REPO_ROOT / "compose.yaml").read_text(encoding="utf-8")
    image_references = re.findall(r"^\s+image:\s+(\S+)$", compose, re.MULTILINE)
    assert image_references
    assert all(re.search(r"@sha256:[0-9a-f]{64}$", ref) for ref in image_references)


def test_container_policy_accepts_supported_runtime_patch_updates() -> None:
    backend = (REPO_ROOT / "infrastructure/container/backend/Dockerfile").read_text(
        encoding="utf-8"
    )
    frontend = (REPO_ROOT / "infrastructure/container/frontend/Dockerfile").read_text(
        encoding="utf-8"
    )

    updated_backend, backend_updates = re.subn(
        r"python:3\.12\.\d+-slim-bookworm@sha256:[0-9a-f]{64}",
        f"python:3.12.17-slim-bookworm@sha256:{'1' * 64}",
        backend,
    )
    updated_frontend, node_updates = re.subn(
        r"node:24\.\d+\.\d+-alpine3\.24@sha256:[0-9a-f]{64}",
        f"node:24.23.0-alpine3.24@sha256:{'2' * 64}",
        frontend,
    )
    updated_frontend, nginx_updates = re.subn(
        r"nginx/nginx-unprivileged:1\.30\.\d+-alpine3\.24-slim@sha256:[0-9a-f]{64}",
        f"nginx/nginx-unprivileged:1.30.7-alpine3.24-slim@sha256:{'3' * 64}",
        updated_frontend,
    )

    assert (backend_updates, node_updates, nginx_updates) == (2, 1, 1)
    _assert_container_image_policy(updated_backend, updated_frontend)


@pytest.mark.parametrize(
    ("dockerfile", "qualified_pattern", "unqualified", "expected_updates"),
    [
        (
            "backend",
            r"python:3\.12\.\d+-slim-bookworm@sha256:[0-9a-f]{64}",
            f"python:3.15.0-slim-bookworm@sha256:{'4' * 64}",
            2,
        ),
        (
            "frontend",
            r"node:24\.\d+\.\d+-alpine3\.24@sha256:[0-9a-f]{64}",
            f"node:26.13.0-alpine3.24@sha256:{'5' * 64}",
            1,
        ),
    ],
)
def test_container_policy_rejects_unqualified_runtime_line_updates(
    dockerfile: str,
    qualified_pattern: str,
    unqualified: str,
    expected_updates: int,
) -> None:
    backend = (REPO_ROOT / "infrastructure/container/backend/Dockerfile").read_text(
        encoding="utf-8"
    )
    frontend = (REPO_ROOT / "infrastructure/container/frontend/Dockerfile").read_text(
        encoding="utf-8"
    )
    if dockerfile == "backend":
        backend, updates = re.subn(qualified_pattern, unqualified, backend)
    else:
        frontend, updates = re.subn(qualified_pattern, unqualified, frontend)

    assert updates == expected_updates
    with pytest.raises(AssertionError):
        _assert_container_image_policy(backend, frontend)


def test_dependency_updates_and_delivery_ownership_are_repository_owned() -> None:
    dependabot = (REPO_ROOT / ".github/dependabot.yml").read_text(encoding="utf-8")
    codeowners = (REPO_ROOT / ".github/CODEOWNERS").read_text(encoding="utf-8")

    assert dependabot.count("package-ecosystem:") == 5
    for ecosystem in ("github-actions", "pip", "npm", "docker"):
        assert f"package-ecosystem: {ecosystem}" in dependabot
    backend_docker_updates = dependabot.split(
        'directory: "/infrastructure/container/backend"', maxsplit=1
    )[1].split("- package-ecosystem:", maxsplit=1)[0]
    frontend_docker_updates = dependabot.split(
        'directory: "/infrastructure/container/frontend"', maxsplit=1
    )[1]
    assert "dependency-name: python" in backend_docker_updates
    assert "version-update:semver-major" in backend_docker_updates
    assert "version-update:semver-minor" in backend_docker_updates
    assert "dependency-name: node" in frontend_docker_updates
    assert "version-update:semver-major" in frontend_docker_updates
    assert "dependency-name: nginx/nginx-unprivileged" in frontend_docker_updates
    assert "version-update:semver-minor" in frontend_docker_updates
    for path in ("/.github/workflows/", "/contracts/deployment/", "/infrastructure/"):
        assert f"{path} @hankgalt" in codeowners
