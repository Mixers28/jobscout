from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from jobscout_shared.models import Action, Base, Job, JobMatch
from jobscout_shared.settings import Settings
from worker.scheduler.notifications import (
    build_notification_messages,
    collect_notification_candidates,
    mark_jobs_notified,
    send_notifications,
)
from worker.scheduler.pipeline import run_scheduled_cycle


def _session_factory(db_path: Path) -> sessionmaker[Session]:
    engine = create_engine(f"sqlite+pysqlite:///{db_path}", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


def test_run_scheduled_cycle_retries_then_succeeds(tmp_path: Path) -> None:
    db_path = tmp_path / "scheduler_retry.db"
    factory = _session_factory(db_path)
    settings = Settings(
        scheduler_max_retries=2,
        scheduler_backoff_seconds=1,
        notification_top_n=5,
        notification_score_threshold=80.0,
    )

    calls = {"score": 0}
    backoffs: list[float] = []

    def ingest_runner() -> dict:
        return {"jobs_seen": 1, "jobs_inserted": 1}

    def scoring_runner() -> dict:
        calls["score"] += 1
        if calls["score"] == 1:
            raise RuntimeError("transient scoring failure")
        return {"jobs_scored": 1, "apply_count": 1, "review_count": 0, "skip_count": 0}

    result = run_scheduled_cycle(
        session_factory=factory,
        settings=settings,
        trigger="test",
        ingest_runner=ingest_runner,
        scoring_runner=scoring_runner,
        sleep_fn=lambda seconds: backoffs.append(seconds),
    )

    assert result.status == "success"
    assert result.attempts == 2
    assert backoffs == [1.0]

    with factory() as session:
        action_types = session.execute(select(Action.action_type)).scalars().all()
    assert "scheduler.run_retry" in action_types
    assert "scheduler.run_completed" in action_types


def test_run_scheduled_cycle_dead_letter_on_terminal_failure(tmp_path: Path) -> None:
    db_path = tmp_path / "scheduler_dead_letter.db"
    factory = _session_factory(db_path)
    settings = Settings(scheduler_max_retries=1, scheduler_backoff_seconds=0)

    def ingest_runner() -> dict:
        raise RuntimeError("ingest failed")

    result = run_scheduled_cycle(
        session_factory=factory,
        settings=settings,
        trigger="test",
        ingest_runner=ingest_runner,
        scoring_runner=lambda: {"jobs_scored": 0},
        sleep_fn=lambda _seconds: None,
    )

    assert result.status == "failed"
    assert result.attempts == 2
    assert "ingest failed" in (result.error or "")

    with factory() as session:
        action_types = session.execute(select(Action.action_type)).scalars().all()
    assert "scheduler.dead_letter" in action_types


def test_notification_batch_filters_threshold_and_lookback(tmp_path: Path) -> None:
    db_path = tmp_path / "scheduler_notifications.db"
    factory = _session_factory(db_path)

    now = datetime.now(timezone.utc)
    with factory() as session:
        session.add(
            Job(
                id=1,
                title="Top Job",
                company="A",
                location_text="Aberdeen",
                url="https://jobs.example.com/top",
                description_text="test role",
                description_hash="h1",
                fetched_at=now,
            )
        )
        session.add(
            Job(
                id=2,
                title="Older Job",
                company="B",
                location_text="Inverness",
                url="https://jobs.example.com/old",
                description_text="test role",
                description_hash="h2",
                fetched_at=now - timedelta(hours=72),
            )
        )
        session.add(
            JobMatch(
                job_id=1,
                total_score=91.0,
                score_breakdown_json={},
                reasons_json=["strong"],
                missing_json=[],
                decision="apply",
                stage="new",
                outcome="pending",
            )
        )
        session.add(
            JobMatch(
                job_id=2,
                total_score=88.0,
                score_breakdown_json={},
                reasons_json=["strong"],
                missing_json=[],
                decision="apply",
                stage="new",
                outcome="pending",
            )
        )
        session.commit()

    batch = collect_notification_candidates(
        session_factory=factory,
        top_n=5,
        score_threshold=90.0,
        lookback_hours=24,
    )
    assert len(batch.top_jobs) == 2
    assert [candidate.job_id for candidate in batch.new_high_score_jobs] == [1]

    messages = build_notification_messages(batch=batch, score_threshold=90.0)
    assert any(message["event"] == "top_jobs_daily" for message in messages)
    assert any(message["event"] == "new_high_score_jobs" for message in messages)


def test_already_notified_jobs_excluded_from_candidates(tmp_path: Path) -> None:
    """Jobs with notified_at set should not appear in notification candidates."""
    db_path = tmp_path / "scheduler_notified.db"
    factory = _session_factory(db_path)

    now = datetime.now(timezone.utc)
    with factory() as session:
        session.add(
            Job(
                id=1,
                title="Already Notified",
                company="A",
                location_text="London",
                url="https://jobs.example.com/old",
                description_text="test role",
                description_hash="h1",
                fetched_at=now,
            )
        )
        session.add(
            Job(
                id=2,
                title="Brand New",
                company="B",
                location_text="Manchester",
                url="https://jobs.example.com/new",
                description_text="test role",
                description_hash="h2",
                fetched_at=now,
            )
        )
        session.add(
            JobMatch(
                job_id=1,
                total_score=95.0,
                score_breakdown_json={},
                reasons_json=["strong"],
                missing_json=[],
                decision="apply",
                stage="new",
                outcome="pending",
                notified_at=now - timedelta(hours=12),
            )
        )
        session.add(
            JobMatch(
                job_id=2,
                total_score=85.0,
                score_breakdown_json={},
                reasons_json=["good"],
                missing_json=[],
                decision="review",
                stage="new",
                outcome="pending",
            )
        )
        session.commit()

    batch = collect_notification_candidates(
        session_factory=factory,
        top_n=5,
        score_threshold=80.0,
        lookback_hours=24,
    )
    # Only the un-notified job should appear
    assert len(batch.top_jobs) == 1
    assert batch.top_jobs[0].job_id == 2
    assert len(batch.new_high_score_jobs) == 1
    assert batch.new_high_score_jobs[0].job_id == 2


def test_duplicate_rows_with_same_description_hash_collapse_to_one_candidate(tmp_path: Path) -> None:
    db_path = tmp_path / "scheduler_duplicate_rows.db"
    factory = _session_factory(db_path)

    now = datetime.now(timezone.utc)
    with factory() as session:
        session.add(
            Job(
                id=1,
                title="Service desk Analyst L1",
                company="A",
                url="https://www.adzuna.co.uk/jobs/details/5660329908?se=first",
                description_text="same description",
                description_hash="same-hash",
                fetched_at=now,
            )
        )
        session.add(
            Job(
                id=2,
                title="Service desk Analyst L1",
                company="A",
                url="https://www.adzuna.co.uk/jobs/details/5660329908?se=second",
                description_text="same description",
                description_hash="same-hash",
                fetched_at=now - timedelta(minutes=1),
            )
        )
        session.add(
            JobMatch(
                job_id=1,
                total_score=95.0,
                score_breakdown_json={},
                reasons_json=["strong"],
                missing_json=[],
                decision="apply",
                stage="new",
                outcome="pending",
            )
        )
        session.add(
            JobMatch(
                job_id=2,
                total_score=94.0,
                score_breakdown_json={},
                reasons_json=["strong"],
                missing_json=[],
                decision="apply",
                stage="new",
                outcome="pending",
            )
        )
        session.commit()

    batch = collect_notification_candidates(
        session_factory=factory,
        top_n=5,
        score_threshold=80.0,
        lookback_hours=24,
    )

    assert [candidate.job_id for candidate in batch.top_jobs] == [1]
    assert [candidate.job_id for candidate in batch.new_high_score_jobs] == [1]


def test_mark_jobs_notified_stamps_notified_at(tmp_path: Path) -> None:
    """mark_jobs_notified should set notified_at on all jobs in the batch."""
    db_path = tmp_path / "scheduler_mark.db"
    factory = _session_factory(db_path)

    now = datetime.now(timezone.utc)
    with factory() as session:
        session.add(
            Job(
                id=1,
                title="Job A",
                company="A",
                url="https://jobs.example.com/a",
                description_text="test",
                description_hash="ha",
                fetched_at=now,
            )
        )
        session.add(
            JobMatch(
                job_id=1,
                total_score=90.0,
                score_breakdown_json={},
                reasons_json=[],
                missing_json=[],
                decision="apply",
                stage="new",
                outcome="pending",
            )
        )
        session.commit()

    batch = collect_notification_candidates(
        session_factory=factory, top_n=5, score_threshold=80.0, lookback_hours=24
    )
    assert len(batch.top_jobs) == 1

    mark_jobs_notified(session_factory=factory, batch=batch)

    # Second call should return no candidates
    batch2 = collect_notification_candidates(
        session_factory=factory, top_n=5, score_threshold=80.0, lookback_hours=24
    )
    assert len(batch2.top_jobs) == 0
    assert len(batch2.new_high_score_jobs) == 0


def test_mark_jobs_notified_only_stamps_jobs_for_delivered_events(tmp_path: Path) -> None:
    """Jobs only covered by failed events should remain eligible for later notifications."""
    db_path = tmp_path / "scheduler_partial_mark.db"
    factory = _session_factory(db_path)

    now = datetime.now(timezone.utc)
    with factory() as session:
        session.add(
            Job(
                id=1,
                title="Top Job",
                company="A",
                url="https://jobs.example.com/top",
                description_text="test",
                description_hash="htop",
                fetched_at=now,
            )
        )
        session.add(
            Job(
                id=2,
                title="High Score Only",
                company="B",
                url="https://jobs.example.com/high",
                description_text="test",
                description_hash="hhigh",
                fetched_at=now - timedelta(minutes=1),
            )
        )
        session.add(
            JobMatch(
                job_id=1,
                total_score=95.0,
                score_breakdown_json={},
                reasons_json=[],
                missing_json=[],
                decision="apply",
                stage="new",
                outcome="pending",
            )
        )
        session.add(
            JobMatch(
                job_id=2,
                total_score=90.0,
                score_breakdown_json={},
                reasons_json=[],
                missing_json=[],
                decision="review",
                stage="new",
                outcome="pending",
            )
        )
        session.commit()

    batch = collect_notification_candidates(
        session_factory=factory, top_n=1, score_threshold=80.0, lookback_hours=24
    )
    assert [candidate.job_id for candidate in batch.top_jobs] == [1]
    assert [candidate.job_id for candidate in batch.new_high_score_jobs] == [1, 2]

    mark_jobs_notified(
        session_factory=factory,
        batch=batch,
        delivered_events=["top_jobs_daily"],
    )

    batch2 = collect_notification_candidates(
        session_factory=factory, top_n=5, score_threshold=80.0, lookback_hours=24
    )
    assert [candidate.job_id for candidate in batch2.top_jobs] == [2]
    assert [candidate.job_id for candidate in batch2.new_high_score_jobs] == [2]


def test_send_notifications_sent_counter_counts_messages_not_channels() -> None:
    """sent should count messages delivered (≥1 channel ok), not channel successes."""
    settings = Settings(
        discord_webhook_url="https://discord.example.com/webhook",
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_username="user",
        smtp_password="pass",
        smtp_use_tls=True,
        notification_email_from="bot@example.com",
        notification_email_to="user@example.com",
    )
    messages = [
        {"event": "top_jobs_daily", "subject": "Top Jobs", "body": "Job A"},
        {"event": "new_high_score_jobs", "subject": "High Score", "body": "Job B"},
    ]

    with (
        patch(
            "worker.scheduler.notifications.send_discord_webhook",
            return_value=(True, ""),
        ),
        patch(
            "worker.scheduler.notifications.send_email_notification",
            return_value=(True, ""),
        ),
    ):
        summary = send_notifications(settings, messages)

    # 2 messages attempted and both delivered — sent must equal attempted (2), not 4.
    assert summary["attempted"] == 2
    assert summary["sent"] == 2
    assert summary["delivered_events"] == ["top_jobs_daily", "new_high_score_jobs"]
    assert summary["errors"] == []


def test_send_notifications_sent_counter_partial_failure() -> None:
    """sent counts only messages where at least one channel succeeded."""
    settings = Settings(
        discord_webhook_url="https://discord.example.com/webhook",
        smtp_host="",
    )
    messages = [
        {"event": "top_jobs_daily", "subject": "Top Jobs", "body": "Job A"},
        {"event": "new_high_score_jobs", "subject": "High Score", "body": "Job B"},
    ]

    call_count = {"n": 0}

    def discord_side_effect(url: str, content: str, timeout_seconds: int = 8) -> tuple[bool, str]:
        call_count["n"] += 1
        # First message fails, second succeeds.
        if call_count["n"] == 1:
            return False, "webhook timeout"
        return True, ""

    with patch(
        "worker.scheduler.notifications.send_discord_webhook",
        side_effect=discord_side_effect,
    ):
        summary = send_notifications(settings, messages)

    assert summary["attempted"] == 2
    assert summary["sent"] == 1
    assert summary["delivered_events"] == ["new_high_score_jobs"]
    assert len(summary["errors"]) == 1
