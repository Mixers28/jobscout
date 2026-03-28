"""add notified_at to job_matches

Revision ID: 20260326_0004
Revises: 20260220_0003
Create Date: 2026-03-26
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260326_0004"
down_revision: str | None = "20260220_0003"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("job_matches") as batch_op:
        batch_op.add_column(sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("job_matches") as batch_op:
        batch_op.drop_column("notified_at")
