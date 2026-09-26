from __future__ import annotations

from pathlib import Path

from sqlalchemy import text

from app.db.session import SessionLocal


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    schema = (
        ROOT
        / "database"
        / "schema.sql"
    ).read_text(
        encoding="utf-8",
    )

    assert (
        "V5_DETERMINISTIC"
        in schema
    ), "database/schema.sql is missing V5_DETERMINISTIC"

    db = SessionLocal()

    try:
        definition = db.execute(
            text(
                """
                SELECT pg_get_constraintdef(c.oid)
                FROM pg_constraint c
                JOIN pg_class t
                  ON t.oid = c.conrelid
                JOIN pg_namespace n
                  ON n.oid = t.relnamespace
                WHERE
                    n.nspname = 'public'
                    AND t.relname = 'quizzes'
                    AND c.conname = 'quizzes_generation_mode_check'
                """
            )
        ).scalar_one()

        assert (
            "V5_DETERMINISTIC"
            in str(definition)
        ), definition

        print()
        print("=" * 88)
        print("QUIZ V5 GENERATION MODE SCHEMA V0.1 REGRESSION")
        print("=" * 88)
        print("schema.sql synchronized       :", True)
        print("DB constraint found           :", True)
        print("V5_DETERMINISTIC allowed      :", True)
        print("Result                        : PASS")
        print("=" * 88)

    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    main()
