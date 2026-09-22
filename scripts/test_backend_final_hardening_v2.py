from __future__ import annotations

from pathlib import Path

from app.db.models import DocumentChunk
from app.main import app
from app.services.source_access import (
    validate_owned_active_chunk_ids,
    validate_owned_document_ids,
)


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    document_code = (
        ROOT / "app/services/document_service.py"
    ).read_text(encoding="utf-8")
    flashcard_code = (
        ROOT / "app/services/flashcard_service.py"
    ).read_text(encoding="utf-8")
    quiz_code = (
        ROOT / "app/services/quiz_service.py"
    ).read_text(encoding="utf-8")
    schema = (
        ROOT / "database/schema.sql"
    ).read_text(encoding="utf-8")
    migration_path = (
        ROOT / "alembic/versions/0002_versioned_document_chunks.py"
    )
    migration = (
        migration_path.read_text(encoding="utf-8")
        if migration_path.exists()
        else ""
    )

    create_quiz_block = quiz_code[
        quiz_code.index("def create_quiz("):
        quiz_code.index(
            "# =========================================================\n# JSON PARSING"
        )
    ]

    checks = {
        "ORM versioned fields": all(
            hasattr(DocumentChunk, field)
            for field in (
                "chunk_set_id",
                "chunking_algorithm",
                "is_active",
                "superseded_at",
            )
        ),
        "Schema versioned fields": all(
            token in schema
            for token in (
                "chunk_set_id character varying(80)",
                "chunking_algorithm character varying(50)",
                "is_active boolean",
                "superseded_at timestamp with time zone",
            )
        ),
        "Schema set uniqueness": (
            "ADD CONSTRAINT uq_document_chunks_set_index "
            "UNIQUE (document_id, chunk_set_id, chunk_index)"
            in schema
        ),
        "Schema active unique index": (
            "uq_document_chunks_active_document_index"
            in schema
        ),
        "Schema active section index": (
            "ix_document_chunks_active_section"
            in schema
        ),
        "Alembic 0002 revision chain": all(
            token in migration
            for token in (
                'revision: str = "0002_versioned_document_chunks"',
                'down_revision: Union[str, None] = "0001_baseline"',
            )
        ),
        "READY rollback snapshot": all(
            token in document_code
            for token in (
                "previous_status",
                "previous_active_count",
            )
        ),
        "READY rollback recovery": all(
            token in document_code
            for token in (
                "active_count_after_rollback",
                'doc.status = "READY"',
                'doc.status = "FAILED"',
            )
        ),
        "Flashcard document ownership": (
            "document_ids = validate_owned_document_ids("
            in flashcard_code
        ),
        "Flashcard active chunk ownership": (
            "validate_owned_active_chunk_ids("
            in flashcard_code
        ),
        "Flashcard global AI owner filter": (
            "Document.owner_id == owner_id,"
            in flashcard_code
        ),
        "Manual Quiz document ownership": (
            "document_ids = validate_owned_document_ids("
            in create_quiz_block
        ),
        "Manual Quiz active chunk ownership": (
            "validate_owned_active_chunk_ids("
            in create_quiz_block
        ),
        "Shared document validator importable": callable(
            validate_owned_document_ids
        ),
        "Shared chunk validator importable": callable(
            validate_owned_active_chunk_ids
        ),
    }

    app.openapi()
    checks["OpenAPI builds"] = True

    print()
    print("=" * 72)
    print("BACKEND FINAL HARDENING V2 WIRING TEST")
    print("=" * 72)

    failed = []

    for name, passed in checks.items():
        print(f"{name}: {passed}")
        if not passed:
            failed.append(name)

    if failed:
        print("Result: FAIL")
        print("Failed:", ", ".join(failed))
        raise SystemExit(1)

    print("Result: PASS")
    print("=" * 72)


if __name__ == "__main__":
    main()
