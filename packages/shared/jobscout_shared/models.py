"""Core SQLAlchemy models for JobScout v0.1."""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Source(Base):
    __tablename__ = "sources"
    __table_args__ = (UniqueConstraint("name", "type", name="uq_sources_name_type"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    config_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("url", "description_hash", name="uq_jobs_url_description_hash"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    location_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    uk_region: Mapped[str | None] = mapped_column(String(128), nullable=True)
    work_mode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    salary_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    contract_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    description_text: Mapped[str] = mapped_column(Text, nullable=False)
    description_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    requirements_text: Mapped[str | None] = mapped_column(Text, nullable=True)


class JobMatch(Base):
    __tablename__ = "job_matches"

    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), primary_key=True)
    total_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    score_breakdown_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    reasons_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    missing_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    decision: Mapped[str] = mapped_column(String(16), nullable=False, default="review")
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stage: Mapped[str] = mapped_column(String(32), nullable=False, default="new")
    reminder_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ApplicationPack(Base):
    __tablename__ = "application_packs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    cv_variant_md: Mapped[str] = mapped_column(Text, nullable=False)
    cover_letter_md: Mapped[str] = mapped_column(Text, nullable=False)
    screening_answers_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    evidence_map_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class Action(Base):
    __tablename__ = "actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    actor: Mapped[str] = mapped_column(String(32), nullable=False)
    action_type: Mapped[str] = mapped_column(String(128), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
