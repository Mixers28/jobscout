"""Inbox, scoring, and decision endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from jobscout_shared.models import Action, ApplicationPack, Job, JobMatch, Source
from jobscout_shared.schemas import (
    AnalyticsSummaryResponse,
    ApplicationPackResponse,
    DecisionType,
    DecisionUpdateRequest,
    InboxJob,
    JobExplainability,
    NeedsUserInputItem,
    PackClaim,
    SchedulerRunResponse,
    SourceConversionRate,
    TrackingOutcome,
    TrackingResponse,
    TrackingStage,
    TrackingUpdateRequest,
    ScoringRunResponse,
    ScreeningAnswer,
)

from ..dependencies import get_db_session
from worker.packs.pipeline import get_latest_application_pack, run_pack_generation
from worker.scheduler import run_scheduled_cycle
from worker.scoring.pipeline import run_scoring

router = APIRouter(prefix="/jobs", tags=["jobs"])


class ScoreRunRequest(BaseModel):
    use_embeddings: bool = False


ALLOWED_STAGE_TRANSITIONS: dict[str, set[str]] = {
    "new": {"new", "applied", "closed"},
    "applied": {"applied", "screening", "interview", "closed"},
    "screening": {"screening", "interview", "closed"},
    "interview": {"interview", "offer", "closed"},
    "offer": {"offer", "closed"},
    "closed": {"closed"},
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso_datetime(value: str | None, fallback: datetime) -> datetime:
    if not value:
        return fallback
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return fallback


def _is_valid_stage_transition(current_stage: str, next_stage: str) -> bool:
    allowed = ALLOWED_STAGE_TRANSITIONS.get(current_stage, {"new"})
    return next_stage in allowed


def _tracking_response_from_match(match: JobMatch) -> TrackingResponse:
    return TrackingResponse(
        job_id=match.job_id,
        decision=cast(DecisionType, match.decision),
        total_score=float(match.total_score or 0.0),
        applied_at=match.applied_at,
        stage=cast(TrackingStage, match.stage),
        reminder_at=match.reminder_at,
        outcome=cast(TrackingOutcome, match.outcome),
    )


def _ensure_job_match(db: Session, job_id: int) -> JobMatch:
    match = db.get(JobMatch, job_id)
    if match is not None:
        return match
    match = JobMatch(
        job_id=job_id,
        total_score=0.0,
        score_breakdown_json={},
        reasons_json=[],
        missing_json=[],
        decision="review",
        stage="new",
        outcome="pending",
    )
    db.add(match)
    return match


def _as_screening_answers(pack: ApplicationPack) -> list[ScreeningAnswer]:
    raw = pack.screening_answers_json or {}
    if isinstance(raw, dict):
        answers = raw.get("screening_answers", [])
        if isinstance(answers, list):
            return [
                ScreeningAnswer.model_validate(item)
                for item in answers
                if isinstance(item, dict)
            ]
        return []
    if isinstance(raw, list):
        return [ScreeningAnswer.model_validate(item) for item in raw if isinstance(item, dict)]
    return []


def _as_pack_response(pack: ApplicationPack) -> ApplicationPackResponse:
    evidence_map = pack.evidence_map_json or {}
    claims = evidence_map.get("claims", []) if isinstance(evidence_map, dict) else []
    needs = evidence_map.get("needs_user_input", []) if isinstance(evidence_map, dict) else []
    missing = evidence_map.get("missing_requirements", []) if isinstance(evidence_map, dict) else []
    status: Literal["OK", "NEEDS_USER_INPUT"] = "OK"
    if isinstance(evidence_map, dict) and evidence_map.get("status") == "NEEDS_USER_INPUT":
        status = "NEEDS_USER_INPUT"
    if needs:
        status = "NEEDS_USER_INPUT"

    parsed_claims: list[PackClaim] = []
    if isinstance(claims, list):
        parsed_claims = [PackClaim.model_validate(item) for item in claims if isinstance(item, dict)]

    parsed_needs: list[NeedsUserInputItem] = []
    if isinstance(needs, list):
        parsed_needs = [
            NeedsUserInputItem.model_validate(item)
            for item in needs
            if isinstance(item, dict)
        ]

    return ApplicationPackResponse(
        pack_id=pack.id,
        job_id=pack.job_id,
        created_at=pack.created_at,
        status=status,
        cv_variant_md=pack.cv_variant_md,
        cover_letter_md=pack.cover_letter_md,
        screening_answers=_as_screening_answers(pack),
        claims=parsed_claims,
        needs_user_input=parsed_needs,
        missing_requirements=missing if isinstance(missing, list) else [],
    )


@router.get("/inbox", response_model=list[InboxJob])
async def read_inbox(
    decision: DecisionType | None = Query(default=None),
    sort_by: Literal["fetched_at", "score"] = Query(default="fetched_at"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db_session),
) -> list[InboxJob]:
    decision_expr = func.coalesce(JobMatch.decision, "review")
    score_expr = func.coalesce(JobMatch.total_score, 0.0)
    stage_expr = func.coalesce(JobMatch.stage, "new")
    outcome_expr = func.coalesce(JobMatch.outcome, "pending")

    stmt = (
        select(
            Job.id,
            Job.title,
            Job.company,
            Job.location_text,
            Job.url,
            Job.fetched_at,
            decision_expr.label("decision"),
            score_expr.label("total_score"),
            JobMatch.applied_at,
            stage_expr.label("stage"),
            JobMatch.reminder_at,
            outcome_expr.label("outcome"),
            JobMatch.reasons_json,
            JobMatch.missing_json,
        )
        .select_from(Job)
        .outerjoin(JobMatch, JobMatch.job_id == Job.id)
        .limit(limit)
        .offset(offset)
    )

    if decision is not None:
        stmt = stmt.where(decision_expr == decision)

    if sort_by == "score":
        stmt = stmt.order_by(score_expr.desc(), Job.fetched_at.desc(), Job.id.desc())
    else:
        stmt = stmt.order_by(Job.fetched_at.desc(), Job.id.desc())

    rows = db.execute(stmt).all()
    return [
        InboxJob(
            id=row.id,
            title=row.title,
            company=row.company,
            location_text=row.location_text,
            url=row.url,
            fetched_at=row.fetched_at,
            decision=row.decision,
            total_score=float(row.total_score or 0.0),
            top_reasons=(row.reasons_json or [])[:5],
            missing_keywords=(row.missing_json or [])[:3],
            applied_at=row.applied_at,
            stage=cast(TrackingStage, row.stage),
            reminder_at=row.reminder_at,
            outcome=cast(TrackingOutcome, row.outcome),
        )
        for row in rows
    ]


@router.post("/score/run", response_model=ScoringRunResponse)
async def run_score_job_matches(
    request: Request,
    payload: ScoreRunRequest | None = None,
) -> ScoringRunResponse:
    settings = request.app.state.settings
    session_factory = request.app.state.session_factory

    summary = run_scoring(
        session_factory=session_factory,
        skills_profile_path=Path(settings.skills_profile_path),
        truth_bank_path=Path(settings.truth_bank_path),
        scoring_weights_path=Path(settings.scoring_weights_path),
        rubric_path=Path(settings.rubric_path),
        use_embeddings=(payload.use_embeddings if payload else False),
    )

    return ScoringRunResponse(
        jobs_scored=summary.jobs_scored,
        apply_count=summary.apply_count,
        review_count=summary.review_count,
        skip_count=summary.skip_count,
    )


@router.post("/schedule/run", response_model=SchedulerRunResponse)
async def trigger_scheduled_run(request: Request) -> SchedulerRunResponse:
    settings = request.app.state.settings
    session_factory = request.app.state.session_factory
    result = run_scheduled_cycle(
        session_factory=session_factory,
        settings=settings,
        trigger="api",
    )
    return SchedulerRunResponse(
        run_id=result.run_id,
        status=cast(Literal["success", "failed"], result.status),
        attempts=result.attempts,
        started_at=result.started_at,
        completed_at=result.completed_at,
        error=result.error,
        ingest_summary=result.ingest_summary,
        scoring_summary=result.scoring_summary,
        notifications=result.notifications,
    )


@router.get("/schedule/runs", response_model=list[SchedulerRunResponse])
async def read_scheduled_runs(
    limit: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db_session),
) -> list[SchedulerRunResponse]:
    stmt = (
        select(Action)
        .where(Action.action_type.in_(["scheduler.run_completed", "scheduler.dead_letter"]))
        .order_by(Action.timestamp.desc(), Action.id.desc())
        .limit(limit)
    )
    actions = db.execute(stmt).scalars().all()

    runs: list[SchedulerRunResponse] = []
    for action in actions:
        payload = action.payload_json or {}
        status: Literal["success", "failed"] = (
            "failed" if action.action_type == "scheduler.dead_letter" else "success"
        )
        runs.append(
            SchedulerRunResponse(
                run_id=str(payload.get("run_id", f"action-{action.id}")),
                status=status,
                attempts=int(payload.get("attempts", payload.get("attempt", 1))),
                started_at=_parse_iso_datetime(str(payload.get("started_at", "")), action.timestamp),
                completed_at=_parse_iso_datetime(str(payload.get("completed_at", "")), action.timestamp),
                error=(str(payload.get("error", "")) or None),
                ingest_summary=payload.get("ingest_summary", {}) if isinstance(payload, dict) else {},
                scoring_summary=payload.get("scoring_summary", {}) if isinstance(payload, dict) else {},
                notifications=payload.get("notifications", {}) if isinstance(payload, dict) else {},
            )
        )
    return runs


@router.get("/analytics/summary", response_model=AnalyticsSummaryResponse)
async def read_analytics_summary(db: Session = Depends(get_db_session)) -> AnalyticsSummaryResponse:
    stmt = (
        select(
            Job.id,
            Job.source_id,
            Source.name,
            JobMatch.total_score,
            JobMatch.decision,
            JobMatch.outcome,
            JobMatch.applied_at,
        )
        .select_from(Job)
        .outerjoin(JobMatch, JobMatch.job_id == Job.id)
        .outerjoin(Source, Source.id == Job.source_id)
    )
    rows = db.execute(stmt).all()

    total_jobs = len(rows)
    scores = [float(row.total_score) for row in rows if row.total_score is not None]
    average_score = round(sum(scores) / len(scores), 2) if scores else 0.0

    applied_jobs = 0
    callback_jobs = 0
    callback_scores: list[float] = []
    by_source: dict[tuple[int | None, str], dict[str, float]] = {}
    callback_outcomes = {"callback", "offer", "accepted"}

    for row in rows:
        source_key = (row.source_id, str(row.name or "unknown"))
        if source_key not in by_source:
            by_source[source_key] = {
                "total_jobs": 0,
                "apply_count": 0,
                "callback_count": 0,
            }
        by_source[source_key]["total_jobs"] += 1

        is_apply = (row.decision == "apply") or (row.applied_at is not None)
        if is_apply:
            applied_jobs += 1
            by_source[source_key]["apply_count"] += 1

        is_callback = str(row.outcome or "").lower() in callback_outcomes
        if is_callback:
            callback_jobs += 1
            by_source[source_key]["callback_count"] += 1
            if row.total_score is not None:
                callback_scores.append(float(row.total_score))

    source_conversion_rates: list[SourceConversionRate] = []
    for (source_id, source_name), stats in by_source.items():
        total = int(stats["total_jobs"])
        apply_count = int(stats["apply_count"])
        callback_count = int(stats["callback_count"])
        apply_rate = round((apply_count / total) * 100.0, 2) if total else 0.0
        callback_rate = round((callback_count / total) * 100.0, 2) if total else 0.0
        source_conversion_rates.append(
            SourceConversionRate(
                source_id=source_id,
                source_name=source_name,
                total_jobs=total,
                apply_count=apply_count,
                callback_count=callback_count,
                apply_rate=apply_rate,
                callback_rate=callback_rate,
            )
        )
    source_conversion_rates.sort(key=lambda item: item.apply_rate, reverse=True)

    average_callback_score = (
        round(sum(callback_scores) / len(callback_scores), 2) if callback_scores else 0.0
    )
    return AnalyticsSummaryResponse(
        total_jobs=total_jobs,
        applied_jobs=applied_jobs,
        callback_jobs=callback_jobs,
        average_score=average_score,
        average_callback_score=average_callback_score,
        source_conversion_rates=source_conversion_rates,
    )


@router.post("/{job_id}/pack/generate", response_model=ApplicationPackResponse)
async def generate_job_pack(
    job_id: int,
    request: Request,
) -> ApplicationPackResponse:
    settings = request.app.state.settings
    session_factory = request.app.state.session_factory
    try:
        run_pack_generation(
            session_factory=session_factory,
            job_id=job_id,
            skills_profile_path=Path(settings.skills_profile_path),
            truth_bank_path=Path(settings.truth_bank_path),
            prompt_guardrail_path=Path(settings.prompt_guardrail_path),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="job not found") from exc

    with session_factory() as session:
        pack = get_latest_application_pack(session, job_id)
        if pack is None:
            raise HTTPException(status_code=500, detail="application pack generation failed")
        return _as_pack_response(pack)


@router.get("/{job_id}/pack", response_model=ApplicationPackResponse)
async def read_latest_job_pack(
    job_id: int,
    db: Session = Depends(get_db_session),
) -> ApplicationPackResponse:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")

    pack = get_latest_application_pack(db, job_id)
    if pack is None:
        raise HTTPException(status_code=404, detail="application pack not found")
    return _as_pack_response(pack)


@router.get("/{job_id}/explain", response_model=JobExplainability)
async def get_job_explainability(
    job_id: int,
    db: Session = Depends(get_db_session),
) -> JobExplainability:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")

    match = db.get(JobMatch, job_id)
    if match is None:
        return JobExplainability(
            job_id=job_id,
            total_score=0.0,
            decision="review",
            score_breakdown={},
            top_reasons=[],
            missing_keywords=[],
        )

    return JobExplainability(
        job_id=job_id,
        total_score=float(match.total_score or 0.0),
        decision=cast(DecisionType, match.decision),
        score_breakdown=match.score_breakdown_json or {},
        top_reasons=(match.reasons_json or [])[:5],
        missing_keywords=(match.missing_json or [])[:3],
    )


@router.post("/{job_id}/decision", response_model=InboxJob)
async def update_decision(
    job_id: int,
    payload: DecisionUpdateRequest,
    request: Request,
    db: Session = Depends(get_db_session),
) -> InboxJob:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")

    match = _ensure_job_match(db, job_id)
    previous_decision = cast(DecisionType, match.decision)
    match.decision = payload.decision
    needs_pack = payload.decision == "apply" and previous_decision != "apply"
    if payload.decision == "apply" and match.stage == "new":
        match.stage = "applied"
        if match.applied_at is None:
            match.applied_at = _utc_now()

    db.commit()
    db.refresh(match)

    if needs_pack:
        settings = request.app.state.settings
        session_factory = request.app.state.session_factory
        try:
            run_pack_generation(
                session_factory=session_factory,
                job_id=job_id,
                skills_profile_path=Path(settings.skills_profile_path),
                truth_bank_path=Path(settings.truth_bank_path),
                prompt_guardrail_path=Path(settings.prompt_guardrail_path),
            )
        except Exception as exc:
            # Pack failed: rollback the decision change so API state stays consistent.
            match.decision = previous_decision
            if previous_decision != "apply":
                match.stage = "new"
                match.applied_at = None
            db.commit()
            raise HTTPException(
                status_code=500,
                detail=f"pack generation failed; decision rolled back: {exc}",
            ) from exc

    db.refresh(match)
    return InboxJob(
        id=job.id,
        title=job.title,
        company=job.company,
        location_text=job.location_text,
        url=job.url,
        fetched_at=job.fetched_at,
        decision=cast(DecisionType, match.decision),
        total_score=float(match.total_score or 0.0),
        top_reasons=(match.reasons_json or [])[:5],
        missing_keywords=(match.missing_json or [])[:3],
        applied_at=match.applied_at,
        stage=cast(TrackingStage, match.stage),
        reminder_at=match.reminder_at,
        outcome=cast(TrackingOutcome, match.outcome),
    )


@router.patch("/{job_id}/tracking", response_model=TrackingResponse)
async def update_tracking(
    job_id: int,
    payload: TrackingUpdateRequest,
    db: Session = Depends(get_db_session),
) -> TrackingResponse:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")

    match = _ensure_job_match(db, job_id)
    current_stage = str(match.stage or "new")
    next_stage = payload.stage or cast(TrackingStage, current_stage)

    if payload.stage is not None and not _is_valid_stage_transition(current_stage, payload.stage):
        raise HTTPException(
            status_code=400,
            detail=f"invalid stage transition: {current_stage} -> {payload.stage}",
        )

    match.stage = next_stage
    if payload.outcome is not None:
        match.outcome = payload.outcome
    if payload.applied_at is not None:
        match.applied_at = payload.applied_at
    if payload.reminder_at is not None:
        match.reminder_at = payload.reminder_at
    if next_stage == "applied" and match.applied_at is None:
        match.applied_at = _utc_now()

    db.commit()
    db.refresh(match)
    return _tracking_response_from_match(match)
