"""Shared Pydantic schemas used across API and worker."""

from datetime import datetime
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, model_validator


class HealthResponse(BaseModel):
    status: str
    service: str
    environment: str


class NormalizedJob(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    company: str
    location_text: str = ""
    url: str
    description_text: str
    requirements_text: str | None = None
    contract_type: str | None = None
    work_mode: str | None = None
    uk_region: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    posted_at: datetime | None = None


SourceType = Literal["email_alert", "rss", "whitelist_career_page"]
DecisionType = Literal["skip", "review", "apply"]
PackStatus = Literal["OK", "NEEDS_USER_INPUT"]
TrackingStage = Literal["new", "applied", "screening", "interview", "offer", "closed"]
TrackingOutcome = Literal["pending", "callback", "rejected", "offer", "accepted", "declined"]
SchedulerRunStatus = Literal["success", "failed"]


def _validate_url(value: str, field_name: str) -> None:
    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{field_name} must be a valid http/https URL, got: {value!r}")


class SourceDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    type: SourceType
    enabled: bool = True
    config_json: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_config(self) -> "SourceDefinition":
        cfg = self.config_json or {}
        if self.type == "rss":
            feed_url = str(cfg.get("feed_url", "")).strip()
            if feed_url and not cfg.get("feed_xml"):
                _validate_url(feed_url, "config_json.feed_url")
        elif self.type == "whitelist_career_page":
            for page in cfg.get("pages", []):
                page_url = str(page.get("url", "")).strip()
                if page_url:
                    _validate_url(page_url, "config_json.pages[].url")
            for raw_url in cfg.get("page_urls", []):
                url = str(raw_url).strip()
                if url:
                    _validate_url(url, "config_json.page_urls[]")
        return self


class SourceResponse(BaseModel):
    id: int
    name: str
    type: SourceType
    enabled: bool
    config_json: dict[str, Any]


class IngestionRunResponse(BaseModel):
    sources_processed: int
    jobs_seen: int
    jobs_inserted: int
    jobs_deduped: int


class ScoringRunResponse(BaseModel):
    jobs_scored: int
    apply_count: int
    review_count: int
    skip_count: int


class DecisionUpdateRequest(BaseModel):
    decision: DecisionType


class InboxJob(BaseModel):
    id: int
    title: str
    company: str
    location_text: str | None
    url: str
    fetched_at: datetime
    decision: DecisionType
    total_score: float = 0.0
    top_reasons: list[str] = Field(default_factory=list)
    missing_keywords: list[str] = Field(default_factory=list)
    applied_at: datetime | None = None
    stage: TrackingStage = "new"
    reminder_at: datetime | None = None
    outcome: TrackingOutcome = "pending"


class JobExplainability(BaseModel):
    job_id: int
    total_score: float
    decision: DecisionType
    score_breakdown: dict[str, Any]
    top_reasons: list[str]
    missing_keywords: list[str]


class EvidenceRef(BaseModel):
    source: Literal["skills_profile", "truth_bank"]
    path: str
    quote: str


class ScreeningAnswer(BaseModel):
    question: str
    answer: str
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)


class PackClaim(BaseModel):
    id: str
    text: str
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    supported: bool


class NeedsUserInputItem(BaseModel):
    field: str
    reason: str


class ApplicationPackResponse(BaseModel):
    pack_id: int
    job_id: int
    created_at: datetime
    status: PackStatus
    cv_variant_md: str
    cover_letter_md: str
    screening_answers: list[ScreeningAnswer] = Field(default_factory=list)
    claims: list[PackClaim] = Field(default_factory=list)
    needs_user_input: list[NeedsUserInputItem] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)


class TrackingUpdateRequest(BaseModel):
    stage: TrackingStage | None = None
    outcome: TrackingOutcome | None = None
    applied_at: datetime | None = None
    reminder_at: datetime | None = None


class TrackingResponse(BaseModel):
    job_id: int
    decision: DecisionType
    total_score: float
    applied_at: datetime | None
    stage: TrackingStage
    reminder_at: datetime | None
    outcome: TrackingOutcome


class SchedulerRunResponse(BaseModel):
    run_id: str
    status: SchedulerRunStatus
    attempts: int
    started_at: datetime
    completed_at: datetime
    error: str | None = None
    ingest_summary: dict[str, Any] = Field(default_factory=dict)
    scoring_summary: dict[str, Any] = Field(default_factory=dict)
    notifications: dict[str, Any] = Field(default_factory=dict)


class SourceConversionRate(BaseModel):
    source_id: int | None = None
    source_name: str
    total_jobs: int
    apply_count: int
    callback_count: int
    apply_rate: float
    callback_rate: float


class AnalyticsSummaryResponse(BaseModel):
    total_jobs: int
    applied_jobs: int
    callback_jobs: int
    average_score: float
    average_callback_score: float
    source_conversion_rates: list[SourceConversionRate] = Field(default_factory=list)
