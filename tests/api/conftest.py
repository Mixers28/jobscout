from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest

from app.main import create_app
from jobscout_shared.models import Base
from jobscout_shared.settings import get_settings


@pytest.fixture
async def api_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[httpx.AsyncClient]:
    db_path = tmp_path / "api.db"
    monkeypatch.setenv("JOBSCOUT_DATABASE_URL", f"sqlite+pysqlite:///{db_path}")
    get_settings.cache_clear()

    app = create_app()
    async with app.router.lifespan_context(app):
        Base.metadata.create_all(app.state.engine)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            yield client

    get_settings.cache_clear()
