"""Fresh-capable immutable baseline schema.

This revision supports two cases:

1. A brand-new empty PostgreSQL database:
   execute the frozen SQL snapshot in alembic/sql/0001_baseline.sql.

2. A legacy/pre-provisioned database that already has the baseline schema:
   keep the historical baseline/stamp behavior and do not recreate tables.

Do not point this revision at mutable database/schema.sql. The snapshot is
intentionally frozen so future schema changes must be represented by later
Alembic revisions.
"""

from __future__ import annotations

from pathlib import Path

from alembic import op
from sqlalchemy import text


revision = '0001_baseline'
down_revision = None
branch_labels = None
depends_on = None


def _strip_psql_meta_commands(
    script: str,
) -> str:
    """
    Remove psql-only meta-command lines from pg_dump output.

    These lines are commands for the psql CLI, not SQL statements,
    so they cannot be executed through psycopg/SQLAlchemy.
    """

    kept_lines: list[str] = []

    for line in script.splitlines(
        keepends=True
    ):
        stripped = line.lstrip()

        if stripped.startswith("\\"):
            continue

        kept_lines.append(line)

    return "".join(kept_lines)


def _split_sql_statements(script: str) -> list[str]:
    """Split PostgreSQL SQL while respecting strings/comments/dollar quotes."""

    statements: list[str] = []
    buffer: list[str] = []

    i = 0
    n = len(script)

    single_quote = False
    double_quote = False
    line_comment = False
    block_comment_depth = 0
    dollar_tag: str | None = None

    while i < n:
        ch = script[i]
        nxt = script[i + 1] if i + 1 < n else ""

        if line_comment:
            buffer.append(ch)

            if ch == "\n":
                line_comment = False

            i += 1
            continue

        if block_comment_depth > 0:
            buffer.append(ch)

            if ch == "/" and nxt == "*":
                buffer.append(nxt)
                block_comment_depth += 1
                i += 2
                continue

            if ch == "*" and nxt == "/":
                buffer.append(nxt)
                block_comment_depth -= 1
                i += 2
                continue

            i += 1
            continue

        if dollar_tag is not None:
            if script.startswith(dollar_tag, i):
                buffer.append(dollar_tag)
                i += len(dollar_tag)
                dollar_tag = None
                continue

            buffer.append(ch)
            i += 1
            continue

        if single_quote:
            buffer.append(ch)

            if ch == "'" and nxt == "'":
                buffer.append(nxt)
                i += 2
                continue

            if ch == "'":
                single_quote = False

            i += 1
            continue

        if double_quote:
            buffer.append(ch)

            if ch == '"' and nxt == '"':
                buffer.append(nxt)
                i += 2
                continue

            if ch == '"':
                double_quote = False

            i += 1
            continue

        if ch == "-" and nxt == "-":
            buffer.extend([ch, nxt])
            line_comment = True
            i += 2
            continue

        if ch == "/" and nxt == "*":
            buffer.extend([ch, nxt])
            block_comment_depth = 1
            i += 2
            continue

        if ch == "'":
            buffer.append(ch)
            single_quote = True
            i += 1
            continue

        if ch == '"':
            buffer.append(ch)
            double_quote = True
            i += 1
            continue

        if ch == "$":
            j = i + 1

            while j < n and (
                script[j].isalnum()
                or script[j] == "_"
            ):
                j += 1

            if j < n and script[j] == "$":
                tag = script[i:j + 1]

                # PostgreSQL dollar tags are $$ or $tag$.
                buffer.append(tag)
                dollar_tag = tag
                i = j + 1
                continue

        if ch == ";":
            statement = "".join(buffer).strip()

            if statement:
                statements.append(statement)

            buffer = []
            i += 1
            continue

        buffer.append(ch)
        i += 1

    tail = "".join(buffer).strip()

    if tail:
        statements.append(tail)

    if (
        single_quote
        or double_quote
        or block_comment_depth
        or dollar_tag is not None
    ):
        raise RuntimeError(
            "Unterminated SQL quote/comment/dollar-quote "
            "in 0001 baseline snapshot"
        )

    return statements


