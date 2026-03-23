from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from jobscout_shared.models import Action, Base
from worker.jobs import run_hello_job


def _session_factory(db_path: Path) -> sessionmaker[Session]:
    engine = create_engine(f"sqlite+pysqlite:///{db_path}", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


def test_hello_job_writes_action_record(tmp_path: Path) -> None:
    db_path = tmp_path / "worker.db"
    factory = _session_factory(db_path)

    action_id = run_hello_job(factory)

    with factory() as session:
        action = session.execute(select(Action).where(Action.id == action_id)).scalar_one()

    assert action.actor == "system"
    assert action.action_type == "worker.hello_job"
    assert action.payload_json["message"] == "hello-job"
