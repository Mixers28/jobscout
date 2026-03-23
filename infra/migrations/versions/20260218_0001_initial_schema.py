"""initial schema

Revision ID: 20260218_0001
Revises:
Create Date: 2026-02-18
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260218_0001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=False),
    )

    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id"), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("company", sa.String(length=255), nullable=False),
        sa.Column("location_text", sa.String(length=255), nullable=True),
        sa.Column("uk_region", sa.String(length=128), nullable=True),
        sa.Column("work_mode", sa.String(length=64), nullable=True),
        sa.Column("salary_min", sa.Float(), nullable=True),
        sa.Column("salary_max", sa.Float(), nullable=True),
        sa.Column("contract_type", sa.String(length=64), nullable=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("description_text", sa.Text(), nullable=False),
        sa.Column("description_hash", sa.String(length=128), nullable=False),
        sa.Column("requirements_text", sa.Text(), nullable=True),
    )

    op.create_table(
        "job_matches",
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), primary_key=True),
        sa.Column("total_score", sa.Float(), nullable=False),
        sa.Column("score_breakdown_json", sa.JSON(), nullable=False),
        sa.Column("reasons_json", sa.JSON(), nullable=False),
        sa.Column("missing_json", sa.JSON(), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=False),
    )

    op.create_table(
        "application_packs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("cv_variant_md", sa.Text(), nullable=False),
        sa.Column("cover_letter_md", sa.Text(), nullable=False),
        sa.Column("screening_answers_json", sa.JSON(), nullable=False),
        sa.Column("evidence_map_json", sa.JSON(), nullable=False),
    )

    op.create_table(
        "actions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("actor", sa.String(length=32), nullable=False),
        sa.Column("action_type", sa.String(length=128), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
    )

    op.create_index("ix_jobs_description_hash", "jobs", ["description_hash"])
    op.create_index("ix_application_packs_job_id", "application_packs", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_application_packs_job_id", table_name="application_packs")
    op.drop_index("ix_jobs_description_hash", table_name="jobs")
    op.drop_table("actions")
    op.drop_table("application_packs")
    op.drop_table("job_matches")
    op.drop_table("jobs")
    op.drop_table("sources")
