from __future__ import annotations

from collections.abc import Iterable

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Document, DocumentChunk, Subject


def _normalize_ids(values: Iterable[int] | None) -> list[int]:
    return list(dict.fromkeys(int(value) for value in (values or [])))


def validate_owned_subject_id(
    db: Session,
    owner_id: int,
    subject_id: int | None,
) -> int | None:
    # Hide foreign-subject existence across tenants.
    if subject_id is None:
        return None

    owned_subject_id = db.scalar(
        select(Subject.id).where(
            Subject.id == int(subject_id),
            Subject.owner_id == owner_id,
        )
    )

    if owned_subject_id is None:
        raise HTTPException(
            status_code=404,
            detail="Subject not found",
        )

    return int(owned_subject_id)


def validate_owned_document_ids(
    db: Session,
    owner_id: int,
    document_ids: Iterable[int] | None,
    *,
    subject_id: int | None = None,
) -> list[int]:
    normalized = _normalize_ids(document_ids)
    if not normalized:
        return []

    stmt = select(Document.id).where(
        Document.id.in_(normalized),
        Document.owner_id == owner_id,
    )

    if subject_id is not None:
        stmt = stmt.where(Document.subject_id == subject_id)

    accessible = set(int(value) for value in db.scalars(stmt).all())

    if accessible != set(normalized):
        raise HTTPException(
            status_code=403,
            detail=(
                "One or more documents are not accessible "
                "or do not belong to the selected subject."
            ),
        )

    return normalized


def validate_owned_active_chunk_ids(
    db: Session,
    owner_id: int,
    chunk_ids: Iterable[int] | None,
    *,
    allowed_document_ids: Iterable[int] | None = None,
    subject_id: int | None = None,
) -> list[int]:
    normalized_chunks = _normalize_ids(chunk_ids)
    if not normalized_chunks:
        return []

    normalized_documents = _normalize_ids(allowed_document_ids)

    stmt = (
        select(DocumentChunk.id)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            DocumentChunk.id.in_(normalized_chunks),
            DocumentChunk.is_active.is_(True),
            Document.owner_id == owner_id,
        )
    )

    if normalized_documents:
        stmt = stmt.where(
            DocumentChunk.document_id.in_(normalized_documents)
        )

    if subject_id is not None:
        stmt = stmt.where(Document.subject_id == subject_id)

    accessible = set(int(value) for value in db.scalars(stmt).all())

    if accessible != set(normalized_chunks):
        raise HTTPException(
            status_code=403,
            detail=(
                "One or more source chunks are not accessible, "
                "are inactive, or do not belong to the selected documents."
            ),
        )

    return normalized_chunks
