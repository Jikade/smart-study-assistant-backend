from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import delete, func, select, text

from app.db.models import (
    Document,
    DocumentChunk,
    DocumentProcessingJob,
)
from app.db.session import SessionLocal
from app.services import document_service
from app.services.source_access import (
    validate_owned_active_chunk_ids,
    validate_owned_document_ids,
)


DOCUMENT_ID = 2
OWNER_ID = 1
SUBJECT_ID = 2


def expect_403(fn, label: str) -> None:
    try:
        fn()
    except HTTPException as exc:
        assert exc.status_code == 403, (
            f"{label}: expected 403, got {exc.status_code}"
        )
        print(f"{label}: PASS (403)")
        return

    raise AssertionError(
        f"{label}: expected HTTPException 403"
    )


def main() -> None:
    db = SessionLocal()

    original_extract_text = document_service.extract_text

    old_status = None
    old_processing_error = None
    max_job_id_before = 0

    try:
        print()
        print("=" * 72)
        print("BACKEND FINAL HARDENING V2 RUNTIME TEST")
        print("=" * 72)

        # -------------------------------------------------
        # 1. Verify actual database schema/revision.
        # -------------------------------------------------
        revision = db.execute(
            text(
                "SELECT version_num "
                "FROM alembic_version "
                "LIMIT 1"
            )
        ).scalar_one_or_none()

        assert revision == "0002_versioned_document_chunks", revision

        columns = set(
            db.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'document_chunks'
                      AND column_name IN (
                          'chunk_set_id',
                          'chunking_algorithm',
                          'is_active',
                          'superseded_at'
                      )
                    """
                )
            ).scalars().all()
        )

        assert columns == {
            "chunk_set_id",
            "chunking_algorithm",
            "is_active",
            "superseded_at",
        }, columns

        indexes = set(
            db.execute(
                text(
                    """
                    SELECT indexname
                    FROM pg_indexes
                    WHERE schemaname = 'public'
                      AND tablename = 'document_chunks'
                    """
                )
            ).scalars().all()
        )

        required_indexes = {
            "uq_document_chunks_active_document_index",
            "ix_document_chunks_active_section",
        }

        assert required_indexes.issubset(indexes), indexes

        print("Actual DB revision/schema/indexes: PASS")

        # -------------------------------------------------
        # 2. Validate legitimate ownership.
        # -------------------------------------------------
        document_ids = validate_owned_document_ids(
            db,
            OWNER_ID,
            [DOCUMENT_ID],
            subject_id=SUBJECT_ID,
        )

        assert document_ids == [DOCUMENT_ID]

        active_chunk_ids = list(
            db.scalars(
                select(DocumentChunk.id)
                .where(
                    DocumentChunk.document_id == DOCUMENT_ID,
                    DocumentChunk.is_active.is_(True),
                )
                .order_by(DocumentChunk.chunk_index)
            ).all()
        )

        assert active_chunk_ids, "Document 2 has no active chunks"

        sample_chunk_id = int(active_chunk_ids[0])

        validated_chunks = validate_owned_active_chunk_ids(
            db,
            OWNER_ID,
            [sample_chunk_id],
            allowed_document_ids=[DOCUMENT_ID],
            subject_id=SUBJECT_ID,
        )

        assert validated_chunks == [sample_chunk_id]

        print(
            "Legitimate document/chunk ownership: PASS "
            f"(chunk={sample_chunk_id})"
        )

        # -------------------------------------------------
        # 3. Validate access denial.
        # -------------------------------------------------
        expect_403(
            lambda: validate_owned_document_ids(
                db,
                999999,
                [DOCUMENT_ID],
                subject_id=SUBJECT_ID,
            ),
            "Foreign-owner document access",
        )

        expect_403(
            lambda: validate_owned_active_chunk_ids(
                db,
                999999,
                [sample_chunk_id],
                allowed_document_ids=[DOCUMENT_ID],
                subject_id=SUBJECT_ID,
            ),
            "Foreign-owner chunk access",
        )

        expect_403(
            lambda: validate_owned_active_chunk_ids(
                db,
                OWNER_ID,
                [sample_chunk_id],
                allowed_document_ids=[999999],
                subject_id=SUBJECT_ID,
            ),
            "Chunk outside requested document_ids",
        )

        # -------------------------------------------------
        # 4. Verify failed re-index preserves READY and the
        #    exact active set.
        #
        #    We fail at extract_text BEFORE new chunks are
        #    written. The test then removes its processing
        #    job and restores processing_error.
        # -------------------------------------------------
        doc = db.get(Document, DOCUMENT_ID)

        assert doc is not None, "Document 2 not found"
        assert doc.status == "READY", (
            f"Document 2 must be READY before test, got {doc.status}"
        )

        old_status = doc.status
        old_processing_error = doc.processing_error

        active_before = list(active_chunk_ids)

        max_job_id_before = int(
            db.scalar(
                select(
                    func.coalesce(
                        func.max(DocumentProcessingJob.id),
                        0,
                    )
                )
            )
            or 0
        )

        def forced_extract_failure(*args, **kwargs):
            raise RuntimeError(
                "FORCED_RUNTIME_ROLLBACK_TEST"
            )

        document_service.extract_text = forced_extract_failure

        try:
            document_service.process_document(
                db,
                doc,
            )
            raise AssertionError(
                "process_document should have raised"
            )
        except RuntimeError as exc:
            assert (
                "FORCED_RUNTIME_ROLLBACK_TEST"
                in str(exc)
            ), exc

        db.expire_all()

        doc_after = db.get(
            Document,
            DOCUMENT_ID,
        )

        assert doc_after is not None
        assert doc_after.status == "READY", (
            "Failed re-index did not restore READY: "
            f"{doc_after.status}"
        )

        active_after = list(
            db.scalars(
                select(DocumentChunk.id)
                .where(
                    DocumentChunk.document_id == DOCUMENT_ID,
                    DocumentChunk.is_active.is_(True),
                )
                .order_by(DocumentChunk.chunk_index)
            ).all()
        )

        assert active_after == active_before, (
            active_before,
            active_after,
        )

        print(
            "Failed re-index preserves READY + active set: PASS"
        )

        # -------------------------------------------------
        # Cleanup the deliberate failed processing job and
        # restore the old processing_error/status.
        # -------------------------------------------------
        document_service.extract_text = (
            original_extract_text
        )

        db.execute(
            delete(DocumentProcessingJob).where(
                DocumentProcessingJob.document_id
                == DOCUMENT_ID,
                DocumentProcessingJob.id
                > max_job_id_before,
            )
        )

        doc_cleanup = db.get(
            Document,
            DOCUMENT_ID,
        )

        if doc_cleanup is not None:
            doc_cleanup.status = old_status
            doc_cleanup.processing_error = (
                old_processing_error
            )

        db.commit()

        print("Runtime-test cleanup: PASS")

        print()
        print("Result: PASS")
        print("=" * 72)

    finally:
        document_service.extract_text = (
            original_extract_text
        )

        try:
            if old_status is not None:
                db.execute(
                    delete(DocumentProcessingJob).where(
                        DocumentProcessingJob.document_id
                        == DOCUMENT_ID,
                        DocumentProcessingJob.id
                        > max_job_id_before,
                    )
                )

                doc_cleanup = db.get(
                    Document,
                    DOCUMENT_ID,
                )

                if doc_cleanup is not None:
                    doc_cleanup.status = old_status
                    doc_cleanup.processing_error = (
                        old_processing_error
                    )

                db.commit()
        except Exception:
            db.rollback()

        db.close()


if __name__ == "__main__":
    main()
