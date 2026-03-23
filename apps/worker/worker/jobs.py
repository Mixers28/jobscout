"""Worker job handlers."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session, sessionmaker

from jobscout_shared.models import Action


def run_hello_job(session_factory: sessionmaker[Session]) -> int:
    with session_factory() as session:
        action = Action(
            actor="system",
            action_type="worker.hello_job",
            payload_json={
                "message": "hello-job",
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        session.add(action)
        session.commit()
        session.refresh(action)
        return action.id
