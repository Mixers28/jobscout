from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from jobscout_shared.models import ApplicationPack, Base, Job, JobMatch
from worker.packs.pipeline import generate_application_pack, run_pack_generation


def _session_factory(db_path: Path) -> sessionmaker[Session]:
    engine = create_engine(f"sqlite+pysqlite:///{db_path}", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


def test_run_pack_generation_persists_pack_with_guardrail_payload(tmp_path: Path) -> None:
    db_path = tmp_path / "pack_generation.db"
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
                    "Exchange Online, SharePoint migration, Teams administration, Veeam backup, "
                    "and L3 incident support"
                ),
                description_hash="pack-hash-1",
            )
        )
        session.add(
            JobMatch(
                job_id=1,
                total_score=82.0,
                score_breakdown_json={},
                reasons_json=["Strong match for M365 operations"],
                missing_json=["Azure Backup"],
                decision="apply",
            )
        )
        session.commit()

    result = run_pack_generation(
        session_factory=factory,
        job_id=1,
        skills_profile_path=Path("skills_profile.json"),
        truth_bank_path=Path("truth_bank.yml"),
    )
    assert result.job_id == 1
    assert result.status in {"OK", "NEEDS_USER_INPUT"}

    with factory() as session:
        pack = session.get(ApplicationPack, result.pack_id)
    assert pack is not None
    assert len(pack.cv_variant_md) > 0
    assert len(pack.cover_letter_md.split()) >= 150 or pack.cover_letter_md == "NEEDS_USER_INPUT"

    evidence_map = pack.evidence_map_json
    assert isinstance(evidence_map.get("claims"), list)
    assert isinstance(evidence_map.get("needs_user_input"), list)


def test_generate_application_pack_flags_missing_truth_fields() -> None:
    job = Job(
        id=1,
        title="Infrastructure Engineer",
        company="ExampleCo",
        location_text="Inverness",
        work_mode="hybrid",
        url="https://jobs.example.com/role-2",
        description_text="M365, Teams, Veeam, and incident response",
        description_hash="pack-hash-2",
    )
    skills_profile = {
        "candidate": {"name": "Test User"},
        "core_domains": [
            {
                "skills": [
                    {
                        "skill": "Exchange Online",
                        "keywords": ["exchange online", "m365"],
                        "evidence": ["Managed Exchange Online and tenant administration"],
                    }
                ]
            }
        ],
        "target_roles": ["Infrastructure Engineer"],
    }
    truth_bank = {
        "identity": {"right_to_work_uk": ""},
        "availability": {"notice_period": ""},
        "role_preferences": {"target_titles": ["Infrastructure Engineer"]},
    }

    payload = generate_application_pack(job=job, skills_profile=skills_profile, truth_bank=truth_bank)
    assert payload["status"] == "NEEDS_USER_INPUT"
    assert any(item["field"] == "identity.right_to_work_uk" for item in payload["needs_user_input"])
    assert all(claim["evidence_refs"] for claim in payload["claims"])


def test_run_pack_generation_requires_prompt_guardrail_contract(tmp_path: Path) -> None:
    db_path = tmp_path / "pack_generation_guardrail.db"
    factory = _session_factory(db_path)

    with factory() as session:
        session.add(
            Job(
                title="M365 Infrastructure Engineer",
                company="ExampleCo",
                location_text="Aberdeen",
                work_mode="hybrid",
                url="https://jobs.example.com/role-guardrail",
                description_text="Exchange Online and Teams administration",
                description_hash="pack-hash-guardrail",
            )
        )
        session.commit()

    with pytest.raises(FileNotFoundError):
        run_pack_generation(
            session_factory=factory,
            job_id=1,
            skills_profile_path=Path("skills_profile.json"),
            truth_bank_path=Path("truth_bank.yml"),
            prompt_guardrail_path=tmp_path / "missing_guardrail.md",
        )
