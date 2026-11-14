"""Standalone App Platform authority-foundation checks."""

from __future__ import annotations

import re
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
            "prompts/README.md",
            "prompts/starting_prompt.md",
            "tests/test_contracts.py",
            "tests/test_governance.py",
        )

        self.assertTrue(all((PROJECT_ROOT / path).is_file() for path in expected_files))

    def test_makefile_exposes_a_portable_non_mutating_check(self) -> None:
        makefile = (PROJECT_ROOT / "Makefile").read_text(encoding="utf-8")

        self.assertIn("check: governance-check contract-check", makefile)
        self.assertIn("PYTHONDONTWRITEBYTECODE=1", makefile)
        self.assertIn("python3", makefile)
        self.assertNotIn("../", makefile)
        self.assertNotIn("terraform apply", makefile)
        self.assertNotIn("gcloud", makefile)

    def test_local_ignore_policy_excludes_sensitive_runtime_state(self) -> None:
        ignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")

        for pattern in (".env", "**/.terraform/", "*.tfstate", "*.tfplan", "*.tfvars"):
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

    def test_documentation_truthfully_records_contract_implementation(self) -> None:
        index = (PROJECT_ROOT / "docs/README.md").read_text(encoding="utf-8")
        layout = (PROJECT_ROOT / "docs/repository_layout.md").read_text(encoding="utf-8")
        overview = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        design = (PROJECT_ROOT / "docs/03_system_design.md").read_text(
            encoding="utf-8"
        )
        normalized_index = " ".join(index.split())
        normalized_overview = " ".join(overview.split())

        self.assertIn(
            "system design and versioned contracts implemented", normalized_index
        )
        self.assertIn("Contract (`C`) evidence", normalized_index)
        self.assertIn(
            "no Fixture (`F`), Live (`L`), or Adoption (`A`) evidence",
            normalized_index,
        )
        self.assertIn("AP-M3", overview)
        self.assertIn(
            "deterministic offline validation implemented", normalized_overview
        )
        self.assertIn("no platform runtime", normalized_overview)
        self.assertIn("Integration draft", index)
        self.assertIn("AP-M3 contract implementation recorded", layout)
        self.assertIn("`contracts/`", layout)
        self.assertIn("Version 1 schemas", layout)
        self.assertIn("Version 1 contract index", design)
        self.assertIn("revision-scoped Contract evidence", design)
        self.assertIn(
            "Runtime, Fixture, Live, and Adoption qualification remain later",
            design,
        )
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

        self.assertEqual(observed, ["ADR-001", "ADR-002", "ADR-003", "ADR-004"])
        self.assertEqual(decisions.count("Status: Accepted"), 4)
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

    def test_fixture_planning_prompt_loads_authority_without_copying_it(self) -> None:
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
        ):
            self.assertIn(authority, prompt)
        for boundary in (
            "Wait for owner approval before editing",
            "leave Finance Assistant requirements, code, infrastructure, Terraform state, DNS",
            "An Integration Draft is not Application Adoption",
            "credential-free, deterministic, and non-mutating",
            "updated `main` after the AP-M3 pull request has merged",
            "propose item 4 planning and evaluation authority",
        ):
            self.assertIn(boundary, normalized_prompt)
        self.assertNotIn("### AP-PR-", prompt)
        self.assertNotIn("## ADR-", prompt)
        self.assertNotIn("terraform apply", prompt)
        self.assertIn(
            "[Deterministic-fixture planning handoff](starting_prompt.md)",
            prompt_index,
        )

    def test_incremental_delivery_sequence_keeps_contracts_and_fixtures_separate(self) -> None:
        index = (PROJECT_ROOT / "docs/README.md").read_text(encoding="utf-8")
        prompt = (PROJECT_ROOT / "prompts/starting_prompt.md").read_text(encoding="utf-8")
        normalized_index = " ".join(index.split())
        normalized_prompt = " ".join(prompt.split())

        for completed in (
            "Governance foundation — complete",
            "Requirements and decisions — complete",
        ):
            self.assertIn(completed, index)
        self.assertIn("System design and versioned contracts — implemented", index)
        self.assertIn("Deterministic fixture planning — next after item 3 merges", index)
        self.assertIn("feat/apps-platform-system-design-contracts", index)
        self.assertIn("feat/apps-platform-fixtures", index)
        self.assertIn("separate bounded branch and pull request", normalized_index)
        self.assertIn(
            "obtain owner approval for the fixture implementation plan",
            normalized_index,
        )
        self.assertIn("propose item 4 planning and evaluation authority", normalized_prompt)
        self.assertIn("Do not implement a Fixture Application", normalized_prompt)
        self.assertIn("Item 4 belongs on a new bounded branch", normalized_prompt)

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
            "It does not authorize a listening service",
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