def _baseline_snapshot_path() -> Path:
    # alembic/versions/0001_*.py -> alembic/sql/0001_baseline.sql
    return (
        Path(__file__).resolve().parents[1]
        / "sql"
        / "0001_baseline.sql"
    )


def _baseline_schema_already_exists() -> bool:
    bind = op.get_bind()

    # "users" is part of the original schema. If it already exists, this is
    # a legacy/pre-provisioned DB and revision 0001 should behave as a stamp.
    result = bind.execute(
        text(
            "SELECT to_regclass('public.users') IS NOT NULL"
        )
    )

    return bool(result.scalar())


def upgrade() -> None:
    if _baseline_schema_already_exists():
        return

    snapshot_path = _baseline_snapshot_path()

    if not snapshot_path.exists():
        raise RuntimeError(
            f"Baseline SQL snapshot is missing: {snapshot_path}"
        )

    script = snapshot_path.read_text(
        encoding="utf-8-sig"
    )

    script = _strip_psql_meta_commands(
        script
    )

    statements = _split_sql_statements(
        script
    )

    if not statements:
        raise RuntimeError(
            "Baseline SQL snapshot contains no executable statements"
        )

    bind = op.get_bind()

    for number, statement in enumerate(
        statements,
        start=1,
    ):
        normalized = statement.strip()

        if not normalized:
            continue

        upper = normalized.upper()

        # Alembic owns this internal version table. A pg_dump snapshot
        # taken from an Alembic-managed database may contain DDL for
        # alembic_version; executing that DDL here can drop/recreate or
        # otherwise interfere with Alembic's own revision bookkeeping.
        if "ALEMBIC_VERSION" in upper:
            continue

        # Alembic already controls the migration transaction.
        if upper in {
            "BEGIN",
            "BEGIN TRANSACTION",
            "COMMIT",
            "END",
        }:
            continue

        if normalized.startswith("\\"):
            raise RuntimeError(
                "psql meta-command found in baseline snapshot; "
                "only SQL is supported"
            )

        # Psycopg3 treats percent signs as placeholder syntax.
        # pg_dump PL/pgSQL bodies can contain literal percent signs,
        # e.g. RAISE EXCEPTION messages. Escape for the driver only;
        # PostgreSQL receives the original single-percent text.
        driver_sql = normalized.replace(
            "%",
            "%%",
        )

        try:
            bind.exec_driver_sql(
                driver_sql
            )
        except Exception as exc:
            preview = " ".join(
                normalized.split()
            )[:240]

            raise RuntimeError(
                "0001 baseline SQL failed at statement "
                f"#{number}: {preview}"
            ) from exc


    # The frozen pg_dump snapshot may rebuild schema "public"
    # (for example via DROP SCHEMA ... CASCADE / CREATE SCHEMA).
    # That can remove the Alembic version table which Alembic created
    # before entering this revision. Recreate only Alembic's own minimal
    # bookkeeping table here, after all baseline SQL has finished.
    #
    # Alembic itself will insert revision "0001_baseline" immediately
    # after upgrade() returns.
    bind.exec_driver_sql(
        """
        CREATE TABLE IF NOT EXISTS public.alembic_version (
            version_num VARCHAR(32) NOT NULL,
            CONSTRAINT alembic_version_pkc
                PRIMARY KEY (version_num)
        )
        """
    )

    # pg_dump commonly clears search_path with:
    #   pg_catalog.set_config('search_path', '', false)
    # Alembic writes to the version table using the unqualified name
    # "alembic_version", so restore the normal application schema before
    # returning control to Alembic.
    bind.exec_driver_sql(
        "SET search_path TO public"
    )



def downgrade() -> None:
    # This project historically treated 0001 as a baseline marker.
    # Destructive baseline downgrade is intentionally unsupported.
    pass
