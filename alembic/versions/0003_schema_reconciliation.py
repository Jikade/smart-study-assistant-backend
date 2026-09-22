"""Reconcile schema drift discovered by fresh-database verification.

Adds the active document-chunk lookup index that exists in the current
database but was not reproducible from revisions 0001 + 0002.

Revision ID: 0003_schema_reconciliation
Revises: 0002_versioned_document_chunks
"""

from __future__ import annotations

from alembic import op


revision = "0003_schema_reconciliation"
down_revision = "0002_versioned_document_chunks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_document_chunks_active_document
        ON public.document_chunks
        USING btree (document_id, is_active, chunk_index)
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP INDEX IF EXISTS public.ix_document_chunks_active_document
        """
    )
