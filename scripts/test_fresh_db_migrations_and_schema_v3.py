from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

from app.core.config import get_settings


ROOT = Path(__file__).resolve().parents[1]
TEST_SUFFIX = "_migration_verify"


def conn_kwargs(url, database: str) -> dict:
    return {
        "host": url.host or "localhost",
        "port": url.port or 5432,
        "user": url.username,
        "password": url.password,
        "dbname": database,
    }


def scalar_rows(conn, query: str) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(query)
        return [str(row[0]) for row in cur.fetchall()]


def table_names(conn) -> set[str]:
    return set(
        scalar_rows(
            conn,
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_type = 'BASE TABLE'
              AND table_name <> 'alembic_version'
            ORDER BY table_name
            """,
        )
    )


def column_signature(conn) -> set[tuple]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                table_name,
                column_name,
                data_type,
                udt_name,
                is_nullable,
                COALESCE(column_default, '')
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name <> 'alembic_version'
            ORDER BY table_name, ordinal_position
            """
        )
        return {
            tuple(row)
            for row in cur.fetchall()
        }


def _normalize_check_definition(
    definition: str,
) -> str:
    """
    Normalize PostgreSQL-equivalent CHECK deparse forms.

    PostgreSQL may represent the same varchar/text ANY-array CHECK either
    by casting each string literal to text or by casting the whole array
    to text[]. These forms are semantically equivalent but stringify
    differently through pg_get_constraintdef().
    """

    value = re.sub(
        r"\s+",
        " ",
        definition.strip(),
    )

    # Normalize casts applied specifically to quoted string literals.
    value = re.sub(
        r"('(?:''|[^'])*')"
        r"::character varying(?:::text)?",
        r"\1",
        value,
        flags=re.I,
    )

    value = re.sub(
        r"('(?:''|[^'])*')::text",
        r"\1",
        value,
        flags=re.I,
    )

    # After literal normalization, an explicit array-level text[] cast is
    # redundant for the equality/ANY checks used by this schema.
    value = re.sub(
        r"\]::text\[\]",
        "]",
        value,
        flags=re.I,
    )

    # Cosmetic spacing differences are not schema drift.
    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    value = re.sub(
        r"\s*([(),=])\s*",
        r"\1",
        value,
    )

    return value


def constraint_signature(conn) -> set[tuple]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                cls.relname AS table_name,
                con.conname AS constraint_name,
                con.contype AS constraint_type,
                pg_get_constraintdef(con.oid, true) AS definition
            FROM pg_constraint con
            JOIN pg_class cls
              ON cls.oid = con.conrelid
            JOIN pg_namespace ns
              ON ns.oid = cls.relnamespace
            WHERE ns.nspname = 'public'
            ORDER BY cls.relname, con.conname
            """
        )

        result: set[tuple] = set()

        for (
            table_name,
            constraint_name,
            constraint_type,
            definition,
        ) in cur.fetchall():
            normalized_definition = str(
                definition
            )

            if constraint_type == "c":
                normalized_definition = (
                    _normalize_check_definition(
                        normalized_definition
                    )
                )

            result.add(
                (
                    table_name,
                    constraint_name,
                    constraint_type,
                    normalized_definition,
                )
            )

        return result


def index_signature(conn) -> set[tuple]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                tablename,
                indexname,
                regexp_replace(indexdef, '\\s+', ' ', 'g')
            FROM pg_indexes
            WHERE schemaname = 'public'
            ORDER BY tablename, indexname
            """
        )
        return {
            tuple(row)
            for row in cur.fetchall()
        }


def extension_names(conn) -> set[str]:
    return set(
        scalar_rows(
            conn,
            """
            SELECT extname
            FROM pg_extension
            ORDER BY extname
            """,
        )
    )


