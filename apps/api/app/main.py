"""Application entrypoint for the JobScout API service."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from jobscout_shared.db import make_engine, make_session_factory
from jobscout_shared.settings import get_settings

from .routers import health, jobs, sources


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    engine = make_engine(settings.database_url)
    session_factory = make_session_factory(engine)

    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory

    yield

    engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(title="JobScout API", version="0.1.0", lifespan=lifespan)
    app.include_router(health.router)
    app.include_router(sources.router)
    app.include_router(jobs.router)
    return app


app = create_app()
