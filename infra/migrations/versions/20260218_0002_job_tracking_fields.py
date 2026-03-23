"""add job tracking fields

Revision ID: 20260218_0002
Revises: 20260218_0001
Create Date: 2026-02-18
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260218_0002"
down_revision: str | None = "20260218_0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("job_matches", sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "job_matches",
        sa.Column(
            "stage",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'new'"),
        ),
    )
    op.add_column("job_matches", sa.Column("reminder_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "job_matches",
        sa.Column(
            "outcome",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("job_matches", "outcome")
    op.drop_column("job_matches", "reminder_at")
    op.drop_column("job_matches", "stage")
    op.drop_column("job_matches", "applied_at")