def alembic_version(conn) -> str | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT to_regclass('public.alembic_version')
            """
        )
        exists = cur.fetchone()[0]

        if exists is None:
            return None

        cur.execute(
            "SELECT version_num FROM alembic_version"
        )
        row = cur.fetchone()

        return None if row is None else str(row[0])


def print_diff(
    label: str,
    current: set,
    fresh: set,
    *,
    max_items: int = 30,
) -> bool:
    only_current = sorted(
        current - fresh,
        key=str,
    )
    only_fresh = sorted(
        fresh - current,
        key=str,
    )

    if not only_current and not only_fresh:
        print(f"{label:<34} PASS")
        return True

    print(f"{label:<34} DRIFT")

    if only_current:
        print("  Present only in CURRENT DB:")
        for item in only_current[:max_items]:
            print(f"    {item}")
        if len(only_current) > max_items:
            print(
                f"    ... +{len(only_current) - max_items} more"
            )

    if only_fresh:
        print("  Present only in FRESH DB:")
        for item in only_fresh[:max_items]:
            print(f"    {item}")
        if len(only_fresh) > max_items:
            print(
                f"    ... +{len(only_fresh) - max_items} more"
            )

    return False


def main() -> None:
    settings = get_settings()
    source_url = make_url(
        settings.database_url
    )

    source_db = source_url.database

    if not source_db:
        raise RuntimeError(
            "DATABASE_URL does not contain a database name"
        )

    if source_db.endswith(TEST_SUFFIX):
        raise RuntimeError(
            "Refusing to run because current DATABASE_URL "
            "already points to the migration verification DB"
        )

    test_db = f"{source_db}{TEST_SUFFIX}"

    print()
    print("=" * 92)
    print("FRESH DATABASE MIGRATION + SCHEMA REPRODUCIBILITY")
    print("=" * 92)
    print(f"Current database : {source_db}")
    print(f"Temporary DB     : {test_db}")
    print(
        "Safety           : current DB is read-only for this test; "
        "temporary DB is recreated"
    )
    print("=" * 92)

    admin_kwargs = conn_kwargs(
        source_url,
        "postgres",
    )

    # -----------------------------------------------------
    # Recreate isolated test DB.
    # -----------------------------------------------------
    with psycopg.connect(
        **admin_kwargs,
        autocommit=True,
    ) as admin:
        with admin.cursor() as cur:
            cur.execute(
                """
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = %s
                  AND pid <> pg_backend_pid()
                """,
                (test_db,),
            )

            cur.execute(
                sql.SQL("DROP DATABASE IF EXISTS {}").format(
                    sql.Identifier(test_db)
                )
            )

            cur.execute(
                sql.SQL("CREATE DATABASE {}").format(
                    sql.Identifier(test_db)
                )
            )

    print("Create isolated temporary DB        PASS")

    fresh_url = source_url.set(
        database=test_db
    )

    env = os.environ.copy()
    env["DATABASE_URL"] = (
        fresh_url.render_as_string(
            hide_password=False
        )
    )

    try:
        # -------------------------------------------------
        # Run Alembic from zero to HEAD.
        # -------------------------------------------------
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "alembic",
                "-c",
                str(ROOT / "alembic.ini"),
                "upgrade",
                "head",
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
        )

        if result.stdout.strip():
            print(result.stdout.strip())

        if result.returncode != 0:
            if result.stderr.strip():
                print(result.stderr.strip())

            raise RuntimeError(
                "alembic upgrade head FAILED on fresh DB"
            )

        print("Alembic upgrade head on fresh DB    PASS")

        source_kwargs = conn_kwargs(
            source_url,
            source_db,
        )
        fresh_kwargs = conn_kwargs(
            source_url,
            test_db,
        )

        with (
            psycopg.connect(
                **source_kwargs
            ) as current_conn,
            psycopg.connect(
                **fresh_kwargs
            ) as fresh_conn,
        ):
            current_head = alembic_version(
                current_conn
            )
            fresh_head = alembic_version(
                fresh_conn
            )

            print(
                f"Current alembic version              "
                f"{current_head}"
            )
            print(
                f"Fresh alembic version                "
                f"{fresh_head}"
            )

            same_head = (
                current_head is not None
                and current_head == fresh_head
            )

            print(
                f"{'Alembic version parity':<34} "
                f"{'PASS' if same_head else 'DRIFT'}"
            )

            current_ext = extension_names(
                current_conn
            )
            fresh_ext = extension_names(
                fresh_conn
            )

            vector_ok = (
                "vector" in fresh_ext
            )

            print(
                f"{'Fresh DB pgvector extension':<34} "
                f"{'PASS' if vector_ok else 'FAIL'}"
            )

            tables_ok = print_diff(
                "Base-table parity",
                table_names(current_conn),
                table_names(fresh_conn),
            )

            columns_ok = print_diff(
                "Column parity",
                column_signature(current_conn),
                column_signature(fresh_conn),
            )

            constraints_ok = print_diff(
                "Constraint parity",
                constraint_signature(current_conn),
                constraint_signature(fresh_conn),
            )

            indexes_ok = print_diff(
                "Index parity",
                index_signature(current_conn),
                index_signature(fresh_conn),
            )

            all_ok = all(
                [
                    same_head,
                    vector_ok,
                    tables_ok,
                    columns_ok,
                    constraints_ok,
                    indexes_ok,
                ]
            )

        print()
        print("-" * 92)

        if all_ok:
            print(
                "RESULT: PASS - fresh database is reproducible "
                "from Alembic HEAD"
            )
        else:
            print(
                "RESULT: DRIFT DETECTED - current DB and fresh "
                "Alembic DB are not equivalent"
            )
            print(
                "Do NOT mark migration verification complete "
                "until the differences are reconciled."
            )

        print("-" * 92)

        if not all_ok:
            raise SystemExit(2)

    finally:
        # -------------------------------------------------
        # Always remove isolated test DB.
        # -------------------------------------------------
        with psycopg.connect(
            **admin_kwargs,
            autocommit=True,
        ) as admin:
            with admin.cursor() as cur:
                cur.execute(
                    """
                    SELECT pg_terminate_backend(pid)
                    FROM pg_stat_activity
                    WHERE datname = %s
                      AND pid <> pg_backend_pid()
                    """,
                    (test_db,),
                )

                cur.execute(
                    sql.SQL(
                        "DROP DATABASE IF EXISTS {}"
                    ).format(
                        sql.Identifier(test_db)
                    )
                )

        print(
            "Drop isolated temporary DB          PASS"
        )
        print("=" * 92)


if __name__ == "__main__":
    main()
