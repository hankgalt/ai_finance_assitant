"""Synthetic managed-state qualification for the deployed PostgreSQL adapter."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    CheckpointMetadata,
    empty_checkpoint,
)
from pydantic import AwareDatetime, BaseModel, ConfigDict

from ai_finance_assistant.agents.context import GoalAgentContext
from ai_finance_assistant.contracts.common import Identifier, ShortText
from ai_finance_assistant.contracts.events import EventStatus, EventType, RunEvent
from ai_finance_assistant.contracts.portfolio import (
    SecurityIdentifier,
    SecurityIdentifierType,
)
from ai_finance_assistant.finance.models import (
    GoalProjectionRequest,
    ImportedAccount,
    ImportedHolding,
    ImportedPortfolio,
    ImportSourceKind,
    PortfolioSnapshot,
)
from ai_finance_assistant.identity.models import (
    PrincipalRole,
    VerifiedIdentity,
    derive_principal_id,
)
from ai_finance_assistant.identity.repositories import PrincipalRepository
from ai_finance_assistant.persistence.checkpoints import (
    Closeable,
    create_postgres_checkpointer,
    verify_postgres_checkpoint_schema,
)
from ai_finance_assistant.persistence.config import (
    PersistenceConfiguration,
    PersistenceOperatorSettings,
)
from ai_finance_assistant.persistence.postgres import PostgresDatabase
from ai_finance_assistant.persistence.repositories import (
    AgentContextRepository,
    ApplicationRepository,
    RunEventRepository,
)

_QUALIFICATION_ID = re.compile(r"^[a-z0-9][a-z0-9-]{5,48}$")


class QualificationError(RuntimeError):
    """A managed-state qualification invariant did not hold."""


class QualificationCheck(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    check_id: Identifier
    status: Literal["passed"] = "passed"
    detail: ShortText


class RetentionProbe(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    session_id: Identifier
    expected_outcome: Literal["removed_by_scheduled_retention"] = "removed_by_scheduled_retention"


class ManagedStateQualificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1"] = "1"
    qualification_id: Identifier
    phase: Literal["prepare", "verify_recovery", "verify_retention"]
    status: Literal["passed"] = "passed"
    backend: Literal["postgres"] = "postgres"
    synthetic_data: Literal[True] = True
    started_at: AwareDatetime
    finished_at: AwareDatetime
    checks: tuple[QualificationCheck, ...]
    retention_probe: RetentionProbe
    cleanup_performed: bool


@dataclass(frozen=True)
class _QualificationIds:
    qualification_id: str
    owner_principal_id: str
    viewer_principal_id: str
    owner_session_id: str
    viewer_session_id: str
    expired_session_id: str
    owner_execution_id: str
    viewer_execution_id: str
    portfolio_id: str
    snapshot_id: str
    goal_context_id: str


def prepare_qualification(
    settings: PersistenceConfiguration,
    *,
    qualification_id: str,
) -> ManagedStateQualificationResult:
    """Write synthetic two-Principal state and prove it survives an adapter restart."""

    started_at = datetime.now(UTC)
    identifiers = _identifiers(qualification_id)
    database = _database(settings)
    try:
        _require_ready_schema(database)
        _delete_checkpoint_threads(settings, identifiers)
        _cleanup(database, identifiers)
        repository = _repository(database, settings)
        principal_repository = PrincipalRepository(database)
        event_repository = RunEventRepository(database)
        context_repository = AgentContextRepository(database)

        def write_principal(role: PrincipalRole) -> str:
            is_owner = role == PrincipalRole.OWNER
            identity = _identity(qualification_id, role)
            principal = principal_repository.ensure(identity, role=role, now=started_at)
            session_id = identifiers.owner_session_id if is_owner else identifiers.viewer_session_id
            execution_id = (
                identifiers.owner_execution_id if is_owner else identifiers.viewer_execution_id
            )
            repository.create_session(
                principal.principal_id,
                session_id,
                label=f"Synthetic {role.value} qualification",
                now=started_at,
            )
            portfolio = _portfolio(identifiers.portfolio_id, started_at)
            repository.save_portfolio(
                portfolio,
                principal_id=principal.principal_id,
                session_id=session_id,
                idempotency_key="qualification-portfolio",
                request_hash="synthetic-portfolio-v1",
                now=started_at,
            )
            repository.save_snapshot(
                principal.principal_id,
                _snapshot(
                    identifiers.snapshot_id,
                    identifiers.portfolio_id,
                    started_at,
                ),
                session_id=session_id,
            )
            context_repository.put(
                session_id,
                _goal_context(identifiers.goal_context_id),
            )
            repository.create_run(
                principal_id=principal.principal_id,
                execution_id=execution_id,
                session_id=session_id,
                workflow_id=settings.workflow_id,
                workflow_version="qualification-v1",
                request_message="Synthetic managed-state qualification",
                idempotency_key="qualification-run",
                request_hash="synthetic-run-v1",
                now=started_at,
            )
            event_repository.append(
                _run_event(
                    session_id=session_id,
                    execution_id=execution_id,
                    workflow_id=settings.workflow_id,
                    started_at=started_at,
                )
            )
            return principal.principal_id

        with ThreadPoolExecutor(max_workers=2) as executor:
            principal_ids = tuple(
                executor.map(write_principal, (PrincipalRole.OWNER, PrincipalRole.VIEWER))
            )
        if set(principal_ids) != {
            identifiers.owner_principal_id,
            identifiers.viewer_principal_id,
        }:
            raise QualificationError("Synthetic identities did not map to expected Principals.")

        expired_at = started_at - timedelta(days=settings.session_retention_days + 1)
        repository.create_session(
            identifiers.owner_principal_id,
            identifiers.expired_session_id,
            label="Synthetic retention probe",
            now=expired_at,
        )
        _require_cross_principal_denial(repository, event_repository, identifiers)
        _write_checkpoint_state(settings, identifiers)
    finally:
        database.close()

    restarted = _database(settings)
    try:
        _require_ready_schema(restarted)
        _require_restart_state(restarted, settings, identifiers)
    finally:
        restarted.close()

    return ManagedStateQualificationResult(
        qualification_id=qualification_id,
        phase="prepare",
        started_at=started_at,
        finished_at=datetime.now(UTC),
        checks=(
            QualificationCheck(
                check_id="schema_ready",
                detail="Application and checkpoint schemas match the expected version.",
            ),
            QualificationCheck(
                check_id="concurrent_principal_writes",
                detail="Two synthetic Principals wrote isolated state concurrently.",
            ),
            QualificationCheck(
                check_id="cross_principal_denial",
                detail="Cross-Principal Session, Run, event, Portfolio, and Snapshot reads failed.",
            ),
            QualificationCheck(
                check_id="principal_owned_goal_contexts",
                detail="Both synthetic Sessions retain their isolated Goal contexts.",
            ),
            QualificationCheck(
                check_id="checkpoint_state",
                detail=(
                    "Synthetic checkpoint threads exist for active and retention-probe Sessions."
                ),
            ),
            QualificationCheck(
                check_id="restart_durability",
                detail="Synthetic authoritative state survived an adapter close and reopen.",
            ),
            QualificationCheck(
                check_id="retention_probe_prepared",
                detail="One expired synthetic Session is ready for the retention identity.",
            ),
        ),
        retention_probe=RetentionProbe(session_id=identifiers.expired_session_id),
        cleanup_performed=False,
    )


def verify_retention_and_cleanup(
    settings: PersistenceConfiguration,
    *,
    qualification_id: str,
) -> ManagedStateQualificationResult:
    """Verify the separate retention run and remove all remaining synthetic state."""

    started_at = datetime.now(UTC)
    identifiers = _identifiers(qualification_id)
    database = _database(settings)
    try:
        _require_ready_schema(database)
        repository = _repository(database, settings)
        if (
            repository.get_session(
                identifiers.owner_principal_id,
                identifiers.expired_session_id,
            )
            is not None
        ):
            raise QualificationError(
                "The expired synthetic Session remains; run the retention job before verification."
            )
        if (
            repository.get_session(
                identifiers.owner_principal_id,
                identifiers.owner_session_id,
            )
            is None
            or repository.get_session(
                identifiers.viewer_principal_id,
                identifiers.viewer_session_id,
            )
            is None
        ):
            raise QualificationError("Retention removed unexpired synthetic state.")
        _require_retention_checkpoint_removed(settings, identifiers)
        _delete_checkpoint_threads(settings, identifiers)
        _cleanup(database, identifiers)
        principals = PrincipalRepository(database)
        if (
            principals.get(identifiers.owner_principal_id) is not None
            or principals.get(identifiers.viewer_principal_id) is not None
        ):
            raise QualificationError("Synthetic Principal cleanup was incomplete.")
    finally:
        database.close()

    return ManagedStateQualificationResult(
        qualification_id=qualification_id,
        phase="verify_retention",
        started_at=started_at,
        finished_at=datetime.now(UTC),
        checks=(
            QualificationCheck(
                check_id="retention_probe_removed",
                detail="The expired synthetic Session was removed by scheduled retention.",
            ),
            QualificationCheck(
                check_id="unexpired_state_preserved",
                detail="Retention preserved both unexpired synthetic Principal resources.",
            ),
            QualificationCheck(
                check_id="synthetic_checkpoints_cleaned",
                detail=(
                    "Retention removed the expired thread and final cleanup removed active threads."
                ),
            ),
            QualificationCheck(
                check_id="synthetic_state_cleaned",
                detail="All remaining qualification-owned application state was removed.",
            ),
        ),
        retention_probe=RetentionProbe(session_id=identifiers.expired_session_id),
        cleanup_performed=True,
    )


def verify_recovered_state(
    settings: PersistenceConfiguration,
    *,
    qualification_id: str,
) -> ManagedStateQualificationResult:
    """Prove that a restored target contains the pre-recovery synthetic state."""

    started_at = datetime.now(UTC)
    identifiers = _identifiers(qualification_id)
    database = _database(settings)
    try:
        _require_ready_schema(database)
        _require_restart_state(database, settings, identifiers)
        repository = _repository(database, settings)
        if (
            repository.get_session(
                identifiers.owner_principal_id,
                identifiers.expired_session_id,
            )
            is None
        ):
            raise QualificationError("The restored target is missing the retention probe.")
    finally:
        database.close()

    return ManagedStateQualificationResult(
        qualification_id=qualification_id,
        phase="verify_recovery",
        started_at=started_at,
        finished_at=datetime.now(UTC),
        checks=(
            QualificationCheck(
                check_id="recovered_schema_ready",
                detail="Restored application and checkpoint schemas match the expected version.",
            ),
            QualificationCheck(
                check_id="recovered_principal_state",
                detail="Both synthetic Principal resource sets are readable after recovery.",
            ),
            QualificationCheck(
                check_id="recovered_goal_contexts",
                detail="Both synthetic Goal contexts are readable after recovery.",
            ),
            QualificationCheck(
                check_id="recovered_checkpoints",
                detail="Active and retention-probe checkpoint threads are readable after recovery.",
            ),
            QualificationCheck(
                check_id="recovered_retention_probe",
                detail="The pre-recovery synthetic retention probe is present.",
            ),
        ),
        retention_probe=RetentionProbe(session_id=identifiers.expired_session_id),
        cleanup_performed=False,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "phase",
        choices=("prepare", "verify-recovery", "verify-retention"),
    )
    parser.add_argument("--qualification-id", required=True)
    args = parser.parse_args(argv)
    settings = PersistenceOperatorSettings()
    try:
        if args.phase == "prepare":
            result = prepare_qualification(settings, qualification_id=args.qualification_id)
        elif args.phase == "verify-recovery":
            result = verify_recovered_state(
                settings,
                qualification_id=args.qualification_id,
            )
        else:
            result = verify_retention_and_cleanup(
                settings,
                qualification_id=args.qualification_id,
            )
    except BaseException as exc:
        print(
            json.dumps(
                {
                    "schema_version": "1",
                    "status": "failed",
                    "error": {
                        "code": "MANAGED_STATE_QUALIFICATION_FAILED",
                        "category": type(exc).__name__,
                        "message": "Managed-state qualification failed.",
                    },
                },
                sort_keys=True,
            )
        )
        return 1
    print(result.model_dump_json(exclude_none=True))
    return 0


def _database(settings: PersistenceConfiguration) -> PostgresDatabase:
    if settings.storage_backend != "postgres" or settings.postgres_dsn is None:
        raise QualificationError("Managed-state qualification requires PostgreSQL.")
    return PostgresDatabase(
        settings.postgres_dsn.get_secret_value(),
        expected_version=settings.storage_expected_schema_version,
        pool_min_size=settings.postgres_pool_min_size,
        pool_max_size=settings.postgres_pool_max_size,
        timeout_seconds=settings.postgres_connect_timeout_seconds,
    )


def _repository(
    database: PostgresDatabase,
    settings: PersistenceConfiguration,
) -> ApplicationRepository:
    return ApplicationRepository(
        database,
        session_retention_days=settings.session_retention_days,
        portfolio_retention_days=settings.portfolio_retention_days,
        run_event_retention_days=settings.run_event_retention_days,
    )


def _require_ready_schema(database: PostgresDatabase) -> None:
    if database.schema_version() != database.expected_version:
        raise QualificationError("Application schema does not match the expected version.")
    verify_postgres_checkpoint_schema(database)


def _checkpointer(
    settings: PersistenceConfiguration,
) -> tuple[BaseCheckpointSaver[str], Closeable]:
    if settings.postgres_dsn is None:
        raise QualificationError("Managed-state qualification requires PostgreSQL.")
    return create_postgres_checkpointer(
        settings.postgres_dsn.get_secret_value(),
        pool_min_size=settings.postgres_pool_min_size,
        pool_max_size=settings.postgres_pool_max_size,
        timeout_seconds=settings.postgres_connect_timeout_seconds,
        setup=False,
    )


def _checkpoint_configs(
    settings: PersistenceConfiguration,
    identifiers: _QualificationIds,
) -> tuple[RunnableConfig, ...]:
    return tuple(
        RunnableConfig(
            configurable={
                "thread_id": f"{principal_id}:{session_id}:{settings.workflow_id}",
                "checkpoint_ns": "",
            }
        )
        for principal_id, session_id in (
            (identifiers.owner_principal_id, identifiers.owner_session_id),
            (identifiers.viewer_principal_id, identifiers.viewer_session_id),
            (identifiers.owner_principal_id, identifiers.expired_session_id),
        )
    )


def _write_checkpoint_state(
    settings: PersistenceConfiguration,
    identifiers: _QualificationIds,
) -> None:
    checkpointer, resource = _checkpointer(settings)
    metadata = CheckpointMetadata(source="input", step=0, parents={})
    try:
        for config in _checkpoint_configs(settings, identifiers):
            checkpointer.put(config, empty_checkpoint(), metadata, {})
    finally:
        resource.close()


def _delete_checkpoint_threads(
    settings: PersistenceConfiguration,
    identifiers: _QualificationIds,
) -> None:
    checkpointer, resource = _checkpointer(settings)
    try:
        configs = _checkpoint_configs(settings, identifiers)
        for config in configs:
            checkpointer.delete_thread(str(config["configurable"]["thread_id"]))
        if any(checkpointer.get_tuple(config) is not None for config in configs):
            raise QualificationError("Synthetic checkpoint cleanup was incomplete.")
    finally:
        resource.close()


def _require_retention_checkpoint_removed(
    settings: PersistenceConfiguration,
    identifiers: _QualificationIds,
) -> None:
    checkpointer, resource = _checkpointer(settings)
    try:
        owner, viewer, expired = _checkpoint_configs(settings, identifiers)
        if checkpointer.get_tuple(expired) is not None:
            raise QualificationError("Retention did not remove the expired checkpoint thread.")
        if checkpointer.get_tuple(owner) is None or checkpointer.get_tuple(viewer) is None:
            raise QualificationError("Retention removed an active checkpoint thread.")
    finally:
        resource.close()


def _require_checkpoint_state(
    settings: PersistenceConfiguration,
    identifiers: _QualificationIds,
) -> None:
    checkpointer, resource = _checkpointer(settings)
    try:
        if any(
            checkpointer.get_tuple(config) is None
            for config in _checkpoint_configs(settings, identifiers)
        ):
            raise QualificationError("Synthetic checkpoint state did not survive restart.")
    finally:
        resource.close()


def _identity(qualification_id: str, role: PrincipalRole) -> VerifiedIdentity:
    return VerifiedIdentity(
        issuer=f"urn:ai-finance-assistant:qualification:{qualification_id}",
        subject=role.value,
        email=f"{role.value}.{qualification_id}@example.invalid",
    )


def _identifiers(qualification_id: str) -> _QualificationIds:
    if _QUALIFICATION_ID.fullmatch(qualification_id) is None:
        raise QualificationError(
            "qualification_id must be 6-49 lowercase alphanumeric or hyphen characters."
        )
    owner = _identity(qualification_id, PrincipalRole.OWNER)
    viewer = _identity(qualification_id, PrincipalRole.VIEWER)
    prefix = f"qualification-{qualification_id}"
    return _QualificationIds(
        qualification_id=qualification_id,
        owner_principal_id=derive_principal_id(owner.issuer, owner.subject),
        viewer_principal_id=derive_principal_id(viewer.issuer, viewer.subject),
        owner_session_id=f"{prefix}-owner-session",
        viewer_session_id=f"{prefix}-viewer-session",
        expired_session_id=f"{prefix}-expired-session",
        owner_execution_id=f"{prefix}-owner-run",
        viewer_execution_id=f"{prefix}-viewer-run",
        portfolio_id=f"{prefix}-portfolio",
        snapshot_id=f"{prefix}-snapshot",
        goal_context_id=f"{prefix}-goal",
    )


def _portfolio(portfolio_id: str, observed: datetime) -> ImportedPortfolio:
    account_id = f"{portfolio_id}-account"
    return ImportedPortfolio(
        portfolio_id=portfolio_id,
        label="Synthetic managed-state qualification",
        base_currency="USD",
        imported_at=observed,
        source_kind=ImportSourceKind.MANUAL,
        source_file_hash=hashlib.sha256(portfolio_id.encode()).hexdigest(),
        accounts=(
            ImportedAccount(
                account_id=account_id,
                portfolio_id=portfolio_id,
                account_type="synthetic",
                holdings=(
                    ImportedHolding(
                        holding_id=f"{portfolio_id}-holding",
                        account_id=account_id,
                        source_row=1,
                        security=SecurityIdentifier(
                            identifier_type=SecurityIdentifierType.USER_DEFINED,
                            value="SYNTHETIC",
                        ),
                        quantity=Decimal("1"),
                        currency="USD",
                        user_price=Decimal("10"),
                        user_price_as_of=observed,
                        user_price_provenance="synthetic qualification fixture",
                    ),
                ),
            ),
        ),
    )


def _snapshot(
    snapshot_id: str,
    portfolio_id: str,
    observed: datetime,
) -> PortfolioSnapshot:
    return PortfolioSnapshot(
        snapshot_id=snapshot_id,
        portfolio_id=portfolio_id,
        calculated_at=observed,
        quote_set_id=f"{portfolio_id}-quotes",
        security_reference_ids=(),
        base_currency="USD",
        base_currency_total=None,
        totals_by_currency=(),
        holding_valuations=(),
        concentrations=(),
        expense_metrics=(),
        diversification=(),
        unpriced_holding_ids=(f"{portfolio_id}-holding",),
        warnings=(),
    )


def _goal_context(context_id: str) -> GoalAgentContext:
    return GoalAgentContext(
        context_id=context_id,
        projection=GoalProjectionRequest.model_validate(
            {
                "projection_id": context_id,
                "currency": "USD",
                "starting_amount": "1000",
                "goal_amount": "2000",
                "contribution_amount": "100",
                "contribution_frequency": "monthly",
                "contribution_timing": "end",
                "horizon_months": 12,
                "risk_tolerance": "not_declared",
                "scenarios": [
                    {
                        "label": "synthetic",
                        "annual_return_rate": "0.05",
                        "annual_inflation_rate": "0.02",
                        "annual_fee_rate": "0",
                    }
                ],
            }
        ),
    )


def _run_event(
    *,
    session_id: str,
    execution_id: str,
    workflow_id: str,
    started_at: datetime,
) -> RunEvent:
    return RunEvent(
        event_id=f"{execution_id}-event-1",
        execution_id=execution_id,
        trace_id=None,
        trace_unavailable_reason="Synthetic qualification does not emit a trace.",
        session_id=session_id,
        workflow_id=workflow_id,
        workflow_version="qualification-v1",
        sequence=1,
        node_id="managed-state-qualification",
        event_type=EventType.RUN_STARTED,
        status=EventStatus.RUNNING,
        started_at=started_at,
        duration_ms=None,
        duration_unavailable_reason="Synthetic qualification event is still running.",
        summary="Synthetic managed-state qualification Run started.",
        safe_metadata={"synthetic": True},
    )


def _require_cross_principal_denial(
    repository: ApplicationRepository,
    events: RunEventRepository,
    identifiers: _QualificationIds,
) -> None:
    if (
        repository.get_session(
            identifiers.viewer_principal_id,
            identifiers.owner_session_id,
        )
        is not None
    ):
        raise QualificationError("A viewer resolved the owner Session.")
    if (
        repository.get_run(
            identifiers.viewer_principal_id,
            identifiers.owner_execution_id,
            session_id=identifiers.owner_session_id,
        )
        is not None
    ):
        raise QualificationError("A viewer resolved the owner Run.")
    if events.list_for_run(
        identifiers.viewer_principal_id,
        identifiers.owner_execution_id,
        session_id=identifiers.owner_session_id,
    ):
        raise QualificationError("A viewer resolved owner RunEvents.")
    try:
        repository.get_portfolio(
            identifiers.viewer_principal_id,
            identifiers.portfolio_id,
            session_id=identifiers.owner_session_id,
        )
    except PermissionError:
        pass
    else:
        raise QualificationError("A viewer resolved the owner Portfolio.")
    try:
        repository.get_snapshot(
            identifiers.viewer_principal_id,
            identifiers.snapshot_id,
            session_id=identifiers.owner_session_id,
        )
    except PermissionError:
        pass
    else:
        raise QualificationError("A viewer resolved the owner Snapshot.")


def _require_restart_state(
    database: PostgresDatabase,
    settings: PersistenceConfiguration,
    identifiers: _QualificationIds,
) -> None:
    repository = _repository(database, settings)
    events = RunEventRepository(database)
    contexts = AgentContextRepository(database)
    for principal_id, session_id, execution_id in (
        (
            identifiers.owner_principal_id,
            identifiers.owner_session_id,
            identifiers.owner_execution_id,
        ),
        (
            identifiers.viewer_principal_id,
            identifiers.viewer_session_id,
            identifiers.viewer_execution_id,
        ),
    ):
        if repository.get_session(principal_id, session_id) is None:
            raise QualificationError("A synthetic Session did not survive restart.")
        if (
            repository.get_portfolio(
                principal_id,
                identifiers.portfolio_id,
                session_id=session_id,
            )
            is None
        ):
            raise QualificationError("A synthetic Portfolio did not survive restart.")
        if (
            repository.get_snapshot(
                principal_id,
                identifiers.snapshot_id,
                session_id=session_id,
            )
            is None
        ):
            raise QualificationError("A synthetic Snapshot did not survive restart.")
        if repository.get_run(principal_id, execution_id, session_id=session_id) is None:
            raise QualificationError("A synthetic Run did not survive restart.")
        if len(events.list_for_run(principal_id, execution_id, session_id=session_id)) != 1:
            raise QualificationError("Synthetic RunEvents did not survive restart.")
        context = contexts.get(session_id, identifiers.goal_context_id)
        if not isinstance(context, GoalAgentContext):
            raise QualificationError("A synthetic Goal context did not survive restart.")
    _require_checkpoint_state(settings, identifiers)


def _cleanup(database: PostgresDatabase, identifiers: _QualificationIds) -> None:
    with database.transaction() as connection:
        connection.execute(
            "DELETE FROM sessions WHERE principal_id IN (?, ?)",
            (identifiers.owner_principal_id, identifiers.viewer_principal_id),
        )
        connection.execute(
            "DELETE FROM application_principals WHERE principal_id IN (?, ?)",
            (identifiers.owner_principal_id, identifiers.viewer_principal_id),
        )


if __name__ == "__main__":
    raise SystemExit(main())
