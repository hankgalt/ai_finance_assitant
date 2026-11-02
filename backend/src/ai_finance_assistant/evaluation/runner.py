"""Run fixed release-qualification commands and reconcile them with versioned evidence."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic

from ai_finance_assistant.core.redaction import redact_text
from ai_finance_assistant.evaluation.models import (
    CheckResult,
    CheckStatus,
    DimensionResult,
    DimensionStatus,
    EvaluationDimension,
    EvaluationManifest,
    QualificationReport,
    ReviewStatus,
)


@dataclass(frozen=True)
class CheckSpec:
    check_id: str
    command: tuple[str, ...]
    cwd: str
    profiles: frozenset[str] = field(default_factory=lambda: frozenset({"core", "full"}))
    environment: tuple[tuple[str, str], ...] = ()
    timeout_seconds: int = 900


CHECK_SPECS = (
    CheckSpec("backend-format", (".venv/bin/ruff", "format", "--check", "."), "backend"),
    CheckSpec("backend-lint", (".venv/bin/ruff", "check", "."), "backend"),
    CheckSpec("backend-types", (".venv/bin/mypy",), "backend"),
    CheckSpec(
        "backend-tests",
        (
            ".venv/bin/pytest",
            "-q",
            "--cov=ai_finance_assistant",
            "--cov-report=json:artifacts/quality/backend-coverage.json",
            "--junitxml=artifacts/quality/backend-junit.xml",
        ),
        "backend",
    ),
    CheckSpec("frontend-format", ("pnpm", "format:check"), "frontend"),
    CheckSpec("frontend-lint", ("pnpm", "lint"), "frontend"),
    CheckSpec("frontend-types", ("pnpm", "typecheck"), "frontend"),
    CheckSpec("frontend-tests", ("pnpm", "test"), "frontend"),
    CheckSpec("frontend-build", ("pnpm", "build"), "frontend"),
    CheckSpec(
        "browser-tests",
        ("pnpm", "test:e2e"),
        "frontend",
        profiles=frozenset({"full"}),
        environment=(("AIFA_PLAYWRIGHT_CAPTURE_EVIDENCE", "false"),),
        timeout_seconds=1_200,
    ),
    CheckSpec(
        "qdrant-integration",
        (".venv/bin/pytest", "-q", "tests/test_qdrant_integration.py"),
        "backend",
        profiles=frozenset({"full"}),
        environment=(("AIFA_TEST_QDRANT_URL", "http://127.0.0.1:6333"),),
    ),
    CheckSpec(
        "redis-integration",
        (".venv/bin/pytest", "-q", "-m", "redis", "tests/test_response_cache_redis.py"),
        "backend",
        profiles=frozenset({"full"}),
        environment=(("AIFA_TEST_REDIS_URL", "redis://127.0.0.1:6379/0"),),
    ),
)

_SENSITIVE_ENV_PREFIXES = (
    "AIFA_",
    "OPENAI_",
    "LANGCHAIN_",
    "LANGSMITH_",
)


def load_manifest(path: Path) -> EvaluationManifest:
    return EvaluationManifest.model_validate_json(path.read_text(encoding="utf-8"))


def safe_test_environment(backend_root: Path) -> dict[str, str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(_SENSITIVE_ENV_PREFIXES)
    }
    environment["AIFA_ENV_FILE"] = str(backend_root / ".test.env")
    return environment


def run_check(spec: CheckSpec, *, repo_root: Path, environment: dict[str, str]) -> CheckResult:
    started = monotonic()
    try:
        process = subprocess.run(
            spec.command,
            cwd=repo_root / spec.cwd,
            env={**environment, **dict(spec.environment)},
            capture_output=True,
            check=False,
            text=True,
            timeout=spec.timeout_seconds,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return CheckResult(
            check_id=spec.check_id,
            status=CheckStatus.FAILED,
            command=spec.command,
            duration_seconds=round(monotonic() - started, 3),
            exit_code=None,
            output_tail=redact_text(f"qualification check unavailable: {type(exc).__name__}"),
        )
    combined = redact_text(f"{process.stdout}\n{process.stderr}".strip())
    return CheckResult(
        check_id=spec.check_id,
        status=CheckStatus.PASSED if process.returncode == 0 else CheckStatus.FAILED,
        command=spec.command,
        duration_seconds=round(monotonic() - started, 3),
        exit_code=process.returncode,
        output_tail=combined[-8_000:],
    )


def reconcile_dimensions(
    manifest: EvaluationManifest,
    *,
    repo_root: Path,
    checks: tuple[CheckResult, ...],
) -> tuple[DimensionResult, ...]:
    check_by_id = {check.check_id: check for check in checks}
    results: list[DimensionResult] = []
    for dimension in EvaluationDimension:
        cases = tuple(case for case in manifest.cases if case.dimension == dimension)
        required_checks = {check_id for case in cases for check_id in case.check_ids}
        failed = tuple(
            sorted(
                check_id
                for check_id in required_checks
                if check_by_id.get(check_id) is not None
                and check_by_id[check_id].status == CheckStatus.FAILED
            )
        )
        not_run = tuple(
            sorted(check_id for check_id in required_checks if check_id not in check_by_id)
        )
        missing_evidence = tuple(
            sorted(
                path
                for case in cases
                for path in case.evidence_paths
                if not (repo_root / path).is_file()
            )
        )
        pending_review = tuple(
            case.case_id for case in cases if case.review_status == ReviewStatus.PENDING
        )
        if failed:
            status = DimensionStatus.FAILED
        elif not_run or missing_evidence:
            status = DimensionStatus.INCOMPLETE
        elif pending_review:
            status = DimensionStatus.REVIEW_REQUIRED
        else:
            status = DimensionStatus.PASSED
        results.append(
            DimensionResult(
                dimension=dimension,
                status=status,
                critical=any(case.critical for case in cases),
                case_ids=tuple(case.case_id for case in cases),
                missing_evidence_paths=missing_evidence,
                failed_check_ids=failed,
                not_run_check_ids=not_run,
                pending_review_case_ids=pending_review,
            )
        )
    return tuple(results)


def build_report(
    manifest: EvaluationManifest,
    *,
    profile: str,
    repo_root: Path,
    checks: tuple[CheckResult, ...],
) -> QualificationReport:
    dimensions = reconcile_dimensions(manifest, repo_root=repo_root, checks=checks)
    critical_failures = sum(
        item.critical and item.status == DimensionStatus.FAILED for item in dimensions
    )
    critical_incomplete = sum(
        item.critical
        and item.status in {DimensionStatus.INCOMPLETE, DimensionStatus.REVIEW_REQUIRED}
        for item in dimensions
    )
    return QualificationReport(
        dataset_version=manifest.dataset_version,
        generated_at=datetime.now(UTC),
        profile=profile,
        release_gate_passed=critical_failures == 0 and critical_incomplete == 0,
        critical_failure_count=critical_failures,
        critical_incomplete_count=critical_incomplete,
        checks=checks,
        dimensions=dimensions,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the fixed release-qualification suite")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", choices=("core", "full"), default="core")
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    manifest = load_manifest(args.manifest.resolve())
    environment = safe_test_environment(repo_root / "backend")
    selected = tuple(spec for spec in CHECK_SPECS if args.profile in spec.profiles)
    checks = tuple(
        run_check(spec, repo_root=repo_root, environment=environment) for spec in selected
    )
    report = build_report(
        manifest,
        profile=args.profile,
        repo_root=repo_root,
        checks=checks,
    )
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))
    raise SystemExit(0 if report.release_gate_passed else 1)


if __name__ == "__main__":
    main()
