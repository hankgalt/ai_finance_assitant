"""Standalone App Platform authority-foundation checks."""

from __future__ import annotations

import re
import tomllib
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ProjectAuthorityTest(unittest.TestCase):
    def test_project_shell_is_self_contained(self) -> None:
        expected_files = (
            ".gitignore",
            "AGENTS.md",
            "GLOSSARY.md",
            "Makefile",
            "README.md",
            "docs/01_product_requirements.md",
            "docs/02_architecture_decision_records.md",
            "docs/03_system_design.md",
            "docs/04_implementation_plan.md",
            "docs/05_evaluation_strategy.md",
            "docs/06_threat_model.md",
            "docs/README.md",
            "docs/repository_layout.md",
            "contracts/README.md",
            "contracts/validation.py",
            "contracts/test-vectors/manifest.v1.json",
            "fixtures/__init__.py",
            "fixtures/applications.py",
            "fixtures/identity.py",
            "fixtures/reference_edge.py",
            "fixtures/registrations/manifest.v1.json",
            "edge/__init__.py",
            "edge/_assertions.py",
            "edge/_generation.py",
            "edge/_identity.py",
            "edge/_routing.py",
            "edge/_runtime.py",
            "edge/verification.py",
            "prompts/README.md",
            "prompts/starting_prompt.md",
            "pyproject.toml",
            "tests/test_contracts.py",
            "tests/test_edge_runtime.py",
            "tests/test_fixtures.py",
            "tests/test_governance.py",
            "tests/fixtures/assertion-test-keys.jwk.json",
            "tests/fixtures/oidc-test-private.jwk.json",
            "uv.lock",
        )

        self.assertTrue(all((PROJECT_ROOT / path).is_file() for path in expected_files))

    def test_makefile_exposes_a_portable_non_mutating_check(self) -> None:
        makefile = (PROJECT_ROOT / "Makefile").read_text(encoding="utf-8")

        self.assertIn(
            "check: governance-check contract-check fixture-check",
            makefile,
        )
        self.assertIn("PYTHONDONTWRITEBYTECODE=1", makefile)
        self.assertIn("python3", makefile)
        self.assertNotIn("../", makefile)
        self.assertNotIn("terraform apply", makefile)
        self.assertNotIn("gcloud", makefile)

    def test_locked_runtime_foundation_is_extraction_safe(self) -> None:
        pyproject = tomllib.loads(
            (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        )
        lock = tomllib.loads((PROJECT_ROOT / "uv.lock").read_text(encoding="utf-8"))
        makefile = (PROJECT_ROOT / "Makefile").read_text(encoding="utf-8")
        packages = {package["name"]: package for package in lock["package"]}

        self.assertEqual(pyproject["project"]["requires-python"], ">=3.12")
        self.assertEqual(
            pyproject["project"]["dependencies"],
            [
                "Authlib>=1.9,<1.10",
                "cryptography>=50,<51",
                "google-cloud-kms>=3.19,<3.20",
                "google-cloud-firestore>=2.34,<2.35",
                "google-cloud-storage>=3.17,<3.18",
                "google-crc32c>=1.9,<1.10",
                "httpx>=0.28,<0.29",
                "starlette>=1.10,<1.11",
                "uvicorn>=0.54,<0.55",
            ],
        )
        self.assertFalse(pyproject["tool"]["uv"]["package"])
        self.assertEqual(packages["authlib"]["version"], "1.9.8")
        self.assertEqual(packages["cryptography"]["version"], "50.0.2")
        self.assertEqual(packages["google-cloud-kms"]["version"], "3.19.0")
        self.assertEqual(packages["google-cloud-firestore"]["version"], "2.34.1")
        self.assertEqual(packages["google-cloud-storage"]["version"], "3.17.1")
        self.assertEqual(packages["google-crc32c"]["version"], "1.9.0")
        self.assertEqual(packages["httpx"]["version"], "0.28.1")
        self.assertEqual(packages["starlette"]["version"], "1.10.0")
        self.assertEqual(packages["uvicorn"]["version"], "0.54.0")
        self.assertIn("hash", packages["authlib"]["sdist"])
        self.assertIn("hash", packages["cryptography"]["sdist"])
        self.assertIn("hash", packages["google-cloud-kms"]["sdist"])
        self.assertIn("hash", packages["google-cloud-firestore"]["sdist"])
        self.assertIn("hash", packages["google-cloud-storage"]["sdist"])
        self.assertIn("hash", packages["google-crc32c"]["sdist"])
        self.assertIn("hash", packages["httpx"]["sdist"])
        self.assertIn("hash", packages["starlette"]["sdist"])
        self.assertIn("hash", packages["uvicorn"]["sdist"])
        self.assertIn("runtime-check", makefile)
        self.assertNotIn("uv sync", makefile)
        self.assertNotIn("uv lock", makefile)

    def test_local_ignore_policy_excludes_sensitive_runtime_state(self) -> None:
        ignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")

        for pattern in (
            ".env",
            ".venv/",
            "**/.terraform/",
            "*.tfstate",
            "*.tfplan",
            "*.tfvars",
        ):
            self.assertIn(pattern, ignore)
        self.assertNotIn(".terraform.lock.hcl", ignore)

    def test_agent_instructions_route_to_platform_authority(self) -> None:
        instructions = (PROJECT_ROOT / "AGENTS.md").read_text(encoding="utf-8")

        self.assertIn("docs/README.md", instructions)
        self.assertIn("GLOSSARY.md", instructions)
        self.assertIn("docs/01_product_requirements.md", instructions)
        self.assertIn("docs/02_architecture_decision_records.md", instructions)
        self.assertIn("docs/03_system_design.md", instructions)
        self.assertIn("docs/06_threat_model.md", instructions)
        self.assertIn("contracts/README.md", instructions)
        self.assertIn("docs/repository_layout.md", instructions)
        self.assertIn("make -C apps-platform check", instructions)
        self.assertIn("one bounded slice per pull request", instructions)
        self.assertIn("leave each change uncommitted until approval", instructions)
        self.assertIn("Merge it before starting the next documented slice", instructions)
        self.assertIn(
            "AP-M5 selects infrastructure and Live-qualification planning boundaries only",
            instructions,
        )
        self.assertIn(
            "AP-M6 authorizes only repository implementation of the networked Shared Edge",
            instructions,
        )

    def test_documentation_truthfully_records_planning_and_evidence_status(self) -> None:
        index = (PROJECT_ROOT / "docs/README.md").read_text(encoding="utf-8")
        layout = (PROJECT_ROOT / "docs/repository_layout.md").read_text(encoding="utf-8")
        overview = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        normalized_index = " ".join(index.split())
        normalized_overview = " ".join(overview.split())

        self.assertIn(
            "AP-M6 implementation in progress",
            normalized_index,
        )
        self.assertIn("Contract (`C`) evidence", normalized_index)
        self.assertIn("Fixture (`F`) evidence", normalized_index)
        self.assertIn(
            "Live (`L`) and Adoption (`A`) evidence remain unavailable",
            normalized_index,
        )
        self.assertIn("AP-M6", overview)
        self.assertIn("AP-M4 remains Fixture-qualified", normalized_overview)
        self.assertIn(
            "attachment-provider and proxy behavior remain unavailable",
            normalized_overview,
        )
        self.assertIn("planning consistency only", normalized_index)
        self.assertIn("Integration draft", index)
        self.assertIn("AP-M6 assertions and application verification recorded", layout)
        self.assertIn("`contracts/`", layout)
        self.assertIn("`fixtures/`", layout)
        self.assertIn("Version 1 schemas", layout)
        self.assertIn("three independent Fixture Applications", layout)
        self.assertIn("history-preserving subtree extraction", layout)
        self.assertIn("Do not create a nested `.git`", layout)

    def test_ap_m3_authorities_have_complete_unique_identifiers(self) -> None:
        plan = (PROJECT_ROOT / "docs/04_implementation_plan.md").read_text(
            encoding="utf-8"
        )
        evaluation = (PROJECT_ROOT / "docs/05_evaluation_strategy.md").read_text(
            encoding="utf-8"
        )
        threat_model = (PROJECT_ROOT / "docs/06_threat_model.md").read_text(
            encoding="utf-8"
        )

        work_packages = re.findall(r"^### (AP-M3-W\d+) ·", plan, re.MULTILINE)
        evaluation_gates = re.findall(
            r"^### (AP-EVAL-M3-\d{2}) ·", evaluation, re.MULTILINE
        )
        threats = re.findall(r"^### (AP-TM-\d{3}) ·", threat_model, re.MULTILINE)

        self.assertEqual(
            work_packages, [f"AP-M3-W{index}" for index in range(1, 7)]
        )
        self.assertEqual(
            evaluation_gates,
            [f"AP-EVAL-M3-{index:02d}" for index in range(1, 10)],
        )
        self.assertEqual(
            threats,
            [f"AP-TM-{index:03d}" for index in range(1, 15)],
        )

    def test_product_requirements_have_unique_stable_identifiers(self) -> None:
        requirements = (PROJECT_ROOT / "docs/01_product_requirements.md").read_text(
            encoding="utf-8"
        )
        observed = re.findall(r"^### (AP-(?:PR|QR)-\d{3}) ·", requirements, re.MULTILINE)
        expected = {
            *(f"AP-PR-{index:03d}" for index in range(1, 10)),
            *(f"AP-QR-{index:03d}" for index in range(1, 7)),
        }

        self.assertEqual(set(observed), expected)
        self.assertEqual(len(observed), len(set(observed)))

    def test_product_requirements_preserve_platform_boundaries(self) -> None:
        requirements = (PROJECT_ROOT / "docs/01_product_requirements.md").read_text(
            encoding="utf-8"
        )

        for boundary in (
            "feature authorization",
            "Application State",
            "Platform State",
            "Fixture Applications",
            "Integration Draft",
            "Finance Assistant migration",
            "no platform capability is implemented",
        ):
            self.assertIn(boundary, requirements)

    def test_architecture_decisions_are_unique_and_trace_requirements(self) -> None:
        decisions = (PROJECT_ROOT / "docs/02_architecture_decision_records.md").read_text(
            encoding="utf-8"
        )
        observed = re.findall(r"^## (ADR-\d{3}) ·", decisions, re.MULTILINE)

        self.assertEqual(
            observed,
            [
                "ADR-001",
                "ADR-002",
                "ADR-003",
                "ADR-004",
                "ADR-005",
                "ADR-006",
                "ADR-007",
                "ADR-008",
                "ADR-009",
            ],
        )
        self.assertEqual(decisions.count("Status: Accepted"), 9)
        normalized_decisions = " ".join(decisions.split())
        for identifier in (
            "AP-PR-001",
            "AP-PR-002",
            "AP-PR-003",
            "AP-PR-004",
            "AP-PR-005",
            "AP-PR-006",
            "AP-PR-007",
            "AP-PR-008",
            "AP-PR-009",
            "AP-QR-001",
            "AP-QR-002",
            "AP-QR-003",
            "AP-QR-004",
            "AP-QR-006",
        ):
            self.assertIn(identifier, decisions)

        for live_topology_decision in (
            "comfforts-platform-non-prod",
            "apps-staging.comfforts.com",
            "gcp-cloud-run-v1",
            "platform-owned Shared VPC",
            "explicit, separately approved operator actions",
            "no Terraform configuration",
        ):
            self.assertIn(live_topology_decision, decisions)

        for live_identity_decision in (
            "authorization-code flow",
            "Consumer Google",
            "accounts and Google Workspace accounts",
            "Firestore Native",
            "absolute lifetime of eight hours",
            "EC_SIGN_P256_SHA256",
            "maximum lifetime of 60 seconds",
            "at most 30 seconds of clock skew",
            "at least every 90 days",
            "24-hour verification overlap",
            "at most 15 minutes",
            "does not claim distributed replay prevention",
        ):
            self.assertIn(live_identity_decision, normalized_decisions)

        for state_and_operator_decision in (
            "remote GCS backend with native state locking and object versioning",
            "Each Fixture Application uses a separate state bucket",
            "at least 90 days old",
            "at least 20 newer generations",
            "No platform root uses `terraform_remote_state`",
            "GitHub Actions using OIDC and GCP Workload Identity Federation",
            "A pull-request plan is advisory",
            "Routine workstation apply is prohibited",
            "Provider-console changes are drift",
            "no backend bucket, state, workflow, identity, credential, plan",
        ):
            self.assertIn(state_and_operator_decision, normalized_decisions)

        for activation_and_rollback_decision in (
            "content-addressed, immutable compiled configuration object",
            "traffic assignment to one immutable edge revision",
            "There is no separate registration endpoint or database",
            "100 percent of edge traffic",
            "provider error or incomplete apply stops for inspection",
            "Successful readback must agree across source, state, provider, and runtime",
            "initial rollback-time objective is 15 minutes",
            "available for at least 24 hours",
            "1,800-second TTL",
            "checks authoritative and recursive resolution with `dig`",
            "does not touch `apps.comfforts.com`",
            "no registration file, configuration bucket, object, edge revision, DNS",
        ):
            self.assertIn(activation_and_rollback_decision, normalized_decisions)

        for evidence_and_cost_decision in (
            "dedicated Cloud Logging bucket",
            "retention is seven days",
            "does not intentionally retain source IP addresses",
            "dedicated private GCS evidence bucket",
            "Evidence retention is 30 days",
            "Screenshots, authenticated browser state, raw provider responses",
            "App Platform Owner is the initial security, availability, privacy, and cost incident contact",
            "monthly budget of USD 20",
            "notifications at 50, 80, and 100 percent",
            "Shared Edge | 0 | 2 | 1 vCPU | 512 MiB | 20",
            "Each Fixture Application | 0 | 1 | 1 vCPU | 512 MiB | 10",
            "at most 55 minutes per connection",
            "no CDN, WAF, HSM key, production replica",
            "Cleanup policy is evaluated in dry-run mode first",
            "platform project pays for Shared Edge resources",
            "no log or evidence bucket, budget, alert, runtime limit",
        ):
            self.assertIn(evidence_and_cost_decision, normalized_decisions)

    def test_shared_edge_decisions_preserve_exclusive_ownership(self) -> None:
        decisions = (PROJECT_ROOT / "docs/02_architecture_decision_records.md").read_text(
            encoding="utf-8"
        )

        for boundary in (
            "certificate secures a hostname",
            "not a certificate boundary",
            "only authoritative input",
            "No resource may be managed by both states",
            "does not transfer ownership",
            "does not move them",
            "Direct manual route changes are drift",
        ):
            self.assertIn(boundary, decisions)

    def test_admission_decision_does_not_become_feature_authorization(self) -> None:
        decisions = (PROJECT_ROOT / "docs/02_architecture_decision_records.md").read_text(
            encoding="utf-8"
        )
        glossary = (PROJECT_ROOT / "GLOSSARY.md").read_text(encoding="utf-8")

        for mode in ("**Public:**", "**Authenticated:**", "**Restricted:**"):
            self.assertIn(mode, decisions)
        for boundary in (
            "Being listed does not grant admission",
            "being admitted does not grant a Feature Entitlement",
            "Email addresses are display or contact attributes",
            "next request or new streaming-connection boundary",
            "market-data-style Feature Entitlement",
            "does not alter its current access policy",
        ):
            self.assertIn(boundary, decisions)
        for term in (
            "## Admission Decision",
            "## Verified Identity Context",
            "## Application Principal",
            "## Feature Entitlement",
        ):
            self.assertIn(term, glossary)

    def test_fixture_first_decision_keeps_application_adoption_separate(self) -> None:
        decisions = (PROJECT_ROOT / "docs/02_architecture_decision_records.md").read_text(
            encoding="utf-8"
        )
        glossary = (PROJECT_ROOT / "GLOSSARY.md").read_text(encoding="utf-8")
        layout = (PROJECT_ROOT / "docs/repository_layout.md").read_text(encoding="utf-8")

        for boundary in (
            "before any real application may be adopted",
            "remain outside\nPlatform State",
            "no Finance Assistant code",
            "is not platform acceptance evidence",
            "A cutover must leave each resource with one active state owner",
            "Finance Assistant-owned slice and evidence",
        ):
            self.assertIn(boundary, decisions)
        self.assertIn("## Application Adoption", glossary)
        self.assertIn("app-owned test state", layout)

    def test_provider_runtime_prompt_loads_authority_without_copying_it(
        self,
    ) -> None:
        prompt = (PROJECT_ROOT / "prompts/starting_prompt.md").read_text(encoding="utf-8")
        prompt_index = (PROJECT_ROOT / "prompts/README.md").read_text(encoding="utf-8")
        normalized_prompt = " ".join(prompt.split())

        for authority in (
            "AGENTS.md",
            "docs/README.md",
            "GLOSSARY.md",
            "docs/01_product_requirements.md",
            "docs/02_architecture_decision_records.md",
            "docs/03_system_design.md",
            "docs/04_implementation_plan.md",
            "docs/05_evaluation_strategy.md",
            "docs/06_threat_model.md",
            "docs/repository_layout.md",
            "contracts/README.md",
            "fixtures/registrations/README.md",
        ):
            self.assertIn(authority, prompt)
        for boundary in (
            "Wait for owner approval before editing",
            "Leave Finance Assistant requirements, code, infrastructure, Terraform state, DNS",
            "An Integration Draft is not Application Adoption",
            "credential-free, deterministic, and non-mutating",
            "updated `main` after the AP-M5 pull request has merged",
            "propose AP-M6, the smallest locally testable networked provider-runtime slice",
            "network server/framework, dependency policy",
            "exact live header, request-body, response-body, non-streaming timeout",
            "Do not write Terraform",
        ):
            self.assertIn(boundary, normalized_prompt)
        self.assertNotIn("### AP-PR-", prompt)
        self.assertNotIn("## ADR-", prompt)
        self.assertNotIn("terraform apply", prompt)
        self.assertIn(
            "[Provider-runtime handoff](starting_prompt.md)",
            prompt_index,
        )

    def test_incremental_delivery_sequence_keeps_later_slices_separate(self) -> None:
        index = (PROJECT_ROOT / "docs/README.md").read_text(encoding="utf-8")
        prompt = (PROJECT_ROOT / "prompts/starting_prompt.md").read_text(encoding="utf-8")
        normalized_index = " ".join(index.split())
        normalized_prompt = " ".join(prompt.split())

        for completed in (
            "Governance foundation — complete",
            "Requirements and decisions — complete",
        ):
            self.assertIn(completed, index)
        self.assertIn("System design and versioned contracts — complete", index)
        self.assertIn(
            "Deterministic fixtures — complete and Fixture-qualified",
            index,
        )
        self.assertIn(
            "Platform infrastructure planning — implemented and planning-validated",
            index,
        )
        for later_slice in (
            "Networked provider runtime — implementation in progress",
            "Terraform and workflow implementation — later",
            "Non-production qualification deployment — later",
            "Live qualification — later",
            "Finance Application Adoption — later and independent",
        ):
            self.assertIn(later_slice, index)
        self.assertIn("separate bounded branch and pull request", normalized_index)
        self.assertIn(
            "propose AP-M6, the smallest locally testable networked provider-runtime slice",
            normalized_prompt,
        )
        self.assertIn("Wait for owner approval before editing", normalized_prompt)
        self.assertIn("Do not write Terraform", normalized_prompt)
        self.assertIn("AP-M6 belongs on a new bounded branch", normalized_prompt)

    def test_fixture_design_selects_a_bounded_in_process_profile(self) -> None:
        design = (PROJECT_ROOT / "docs/03_system_design.md").read_text(
            encoding="utf-8"
        )
        threat_model = (PROJECT_ROOT / "docs/06_threat_model.md").read_text(
            encoding="utf-8"
        )
        normalized_threat_model = " ".join(threat_model.split())

        for boundary in (
            "handle(request) -> response",
            "It opens no listening socket",
            "fixture-in-process-v1",
            "fixture-public",
            "fixture-authenticated",
            "fixture-restricted",
            "adds no external registration endpoint",
            "or database",
            "No Fixture (`F`) evidence exists",
        ):
            self.assertIn(boundary, design)

        for threat_control in (
            "at most 32 headers",
            "65,536 UTF-8 bytes",
            "HMAC-SHA-256",
            "60 seconds",
            "256-entry fail-closed replay store",
            "There is no registration API or database",
            "produces no Fixture (`F`) evidence",
        ):
            self.assertIn(threat_control, normalized_threat_model)

        self.assertIn("Finance Assistant code", design)
        self.assertIn("network direct-bypass control", threat_model)

    def test_ap_m5_and_ap_m6_authorities_have_complete_unique_identifiers(self) -> None:
        plan = (PROJECT_ROOT / "docs/04_implementation_plan.md").read_text(
            encoding="utf-8"
        )
        evaluation = (PROJECT_ROOT / "docs/05_evaluation_strategy.md").read_text(
            encoding="utf-8"
        )

        work_packages = re.findall(r"^#### (AP-M5-W\d+) ·", plan, re.MULTILINE)
        planning_gates = re.findall(
            r"^### (AP-EVAL-M5-\d{2}) ·", evaluation, re.MULTILINE
        )
        runtime_packages = re.findall(r"^#### (AP-M6-W\d+) ·", plan, re.MULTILINE)
        runtime_gates = re.findall(
            r"^#### (AP-EVAL-M6-\d{2}) ·", evaluation, re.MULTILINE
        )
        live_gates = re.findall(
            r"^#### (AP-EVAL-M9-\d{2}) ·", evaluation, re.MULTILINE
        )
        future_boundaries = re.findall(
            r"^### (AP-EVAL-M[7-9]) ·", evaluation, re.MULTILINE
        )

        self.assertEqual(
            work_packages,
            [f"AP-M5-W{index}" for index in range(1, 10)],
        )
        self.assertEqual(
            planning_gates,
            [f"AP-EVAL-M5-{index:02d}" for index in range(1, 10)],
        )
        self.assertEqual(
            runtime_packages,
            [f"AP-M6-W{index}" for index in range(1, 12)],
        )
        self.assertEqual(
            runtime_gates,
            [f"AP-EVAL-M6-{index:02d}" for index in range(1, 11)],
        )
        self.assertEqual(
            live_gates,
            [f"AP-EVAL-M9-{index:02d}" for index in range(1, 11)],
        )
        self.assertEqual(
            future_boundaries,
            ["AP-EVAL-M7", "AP-EVAL-M8", "AP-EVAL-M9"],
        )
        for identifiers in (
            work_packages,
            planning_gates,
            runtime_packages,
            runtime_gates,
            live_gates,
        ):
            self.assertEqual(len(identifiers), len(set(identifiers)))

    def test_ap_m6_resolves_runtime_inputs_and_separates_later_delivery(self) -> None:
        plan = (PROJECT_ROOT / "docs/04_implementation_plan.md").read_text(
            encoding="utf-8"
        )
        evaluation = (PROJECT_ROOT / "docs/05_evaluation_strategy.md").read_text(
            encoding="utf-8"
        )
        normalized_plan = " ".join(plan.split())
        normalized_evaluation = " ".join(evaluation.split())

        for later_slice in (
            "AP-M6 · Networked provider runtime implementation",
            "AP-M7 · Terraform and workflow implementation",
            "AP-M8 · Non-production qualification deployment",
            "AP-M9 · Live qualification",
            "Later Application Adoption",
        ):
            self.assertIn(later_slice, plan)

        for planning_boundary in (
            "AP-M5 produces no Contract, Fixture, Live, or Adoption evidence",
            "Each item below requires a new owner-approved branch",
            "no later slice inherits mutation authority merely because AP-M5 is accepted",
            "Python 3.12-or-newer Starlette/Uvicorn runtime",
            "exact header, body, timeout, concurrency, stream, rate, and rejection behavior",
            "Owner acceptance of its exact values is required before AP-M6-W2",
            "Dedicated GitHub organization, repository, workflow subjects",
            "Globally unique state, configuration, log, and evidence bucket names",
            "These are unavailable inputs, not permission to query a provider",
        ):
            self.assertIn(planning_boundary, normalized_plan)

        for evaluation_boundary in (
            "internally consistent planning authority for the initial GCP qualification topology",
            "It proves no provider behavior and creates no new evidence class",
            "The default `make check` remains separate and credential-free",
            "A deployment result cannot qualify routing, identity, direct-origin denial",
            "leave Finance Assistant and every Application Adoption unchanged and unavailable",
        ):
            self.assertIn(evaluation_boundary, normalized_evaluation)

    def test_ap_m6_runtime_profile_is_exact_and_non_operational(self) -> None:
        design = (PROJECT_ROOT / "docs/03_system_design.md").read_text(
            encoding="utf-8"
        )
        evaluation = (PROJECT_ROOT / "docs/05_evaluation_strategy.md").read_text(
            encoding="utf-8"
        )
        threat_model = (PROJECT_ROOT / "docs/06_threat_model.md").read_text(
            encoding="utf-8"
        )
        normalized_design = " ".join(design.split())
        normalized_evaluation = " ".join(evaluation.split())
        normalized_threat_model = " ".join(threat_model.split())

        for selected_value in (
            "create_app(runtime_configuration, adapters) -> ASGI application",
            "Starlette as the ASGI framework",
            "Uvicorn as the server",
            "complete transitive resolution is committed in `uv.lock`",
            "at most 64 request headers",
            "at most 25 MiB per request body",
            "at most 100 MiB per streamed HTTP response",
            "300-second non-streaming request timeout",
            "55-minute absolute streaming lifetime",
            "at most 20 active requests and 10 streaming connections",
            "120 request starts per minute per trusted client key",
            "not a distributed rate-limit or WAF claim",
        ):
            self.assertIn(selected_value, normalized_design)

        for evaluation_boundary in (
            "must fail if a connection is attempted to any non-loopback address",
            "Dependency synchronization is a separate setup action",
            "AP-EVAL-M6 performs no authenticated provider",
            "production adapters are locally tested implementations",
        ):
            self.assertIn(evaluation_boundary, normalized_evaluation)

        self.assertIn(
            "AP-EVAL-M6 covers the exact network-runtime profile",
            normalized_threat_model,
        )
        self.assertIn(
            "remaining request and proxy limits remain unimplemented",
            normalized_threat_model,
        )

    def test_ap_m6_runtime_path_is_bounded_and_later_capabilities_remain_absent(
        self,
    ) -> None:
        layout = (PROJECT_ROOT / "docs/repository_layout.md").read_text(
            encoding="utf-8"
        )

        reserved_paths = (
            "registrations",
            "infrastructure",
            "artifacts",
            "docs/runbooks",
        )
        for relative_path in reserved_paths:
            self.assertFalse(
                (PROJECT_ROOT / relative_path).exists(),
                f"AP-M6 must not create later capability path: {relative_path}",
            )

        self.assertTrue((PROJECT_ROOT / "edge/__init__.py").is_file())
        self.assertTrue((PROJECT_ROOT / "edge/_generation.py").is_file())
        self.assertTrue((PROJECT_ROOT / "edge/_routing.py").is_file())
        self.assertTrue((PROJECT_ROOT / "edge/_runtime.py").is_file())

        for reserved_reference in (
            "`edge/`",
            "`registrations/`",
            "`infrastructure/terraform/bootstrap/`",
            "`infrastructure/terraform/platform/`",
            "`infrastructure/terraform/fixtures/<application-id>/`",
            "`artifacts/`",
            "`docs/runbooks/`",
            "not authorization to scaffold empty modules",
        ):
            self.assertIn(reserved_reference, layout)

        prohibited_suffixes = (".tf", ".tf.json", ".tfvars", ".tfstate", ".tfplan")
        prohibited_files = sorted(
            path.relative_to(PROJECT_ROOT).as_posix()
            for path in PROJECT_ROOT.rglob("*")
            if path.is_file()
            and (
                path.name.endswith(prohibited_suffixes)
                or path.name == ".terraform.lock.hcl"
            )
        )
        self.assertEqual(prohibited_files, [])
        self.assertFalse((PROJECT_ROOT / ".github/workflows").exists())

    def test_ap_m5_default_gate_has_no_live_operator_command(self) -> None:
        makefile = (PROJECT_ROOT / "Makefile").read_text(encoding="utf-8")
        evaluation = (PROJECT_ROOT / "docs/05_evaluation_strategy.md").read_text(
            encoding="utf-8"
        )
        normalized_makefile = " ".join(makefile.split())

        for prohibited_command in (
            "terraform",
            "gcloud",
            "gsutil",
            " dig ",
            " curl ",
            "docker",
            "kubectl",
            "openssl",
        ):
            self.assertNotIn(prohibited_command, f" {normalized_makefile} ")

        self.assertIn(
            "check: governance-check contract-check fixture-check",
            makefile,
        )
        self.assertIn("credential-free, deterministic, network-free", evaluation)

    def test_ap_m4_authorities_have_complete_unique_identifiers(self) -> None:
        plan = (PROJECT_ROOT / "docs/04_implementation_plan.md").read_text(
            encoding="utf-8"
        )
        evaluation = (PROJECT_ROOT / "docs/05_evaluation_strategy.md").read_text(
            encoding="utf-8"
        )

        work_packages = re.findall(r"^#### (AP-M4-W\d+) ·", plan, re.MULTILINE)
        evaluation_gates = re.findall(
            r"^### (AP-EVAL-M4-\d{2}) ·", evaluation, re.MULTILINE
        )

        self.assertEqual(
            work_packages, [f"AP-M4-W{index}" for index in range(1, 8)]
        )
        self.assertEqual(
            evaluation_gates,
            [f"AP-EVAL-M4-{index:02d}" for index in range(1, 10)],
        )
        self.assertEqual(len(work_packages), len(set(work_packages)))
        self.assertEqual(len(evaluation_gates), len(set(evaluation_gates)))

    def test_ap_m4_authority_is_fixture_only(self) -> None:
        plan = (PROJECT_ROOT / "docs/04_implementation_plan.md").read_text(
            encoding="utf-8"
        )
        evaluation = (PROJECT_ROOT / "docs/05_evaluation_strategy.md").read_text(
            encoding="utf-8"
        )
        normalized_plan = " ".join(plan.split())
        normalized_evaluation = " ".join(evaluation.split())

        for boundary in (
            "It does not turn the harness into a network server",
            "external registration endpoint, or database",
            "AP-M4 produces Fixture (`F`) evidence only",
            "Each work package is a separate small commit",
            "Finance Assistant requirements, code, infrastructure",
        ):
            self.assertIn(boundary, normalized_plan)

        for gate_boundary in (
            "AP-EVAL-M3 continues to own Contract (`C`) evidence",
            "Live (`L`) and Adoption (`A`) evidence remain unavailable",
            "no listening socket",
            "There is no registration API or database",
            "AP-EVAL-M4 passes only when all nine gates",
        ):
            self.assertIn(gate_boundary, normalized_evaluation)


if __name__ == "__main__":
    unittest.main()
