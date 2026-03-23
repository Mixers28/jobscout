"""Health endpoints for readiness and connectivity checks."""

from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy import text

from jobscout_shared.schemas import HealthResponse

router = APIRouter()


@router.get("/")
async def read_root(request: Request) -> dict[str, str]:
    settings = request.app.state.settings
    return {
        "service": "jobscout-api",
        "status": "ok",
        "environment": settings.app_env,
        "health": "/health",
    }


@router.get("/favicon.ico", include_in_schema=False)
async def read_favicon() -> Response:
    return Response(status_code=204)


@router.get("/health", response_model=HealthResponse)
async def read_health(request: Request) -> HealthResponse:
    settings = request.app.state.settings
    return HealthResponse(status="ok", service="jobscout-api", environment=settings.app_env)


@router.get("/health/db")
async def read_db_health(request: Request) -> dict[str, str]:
    engine = request.app.state.engine
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"database unavailable: {exc}") from exc
    return {"status": "ok"}
