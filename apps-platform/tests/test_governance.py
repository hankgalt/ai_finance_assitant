"""Standalone App Platform governance-foundation checks."""

from __future__ import annotations

import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class GovernanceFoundationTest(unittest.TestCase):
    def test_project_shell_is_self_contained(self) -> None:
        expected_files = (
            ".gitignore",
            "Makefile",
            "README.md",
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


if __name__ == "__main__":
    unittest.main()
