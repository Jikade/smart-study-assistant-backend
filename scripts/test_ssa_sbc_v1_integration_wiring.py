from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(path: Path, needle: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert needle in text, f"{label} missing in {path}"


def main():
    models = ROOT / "app/db/models.py"
    document_service = ROOT / "app/services/document_service.py"
    rag_service = ROOT / "app/services/rag_service.py"
    flashcard_service = ROOT / "app/services/flashcard_service.py"
    quiz_service = ROOT / "app/services/quiz_service.py"
    documents_router = ROOT / "app/api/v1/routers/documents.py"

    for needle in (
        "chunk_set_id = mapped_column(",
        "chunking_algorithm = mapped_column(",
        "is_active = mapped_column(",
        "superseded_at = mapped_column(",
    ):
        require(models, needle, needle)

    for needle in (
        "SSA_SBC_VERSION",
        "structural_chunk_text(",
        "chunk_set_id = (",
        "is_active=False",
        "Atomic chunk-set switch validation failed",
    ):
        require(document_service, needle, needle)

    require(
        rag_service,
        "WHERE dc.is_active = TRUE",
        "RAG active-only",
    )
    require(
        flashcard_service,
        "DocumentChunk.is_active.is_(",
        "Flashcard active-only",
    )
    require(
        quiz_service,
        "DocumentChunk.is_active.is_(",
        "Quiz active-only",
    )
    require(
        documents_router,
        "DocumentChunk.is_active.is_(",
        "Document API active-only",
    )

    document_text = document_service.read_text(
        encoding="utf-8"
    )
    assert (
        "db.execute(delete(DocumentChunk).where("
        "DocumentChunk.document_id == doc.id))"
        not in document_text
    ), "Destructive legacy delete is still present"

    print()
    print("=" * 72)
    print("SSA-SBC-V1 INTEGRATION WIRING TEST")
    print("=" * 72)
    print("ORM versioning fields:", True)
    print("Versioned build wired:", True)
    print("Atomic active-set switch wired:", True)
    print("RAG active-only:", True)
    print("Quiz active-only:", True)
    print("Flashcards active-only:", True)
    print("Document chunks API active-only:", True)
    print("Destructive legacy delete removed:", True)
    print("Result: PASS")
    print("=" * 72)


if __name__ == "__main__":
    main()
