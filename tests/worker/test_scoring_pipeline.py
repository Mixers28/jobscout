from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from jobscout_shared.models import Base, Job, JobMatch
from worker.scoring.pipeline import run_scoring


def _session_factory(db_path: Path) -> sessionmaker[Session]:
    engine = create_engine(f"sqlite+pysqlite:///{db_path}", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


def test_run_scoring_persists_job_match(tmp_path: Path) -> None:
    db_path = tmp_path / "score.db"
    factory = _session_factory(db_path)

    with factory() as session:
        session.add(
            Job(
                title="M365 Infrastructure Engineer",
                company="ExampleCo",
                location_text="Aberdeen",
                work_mode="hybrid",
                url="https://jobs.example.com/role-1",
                description_text=(
                    "Microsoft 365, Exchange Online, SharePoint migration, Veeam, Azure Backup, "
                    "L3 support, incident ownership"
                ),
                description_hash="hash-1",
            )
        )
        session.commit()

    summary = run_scoring(
        session_factory=factory,
        skills_profile_path=Path("skills_profile.json"),
        truth_bank_path=Path("truth_bank.yml"),
        scoring_weights_path=Path("scoring_weights.yml"),
        use_embeddings=False,
    )

    assert summary.jobs_scored == 1

    with factory() as session:
        match = session.get(JobMatch, 1)

    assert match is not None
    assert match.total_score >= 0
    assert match.decision in {"skip", "review", "apply"}
    assert len(match.reasons_json) <= 5
    assert len(match.missing_json) <= 3


def test_hard_filter_role_family_sets_skip(tmp_path: Path) -> None:
    db_path = tmp_path / "score_hard_filter.db"
    factory = _session_factory(db_path)

    with factory() as session:
        session.add(
            Job(
                title="Senior Software Engineer",
                company="DevCo",
                location_text="London",
                work_mode="onsite",
                url="https://jobs.example.com/role-2",
                description_text="Onsite backend software engineer role requiring full stack delivery",
                description_hash="hash-2",
            )
        )
        session.commit()

    run_scoring(
        session_factory=factory,
        skills_profile_path=Path("skills_profile.json"),
        truth_bank_path=Path("truth_bank.yml"),
        scoring_weights_path=Path("scoring_weights.yml"),
        use_embeddings=False,
    )

    with factory() as session:
        match = session.get(JobMatch, 1)

    assert match is not None
    assert match.decision == "skip"
    assert match.score_breakdown_json["hard_filters"]["triggered"] is True


def test_run_scoring_rejects_weights_that_drift_from_rubric(tmp_path: Path) -> None:
    db_path = tmp_path / "score_rubric_contract.db"
    factory = _session_factory(db_path)

    with factory() as session:
        session.add(
            Job(
                title="M365 Engineer",
                company="ExampleCo",
                location_text="Aberdeen",
                work_mode="hybrid",
                url="https://jobs.example.com/role-3",
                description_text="Exchange Online and SharePoint role",
                description_hash="hash-3",
            )
        )
        session.commit()

    drifted_weights = tmp_path / "scoring_weights_drift.yml"
    source = Path("scoring_weights.yml").read_text(encoding="utf-8")
    drifted_weights.write_text(source.replace("min: 80", "min: 70", 1), encoding="utf-8")

    with pytest.raises(ValueError, match="RUBRIC.md"):
        run_scoring(
            session_factory=factory,
            skills_profile_path=Path("skills_profile.json"),
            truth_bank_path=Path("truth_bank.yml"),
            scoring_weights_path=drifted_weights,
            use_embeddings=False,
        )
