"""Standalone App Platform governance-foundation checks."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class GovernanceFoundationTest(unittest.TestCase):
    def test_project_shell_is_self_contained(self) -> None:
        expected_files = (
            ".gitignore",
            "AGENTS.md",
            "GLOSSARY.md",
            "Makefile",
            "README.md",
            "docs/01_product_requirements.md",
            "docs/02_architecture_decision_records.md",
            "docs/README.md",
            "docs/repository_layout.md",
            "prompts/README.md",
            "tests/test_governance.py",
        )

        self.assertTrue(all((PROJECT_ROOT / path).is_file() for path in expected_files))

    def test_makefile_exposes_a_portable_non_mutating_check(self) -> None:
        makefile = (PROJECT_ROOT / "Makefile").read_text(encoding="utf-8")

        self.assertIn("check: governance-check", makefile)
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
        self.assertIn("docs/repository_layout.md", instructions)
        self.assertIn("make -C apps-platform check", instructions)

    def test_documentation_truthfully_limits_the_requirements_slice(self) -> None:
        index = (PROJECT_ROOT / "docs/README.md").read_text(encoding="utf-8")
        layout = (PROJECT_ROOT / "docs/repository_layout.md").read_text(encoding="utf-8")

        self.assertIn("requirements and shared-edge ownership decisions defined", index)
        self.assertIn("remaining decisions\npending", index)
        self.assertIn("does not claim", index)
        self.assertIn("Integration draft", index)
        self.assertIn("history-preserving subtree extraction", layout)
        self.assertIn("Do not create a nested `.git`", layout)

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

        self.assertEqual(observed, ["ADR-001", "ADR-002"])
        self.assertEqual(decisions.count("Status: Accepted"), 2)
        for identifier in (
            "AP-PR-001",
            "AP-PR-002",
            "AP-PR-003",
            "AP-PR-007",
            "AP-QR-001",
            "AP-QR-002",
            "AP-QR-003",
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


if __name__ == "__main__":
    unittest.main()
