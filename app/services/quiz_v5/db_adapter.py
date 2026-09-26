from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from app.services.quiz_v5.extractor import ChunkInput

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


SSA_QV5_DB_ADAPTER_VERSION = "SSA-QV5-DB-ADAPTER-V0.1"


def load_document_chunks(
    db: "Session",
    *,
    document_ids: Iterable[int],
    owner_id: int | None = None,
) -> list[ChunkInput]:
    """
    Read-only DB adapter for Quiz V5.

    Invariants:
    - requested documents exist;
    - optional owner constraint matches;
    - all requested documents are READY;
    - only active chunks are exposed;
    - ordering is deterministic.

    This adapter never writes to the database.
    """
    from sqlalchemy import select
    from app.db.models import (
        Document,
        DocumentChunk,
    )

    requested = tuple(
        sorted(
            {
                int(value)
                for value in document_ids
            }
        )
    )

    if not requested:
        raise ValueError(
            "At least one document_id is required."
        )

    stmt = select(Document).where(
        Document.id.in_(requested)
    )

    if owner_id is not None:
        stmt = stmt.where(
            Document.owner_id == owner_id
        )

    documents = list(
        db.scalars(stmt).all()
    )

    found_ids = {
        int(document.id)
        for document in documents
    }

    missing = [
        document_id
        for document_id in requested
        if document_id not in found_ids
    ]

    if missing:
        raise ValueError(
            "Document(s) not found or not owned by requested owner: "
            + ", ".join(
                str(value)
                for value in missing
            )
        )

    not_ready = [
        int(document.id)
        for document in documents
        if str(document.status or "").upper()
        != "READY"
    ]

    if not_ready:
        raise ValueError(
            "Document(s) are not READY: "
            + ", ".join(
                str(value)
                for value in not_ready
            )
        )

    rows = list(
        db.scalars(
            select(DocumentChunk)
            .where(
                DocumentChunk.document_id.in_(
                    requested
                ),
                DocumentChunk.is_active.is_(True),
            )
            .order_by(
                DocumentChunk.document_id,
                DocumentChunk.chunk_index,
                DocumentChunk.id,
            )
        ).all()
    )

    if not rows:
        raise ValueError(
            "Selected document(s) have no active chunks."
        )

    return [
        ChunkInput(
            document_id=int(
                chunk.document_id
            ),
            chunk_id=int(
                chunk.id
            ),
            section_id=(
                int(chunk.section_id)
                if chunk.section_id is not None
                else None
            ),
            text=str(
                chunk.content
                or ""
            ),
            chunk_index=int(
                chunk.chunk_index
            ),
        )
        for chunk in rows
    ]
