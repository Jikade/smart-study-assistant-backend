from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import select

from app.db.models import Document, DocumentSection
from app.db.session import SessionLocal
from app.services.document_service import clean_text, extract_text
from app.services.structural_chunker import (
    SSA_SBC_VERSION,
    structural_chunk_text,
)


def main():
    document_id = int(sys.argv[1]) if len(sys.argv) > 1 else 2

    with SessionLocal() as db:
        doc = db.get(Document, document_id)
        if doc is None:
            raise SystemExit(
                f"Document {document_id} not found"
            )

        sections = list(
            db.scalars(
                select(DocumentSection)
                .where(
                    DocumentSection.document_id == document_id
                )
                .order_by(
                    DocumentSection.section_order,
                    DocumentSection.id,
                )
            ).all()
        )

        raw, _ = extract_text(
            Path(doc.storage_url),
            doc.file_extension or "",
        )
        cleaned = clean_text(raw)

        chunks = structural_chunk_text(
            cleaned,
            sections=sections,
        )

        print()
        print("=" * 88)
        print(
            f"SSA-SBC-V1 PREVIEW | document={document_id} "
            f"| chunks={len(chunks)}"
        )
        print("=" * 88)

        for index, chunk in enumerate(chunks):
            heading = chunk.structural_heading or "<PREAMBLE>"
            preview_text = (
                chunk.content[:180]
                .replace("\n", " ")
            )

            print(
                f"[{index:03d}] "
                f"block={chunk.block_index} "
                f"section={chunk.section_id} "
                f"chars={len(chunk.content)} "
                f"heading={heading!r}"
            )
            print("      " + preview_text)

        print("=" * 88)
        print("Algorithm:", SSA_SBC_VERSION)


if __name__ == "__main__":
    main()
