from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, cast

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / "backend/data/evaluation/m9_release_manifest.v1.json"
MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def _manifest() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(MANIFEST_PATH.read_text(encoding="utf-8")))


def test_m9_release_manifest_covers_required_ids_and_existing_evidence() -> None:
    manifest = _manifest()
    assert manifest["schema_version"] == "1"
    assert {entry["id"] for entry in manifest["product_requirements"]} == {
        f"PR-{number:03d}" for number in range(1, 16)
    }
    assert {entry["id"] for entry in manifest["coursework_criteria"]} == {
        f"CA-{number:02d}" for number in range(1, 14)
    }

    paths: set[str] = set(manifest["release_documents"])
    paths.update(manifest["release_evidence"])
    paths.update(manifest["sample_data"])
    paths.add(manifest["qualification_report"])
    for group in ("product_requirements", "coursework_criteria"):
        for entry in manifest[group]:
            paths.update(entry["evidence"])
    missing = sorted(path for path in paths if not (REPO_ROOT / path).is_file())
    assert missing == []

    qualification = json.loads(
        (REPO_ROOT / manifest["qualification_report"]).read_text(encoding="utf-8")
    )
    assert qualification["schema_version"] == "1"
    assert qualification["dataset_version"] == "m8-release-qualification-v1"
    if os.getenv("AIFA_M9_REQUIRE_QUALIFICATION_PASS") == "true":
        assert qualification["release_gate_passed"] is True
        assert qualification["critical_failure_count"] == 0
        assert qualification["critical_incomplete_count"] == 0


def test_release_document_links_resolve_locally() -> None:
    broken: list[str] = []
    for relative_path in _manifest()["release_documents"]:
        document = REPO_ROOT / relative_path
        for target in MARKDOWN_LINK.findall(document.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://", "#")):
                continue
            resolved = (document.parent / target.split("#", maxsplit=1)[0]).resolve()
            if not resolved.exists():
                broken.append(f"{relative_path} -> {target}")
    assert broken == []


def test_packaged_samples_match_their_checksums() -> None:
    sample_manifest_path = REPO_ROOT / "examples/portfolios/manifest.v1.json"
    sample_manifest = json.loads(sample_manifest_path.read_text(encoding="utf-8"))
    for dataset in sample_manifest["datasets"]:
        content = (sample_manifest_path.parent / dataset["path"]).read_bytes()
        assert hashlib.sha256(content).hexdigest() == dataset["sha256"]


def test_frontend_measured_line_coverage_meets_fallback_target() -> None:
    coverage_path = REPO_ROOT / "backend/artifacts/m9/frontend-coverage/coverage-summary.json"
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
    assert coverage["total"]["lines"]["pct"] >= 80


def test_mcp_release_surface_is_explicitly_read_only() -> None:
    mcp = _manifest()["mcp"]
    assert mcp == {
        "adapter_version": "read-only-mcp-v1",
        "transport": "stdio",
        "tools": [
            "search_education",
            "get_market_quote",
            "analyze_portfolio",
            "project_goal",
        ],
        "mutation_tools": [],
    }
