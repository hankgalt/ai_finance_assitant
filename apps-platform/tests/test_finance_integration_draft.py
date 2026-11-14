"""Non-authoritative Finance Assistant integration-package checks."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = PROJECT_ROOT / "integrations/ai_finance_assistant"
FINANCE_BASELINE = "9dedac71ad358deb5ef1c02e2f0fea6e21773a71"


def _normalized(content: str) -> str:
    return " ".join(content.split())


class FinanceIntegrationDraftTest(unittest.TestCase):
    def test_package_is_complete_and_every_document_is_inactive(self) -> None:
        expected = {
            "README.md",
            "edge_migration_contract.draft.md",
            "proposed_changes/architecture_decisions_delta.md",
            "proposed_changes/evaluation_strategy_delta.md",
            "proposed_changes/implementation_plan_delta.md",
            "proposed_changes/repository_layout_delta.md",
            "proposed_changes/requirements_delta.md",
            "proposed_changes/system_design_delta.md",
        }
        observed = {
            str(path.relative_to(PACKAGE_ROOT)) for path in PACKAGE_ROOT.rglob("*.md")
        }

        self.assertEqual(observed, expected)
        for relative_path in expected:
            content = (PACKAGE_ROOT / relative_path).read_text(encoding="utf-8")
            self.assertIn("Integration Draft — inactive", content, relative_path)

    def test_package_names_its_source_and_cannot_activate_itself(self) -> None:
        package = (PACKAGE_ROOT / "README.md").read_text(encoding="utf-8")
        contract = (PACKAGE_ROOT / "edge_migration_contract.draft.md").read_text(
            encoding="utf-8"
        )
        normalized_package = _normalized(package)
        normalized_contract = _normalized(contract)

        self.assertIn(FINANCE_BASELINE, package)
        self.assertIn(FINANCE_BASELINE, contract)
        for boundary in (
            "not authority for either project",
            "does not modify Finance requirements",
            "Copying, merging, or extracting this package does not satisfy Application Adoption",
        ):
            self.assertIn(boundary, normalized_package)
        self.assertIn("not a machine contract", normalized_contract)
        self.assertIn("or authorization to mutate either deployment", normalized_contract)

    def test_package_is_discoverable_but_never_in_the_authority_chain(self) -> None:
        docs_index = (PROJECT_ROOT / "docs/README.md").read_text(encoding="utf-8")
        layout = (PROJECT_ROOT / "docs/repository_layout.md").read_text(encoding="utf-8")
        prompt = (PROJECT_ROOT / "prompts/starting_prompt.md").read_text(encoding="utf-8")
        normalized_prompt = _normalized(prompt)

        self.assertIn("Inactive integration inputs", docs_index)
        self.assertIn("integrations/ai_finance_assistant/README.md", prompt)
        self.assertIn("every linked draft in that package completely", normalized_prompt)
        self.assertIn("as non-authoritative inputs", normalized_prompt)
        self.assertIn("cannot define generic platform behavior", normalized_prompt)
        self.assertIn("Inactive application-adoption inputs", layout)

    def test_transfer_contract_preserves_exclusive_ownership_and_finance_boundaries(self) -> None:
        contract = (PACKAGE_ROOT / "edge_migration_contract.draft.md").read_text(
            encoding="utf-8"
        )
        normalized_contract = _normalized(contract)

        for boundary in (
            "Every live resource has exactly one active state owner",
            "may not broaden Finance admission",
            "Secret payloads never enter a repository",
            "Finance runtime/data teardown and platform edge teardown remain separate",
            "leaves Finance state before Platform State assumes it",
            "Finance state must not resume management concurrently",
            "Finance Principal-isolation and critical feature-parity results",
        ):
            self.assertIn(boundary, normalized_contract)

    def test_access_expansion_is_sequenced_after_edge_ownership_migration(self) -> None:
        contract = _normalized(
            (PACKAGE_ROOT / "edge_migration_contract.draft.md").read_text(encoding="utf-8")
        )
        requirements = _normalized(
            (PACKAGE_ROOT / "proposed_changes/requirements_delta.md").read_text(encoding="utf-8")
        )
        plan = _normalized(
            (PACKAGE_ROOT / "proposed_changes/implementation_plan_delta.md").read_text(
                encoding="utf-8"
            )
        )
        evaluation = _normalized(
            (PACKAGE_ROOT / "proposed_changes/evaluation_strategy_delta.md").read_text(
                encoding="utf-8"
            )
        )
        design = _normalized(
            (PACKAGE_ROOT / "proposed_changes/system_design_delta.md").read_text(encoding="utf-8")
        )

        for boundary in (
            "migration must preserve Finance Assistant's current Restricted, owner-only Admission Mode",
            "After the ownership migration is accepted and stable",
            "Authenticated admission for any successfully authenticated Google identity",
            "Massive Stocks Basic personal-use right does not permit market-data display to other users",
            "does not change the current owner-only deployment",
        ):
            self.assertIn(boundary, contract)
        self.assertIn("cutover may not bundle an application-access expansion", requirements)
        self.assertIn("Only after the edge-ownership migration is accepted", plan)
        self.assertIn("Finance remains Restricted and owner-only", evaluation)
        self.assertIn("without transferring Feature Entitlements to the platform", design)
        self.assertIn("without repeating the edge-ownership migration", design)
        self.assertNotIn("Finance Admission Mode at adoption time", contract)

    def test_proposed_deltas_cover_every_finance_authority_without_editing_it(self) -> None:
        deltas = {
            path.name: path.read_text(encoding="utf-8")
            for path in (PACKAGE_ROOT / "proposed_changes").glob("*.md")
        }

        expected_targets = {
            "requirements_delta.md": "docs/01_requirements_specification.md",
            "architecture_decisions_delta.md": "ADR-030",
            "system_design_delta.md": "docs/03_system_design.md",
            "implementation_plan_delta.md": "docs/04_implementation_plan.md",
            "evaluation_strategy_delta.md": "docs/05_evaluation_strategy.md",
            "repository_layout_delta.md": "Finance repository-layout",
        }
        for filename, target in expected_targets.items():
            self.assertIn(filename, deltas)
            if filename == "repository_layout_delta.md":
                self.assertIn("does not move, delete, or deprecate", deltas[filename])
            else:
                self.assertIn(target, deltas[filename])

    def test_package_contains_no_secret_like_payload_or_executable_mutation(self) -> None:
        content = "\n".join(
            path.read_text(encoding="utf-8") for path in PACKAGE_ROOT.rglob("*.md")
        )

        self.assertIsNone(re.search(r"gh[pousr]_[A-Za-z0-9_]{20,}", content))
        self.assertIsNone(re.search(r"AIza[0-9A-Za-z_-]{30,}", content))
        self.assertNotIn("terraform apply", content)
        self.assertNotIn("terraform destroy", content)
        self.assertNotIn("gcloud compute", content)
        self.assertNotIn("BEGIN PRIVATE KEY", content)


if __name__ == "__main__":
    unittest.main()
