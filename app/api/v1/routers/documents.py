from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession
from app.db.models import Document, DocumentChunk, Subject
from app.schemas.common import MessageResponse, Page
from app.schemas.documents import ChunkOut, DocumentOut, ProcessDocumentResponse
from app.services.document_service import process_document, save_upload

from app.services.document_service import (
    embed_existing_chunks,
)

from app.core.config import get_settings

settings = get_settings()

from sqlalchemy import func, select

from app.schemas.documents import (
    EmbedDocumentResponse,
)



router = APIRouter(prefix="/documents", tags=["documents"])


def owned_document(db: DbSession, user_id: int, document_id: int) -> Document:
    row = db.scalar(select(Document).where(Document.id == document_id, Document.owner_id == user_id))
    if row is None:
        raise HTTPException(404, "Document not found")
    return row


@router.post(
    "/{document_id}/embed",
    response_model=EmbedDocumentResponse,
)
def embed_document(
    document_id: int,
    db: DbSession,
    user: CurrentUser,
    force: bool = False,
):

    doc = owned_document(
        db,
        user.id,
        document_id,
    )

    if doc.status != "READY":
        raise HTTPException(
            400,
            "Document must be READY before embedding.",
        )

    chunks_total = (
        db.scalar(
            select(
                func.count(
                    DocumentChunk.id
                )
            )
            .where(
                DocumentChunk.document_id
                == document_id
            )
        )
        or 0
    )

    try:

        created = embed_existing_chunks(
            db,
            document_id,
            force=force,
        )

    except Exception as exc:

        raise HTTPException(
            422,
            str(exc),
        ) from exc

    return EmbedDocumentResponse(
        document_id=document_id,
        chunks_total=chunks_total,
        embeddings_created=created,
        embedding_model=(
            settings.ai_embedding_model
            or "not-configured"
        ),
    )

@router.get("", response_model=Page[DocumentOut])
def list_documents(db: DbSession, user: CurrentUser, subject_id: int | None = None, limit: int = 50, offset: int = 0):
    filters = [Document.owner_id == user.id]
    if subject_id is not None:
        filters.append(Document.subject_id == subject_id)
    total = db.scalar(select(func.count(Document.id)).where(*filters)) or 0
    items = list(db.scalars(select(Document).where(*filters).order_by(Document.created_at.desc()).limit(limit).offset(offset)).all())
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.post("/upload", response_model=DocumentOut, status_code=201)
def upload_document(
    db: DbSession,
    user: CurrentUser,
    file: UploadFile = File(...),
    subject_id: int | None = Form(default=None),
    process_now: bool = Form(default=False),
):
    if subject_id is not None and not db.scalar(select(Subject.id).where(Subject.id == subject_id, Subject.owner_id == user.id)):
        raise HTTPException(404, "Subject not found")
    doc = save_upload(db, user.id, file, subject_id)
    if process_now:
        try:
            process_document(db, doc)
            db.refresh(doc)
        except Exception as exc:
            raise HTTPException(422, f"Document uploaded but processing failed: {exc}") from exc
    return doc


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(document_id: int, db: DbSession, user: CurrentUser):
    return owned_document(db, user.id, document_id)


@router.post("/{document_id}/process", response_model=ProcessDocumentResponse)
def process(document_id: int, db: DbSession, user: CurrentUser):
    doc = owned_document(db, user.id, document_id)
    try:
        chunks, embeddings = process_document(db, doc)
    except Exception as exc:
        raise HTTPException(422, str(exc)) from exc
    return ProcessDocumentResponse(document_id=doc.id, status="READY", chunks_created=chunks, embeddings_created=embeddings)


@router.get("/{document_id}/chunks", response_model=list[ChunkOut])
def document_chunks(document_id: int, db: DbSession, user: CurrentUser, limit: int = 200):
    owned_document(db, user.id, document_id)
    return list(
        db.scalars(
            select(DocumentChunk)
            .where(
                DocumentChunk.document_id == document_id,
                DocumentChunk.is_active.is_(True),
            )
            .order_by(DocumentChunk.chunk_index)
            .limit(limit)
        ).all()
    )


@router.delete("/{document_id}", response_model=MessageResponse)
def delete_document(document_id: int, db: DbSession, user: CurrentUser):
    row = owned_document(db, user.id, document_id)
    storage_url = row.storage_url
    db.delete(row); db.commit()
    if storage_url:
        from pathlib import Path
        Path(storage_url).unlink(missing_ok=True)
    return MessageResponse(message="Document deleted")
