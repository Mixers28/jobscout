"""FastAPI dependencies for database access and settings."""

from collections.abc import AsyncGenerator

from fastapi import Request
from sqlalchemy.orm import Session

from jobscout_shared.settings import Settings, get_settings


def get_app_settings() -> Settings:
    return get_settings()


async def get_db_session(request: Request) -> AsyncGenerator[Session, None]:
    session_factory = request.app.state.session_factory
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
