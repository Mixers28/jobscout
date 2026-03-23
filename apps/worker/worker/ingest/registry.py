"""Source registry management helpers."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from jobscout_shared.models import Source
from jobscout_shared.schemas import SourceDefinition


SOURCE_ENABLED_KEY = "enabled"


def upsert_sources(session: Session, source_defs: list[SourceDefinition]) -> list[Source]:
    persisted: list[Source] = []
    for source_def in source_defs:
        source = session.execute(
            select(Source).where(Source.name == source_def.name, Source.type == source_def.type)
        ).scalar_one_or_none()

        merged_config = dict(source_def.config_json)
        merged_config[SOURCE_ENABLED_KEY] = source_def.enabled

        if source is None:
            source = Source(
                name=source_def.name,
                type=source_def.type,
                config_json=merged_config,
            )
            session.add(source)
        else:
            source.config_json = merged_config

        persisted.append(source)

    session.flush()
    return persisted


def is_source_enabled(source: Source) -> bool:
    return bool((source.config_json or {}).get(SOURCE_ENABLED_KEY, True))


def list_enabled_sources(session: Session) -> list[Source]:
    all_sources = session.execute(select(Source).order_by(Source.id.asc())).scalars().all()
    return [source for source in all_sources if is_source_enabled(source)]
