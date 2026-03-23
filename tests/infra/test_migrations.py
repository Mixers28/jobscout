from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

REQUIRED_TABLES = {
    "sources",
    "jobs",
    "job_matches",
    "application_packs",
    "actions",
}


def test_alembic_upgrade_head_creates_required_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "migration.db"

    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{db_path}")

    command.upgrade(config, "head")
    command.upgrade(config, "head")

    engine = create_engine(f"sqlite+pysqlite:///{db_path}")
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    assert REQUIRED_TABLES.issubset(table_names)
    job_match_columns = {column["name"] for column in inspector.get_columns("job_matches")}
    assert {"applied_at", "stage", "reminder_at", "outcome"}.issubset(job_match_columns)
