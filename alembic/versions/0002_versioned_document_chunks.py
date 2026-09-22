"""Add versioned document chunk sets for SSA-SBC.

Revision ID: 0002_versioned_document_chunks
Revises: 0001_baseline
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0002_versioned_document_chunks"
down_revision: Union[str, None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.document_chunks
            ADD COLUMN IF NOT EXISTS chunk_set_id varchar(80)
                NOT NULL DEFAULT 'legacy-v1',
            ADD COLUMN IF NOT EXISTS chunking_algorithm varchar(50)
                NOT NULL DEFAULT 'legacy-v1',
            ADD COLUMN IF NOT EXISTS is_active boolean
                NOT NULL DEFAULT TRUE,
            ADD COLUMN IF NOT EXISTS superseded_at timestamptz;
        """
    )

    op.execute(
        """
        UPDATE public.document_chunks
        SET
            chunk_set_id = COALESCE(chunk_set_id, 'legacy-v1'),
            chunking_algorithm = COALESCE(chunking_algorithm, 'legacy-v1'),
            is_active = COALESCE(is_active, TRUE);
        """
    )

    op.execute(
        """
        ALTER TABLE public.document_chunks
            DROP CONSTRAINT IF EXISTS
            document_chunks_document_id_chunk_index_key;
        """
    )

    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS
            uq_document_chunks_set_index
        ON public.document_chunks
            (document_id, chunk_set_id, chunk_index);
        """
    )

    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS
            uq_document_chunks_active_document_index
        ON public.document_chunks
            (document_id, chunk_index)
        WHERE is_active = TRUE;
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS
            ix_document_chunks_active_section
        ON public.document_chunks
            (document_id, section_id, chunk_index)
        WHERE is_active = TRUE;
        """
    )


def downgrade() -> None:
    raise RuntimeError(
        "Downgrade is intentionally unsupported because "
        "removing versioned chunk history can be lossy."
    )
