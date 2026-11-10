"""Least-privilege PostgreSQL role policy for managed application state."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from typing import Any

import psycopg


def database_role_policy_statements(
    *,
    database: str,
    schema: str,
    migration_role: str,
    runtime_role: str,
    retention_role: str,
) -> tuple[str, ...]:
    """Render the reviewable SQL used by both tests and the Cloud SQL Data API."""

    database_identifier = _quote_identifier(database)
    schema_identifier = _quote_identifier(schema)
    migration_identifier = _quote_identifier(migration_role)
    runtime_identifier = _quote_identifier(runtime_role)
    retention_identifier = _quote_identifier(retention_role)
    statements = [f"REVOKE CREATE ON SCHEMA {schema_identifier} FROM PUBLIC;"]
    for role in (migration_identifier, runtime_identifier, retention_identifier):
        statements.extend(
            (
                f"GRANT CONNECT ON DATABASE {database_identifier} TO {role};",
                f"ALTER ROLE {role} IN DATABASE {database_identifier} "
                f"SET search_path TO {schema_identifier}, pg_catalog;",
            )
        )
    statements.extend(
        (
            f"GRANT USAGE, CREATE ON SCHEMA {schema_identifier} TO {migration_identifier};",
            f"GRANT USAGE ON SCHEMA {schema_identifier} TO {runtime_identifier};",
            f"GRANT USAGE ON SCHEMA {schema_identifier} TO {retention_identifier};",
        )
    )
    return tuple(statements)


def migration_default_privilege_statements(
    *,
    schema: str,
    runtime_role: str,
    retention_role: str,
) -> tuple[str, ...]:
    """Render grants that the migration role must install for its own future objects."""

    schema_identifier = _quote_identifier(schema)
    runtime_identifier = _quote_identifier(runtime_role)
    retention_identifier = _quote_identifier(retention_role)
    return (
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema_identifier} "
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {runtime_identifier};",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema_identifier} "
        f"GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO {runtime_identifier};",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema_identifier} "
        f"GRANT SELECT, DELETE ON TABLES TO {retention_identifier};",
    )


def apply_database_role_policy(
    connection: psycopg.Connection[Any],
    *,
    database: str,
    schema: str,
    migration_role: str,
    runtime_role: str,
    retention_role: str,
) -> None:
    """Apply the durable migration/runtime/retention privilege boundary."""

    for statement in database_role_policy_statements(
        database=database,
        schema=schema,
        migration_role=migration_role,
        runtime_role=runtime_role,
        retention_role=retention_role,
    ):
        connection.execute(statement)


def apply_migration_default_privileges(
    connection: psycopg.Connection[Any],
    *,
    schema: str,
    runtime_role: str,
    retention_role: str,
) -> None:
    """Set future-object grants as the role that will own migrated objects."""

    for statement in migration_default_privilege_statements(
        schema=schema,
        runtime_role=runtime_role,
        retention_role=retention_role,
    ):
        connection.execute(statement)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--migration-role", required=True)
    parser.add_argument("--runtime-role", required=True)
    parser.add_argument("--retention-role", required=True)
    args = parser.parse_args(argv)
    print(
        "\n".join(
            database_role_policy_statements(
                database=args.database,
                schema=args.schema,
                migration_role=args.migration_role,
                runtime_role=args.runtime_role,
                retention_role=args.retention_role,
            )
        )
    )
    return 0


def _quote_identifier(value: str) -> str:
    if not value or "\x00" in value:
        raise ValueError("PostgreSQL identifiers must be non-empty and contain no NUL bytes.")
    return '"' + value.replace('"', '""') + '"'


if __name__ == "__main__":
    raise SystemExit(main())
