"""Source registry and ingestion endpoints."""

from __future__ import annotations

from typing import cast

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from jobscout_shared.models import Source
from jobscout_shared.schemas import IngestionRunResponse, SourceDefinition, SourceResponse, SourceType
from worker.ingest.pipeline import run_ingest
from worker.ingest.registry import is_source_enabled, upsert_sources

from ..dependencies import get_db_session

router = APIRouter(prefix="/sources", tags=["sources"])


class SourceEnabledUpdateRequest(BaseModel):
    enabled: bool


def _source_to_response(source: Source) -> SourceResponse:
    return SourceResponse(
        id=source.id,
        name=source.name,
        type=cast(SourceType, source.type),
        enabled=is_source_enabled(source),
        config_json=source.config_json or {},
    )


@router.post("/register", response_model=list[SourceResponse])
async def register_sources(
    sources: list[SourceDefinition],
    db: Session = Depends(get_db_session),
) -> list[SourceResponse]:
    persisted = upsert_sources(db, sources)
    db.commit()
    return [_source_to_response(source) for source in persisted]


@router.get("", response_model=list[SourceResponse])
async def list_sources(
    enabled_only: bool = Query(default=False),
    db: Session = Depends(get_db_session),
) -> list[SourceResponse]:
    sources = db.execute(select(Source).order_by(Source.id.asc())).scalars().all()
    if enabled_only:
        sources = [source for source in sources if is_source_enabled(source)]
    return [_source_to_response(source) for source in sources]


@router.patch("/{source_id}/enabled", response_model=SourceResponse)
async def set_source_enabled(
    source_id: int,
    payload: SourceEnabledUpdateRequest,
    db: Session = Depends(get_db_session),
) -> SourceResponse:
    source = db.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="source not found")

    config = dict(source.config_json or {})
    config["enabled"] = payload.enabled
    source.config_json = config

    db.commit()
    db.refresh(source)
    return _source_to_response(source)


@router.post("/ingest/run", response_model=IngestionRunResponse)
async def run_ingestion(
    request: Request,
    sources: list[SourceDefinition] | None = None,
) -> IngestionRunResponse:
    session_factory = request.app.state.session_factory
    return run_ingest(session_factory=session_factory, source_definitions=sources)
