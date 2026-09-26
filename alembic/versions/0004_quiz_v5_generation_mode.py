"""Allow deterministic Quiz V5 generation mode.

Revision ID: 0004_quiz_v5_generation_mode
Revises: 0003_schema_reconciliation
"""

from __future__ import annotations

from alembic import op


revision = "0004_quiz_v5_generation_mode"
down_revision = "0003_schema_reconciliation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.quizzes
            DROP CONSTRAINT IF EXISTS
            quizzes_generation_mode_check
        """
    )

    op.execute(
        """
        ALTER TABLE public.quizzes
            ADD CONSTRAINT quizzes_generation_mode_check
            CHECK (
                generation_mode IN (
                    'AI',
                    'MANUAL',
                    'IMPORTED',
                    'FORKED',
                    'V5_DETERMINISTIC'
                )
            )
        """
    )


def downgrade() -> None:
    raise RuntimeError(
        "Downgrade is intentionally unsupported because "
        "existing V5_DETERMINISTIC quizzes would violate "
        "the previous generation_mode constraint."
    )
