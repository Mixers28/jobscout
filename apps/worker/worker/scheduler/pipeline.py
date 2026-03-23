"""Scheduled pipeline execution with retries and run logging."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from sqlalchemy.orm import Session, sessionmaker

from jobscout_shared.models import Action
from jobscout_shared.settings import Settings

from worker.ingest.pipeline import run_ingest
from worker.scoring.pipeline import run_scoring

from .notifications import (
    build_notification_messages,
    collect_notification_candidates,
    send_notifications,
)


@dataclass(slots=True)
class ScheduledRunSummary:
    run_id: str
    status: str
    attempts: int
    started_at: datetime
    completed_at: datetime
    error: str | None
    ingest_summary: dict[str, Any]
    scoring_summary: dict[str, Any]
    notifications: dict[str, Any]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if hasattr(value, "model_dump"):
        return dict(value.model_dump())
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    return {"value": str(value)}


def _log_action(
    session_factory: sessionmaker[Session],
    action_type: str,
    payload: dict[str, Any],
) -> None:
    with session_factory() as session:
        session.add(
            Action(
                actor="system",
                action_type=action_type,
                payload_json=payload,
            )
        )
        session.commit()


def run_scheduled_cycle(
    session_factory: sessionmaker[Session],
    settings: Settings,
    trigger: str = "manual",
    ingest_runner: Callable[[], Any] | None = None,
    scoring_runner: Callable[[], Any] | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> ScheduledRunSummary:
    run_id = str(uuid4())
    started_at = _utc_now()
    max_retries = max(0, settings.scheduler_max_retries)
    ingest_runner = ingest_runner or (lambda: run_ingest(session_factory=session_factory))
    scoring_runner = scoring_runner or (
        lambda: run_scoring(
            session_factory=session_factory,
            skills_profile_path=Path(settings.skills_profile_path),
            truth_bank_path=Path(settings.truth_bank_path),
            scoring_weights_path=Path(settings.scoring_weights_path),
            rubric_path=Path(settings.rubric_path),
            use_embeddings=False,
        )
    )

    last_error: str | None = None
    ingest_summary: dict[str, Any] = {}
    scoring_summary: dict[str, Any] = {}
    notification_summary: dict[str, Any] = {}

    for attempt in range(1, max_retries + 2):
        _log_action(
            session_factory,
            "scheduler.run_started",
            {
                "run_id": run_id,
                "trigger": trigger,
                "attempt": attempt,
                "started_at": _utc_now().isoformat(),
            },
        )
        try:
            ingest_summary = _to_dict(ingest_runner())
            scoring_summary = _to_dict(scoring_runner())
            batch = collect_notification_candidates(
                session_factory=session_factory,
                top_n=settings.notification_top_n,
                score_threshold=settings.notification_score_threshold,
                lookback_hours=settings.notification_lookback_hours,
            )
            messages = build_notification_messages(
                batch=batch,
                score_threshold=settings.notification_score_threshold,
            )
            notification_summary = send_notifications(settings=settings, messages=messages)

            completed_at = _utc_now()
            payload = {
                "run_id": run_id,
                "trigger": trigger,
                "attempts": attempt,
                "status": "success",
                "started_at": started_at.isoformat(),
                "completed_at": completed_at.isoformat(),
                "ingest_summary": ingest_summary,
                "scoring_summary": scoring_summary,
                "notifications": notification_summary,
            }
            _log_action(session_factory, "scheduler.run_completed", payload)
            return ScheduledRunSummary(
                run_id=run_id,
                status="success",
                attempts=attempt,
                started_at=started_at,
                completed_at=completed_at,
                error=None,
                ingest_summary=ingest_summary,
                scoring_summary=scoring_summary,
                notifications=notification_summary,
            )
        except Exception as exc:  # pragma: no cover - exercised via tests with fake runners
            last_error = str(exc)
            _log_action(
                session_factory,
                "scheduler.run_retry",
                {
                    "run_id": run_id,
                    "trigger": trigger,
                    "attempt": attempt,
                    "error": last_error,
                },
            )
            if attempt <= max_retries:
                backoff = max(0, settings.scheduler_backoff_seconds) * (2 ** (attempt - 1))
                if backoff > 0:
                    sleep_fn(float(backoff))
                continue

            completed_at = _utc_now()
            dead_letter_payload = {
                "run_id": run_id,
                "trigger": trigger,
                "attempts": attempt,
                "status": "failed",
                "started_at": started_at.isoformat(),
                "completed_at": completed_at.isoformat(),
                "error": last_error,
            }
            _log_action(session_factory, "scheduler.dead_letter", dead_letter_payload)
            return ScheduledRunSummary(
                run_id=run_id,
                status="failed",
                attempts=attempt,
                started_at=started_at,
                completed_at=completed_at,
                error=last_error,
                ingest_summary=ingest_summary,
                scoring_summary=scoring_summary,
                notifications=notification_summary,
            )

    completed_at = _utc_now()
    return ScheduledRunSummary(
        run_id=run_id,
        status="failed",
        attempts=max_retries + 1,
        started_at=started_at,
        completed_at=completed_at,
        error=last_error or "scheduler exited unexpectedly",
        ingest_summary=ingest_summary,
        scoring_summary=scoring_summary,
        notifications=notification_summary,
    )


def run_scheduler_loop(
    session_factory: sessionmaker[Session],
    settings: Settings,
    trigger: str = "daemon",
    max_runs: int | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> list[ScheduledRunSummary]:
    results: list[ScheduledRunSummary] = []
    interval_seconds = max(1, settings.scheduler_interval_seconds)
    run_count = 0
    while True:
        run_count += 1
        results.append(
            run_scheduled_cycle(
                session_factory=session_factory,
                settings=settings,
                trigger=trigger,
                sleep_fn=sleep_fn,
            )
        )
        if max_runs is not None and run_count >= max_runs:
            break
        sleep_fn(float(interval_seconds))
    return results
