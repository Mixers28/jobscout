"""add uniqueness constraints to sources and jobs

Revision ID: 20260220_0003
Revises: 20260218_0002
Create Date: 2026-02-20
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260220_0003"
down_revision: str | None = "20260218_0002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("sources") as batch_op:
        batch_op.create_unique_constraint("uq_sources_name_type", ["name", "type"])
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.create_unique_constraint("uq_jobs_url_description_hash", ["url", "description_hash"])


def downgrade() -> None:
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.drop_constraint("uq_jobs_url_description_hash", type_="unique")
    with op.batch_alter_table("sources") as batch_op:
        batch_op.drop_constraint("uq_sources_name_type", type_="unique")
