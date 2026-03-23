"""End-to-end ingestion pipeline with dedupe and persistence."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from jobscout_shared.models import Job, Source
from jobscout_shared.normalization import canonicalize_url, compute_description_hash
from jobscout_shared.schemas import IngestionRunResponse, NormalizedJob, SourceDefinition

from .adapters import parse_email_alert_jobs, parse_rss_jobs, parse_whitelist_page_jobs
from .registry import list_enabled_sources, upsert_sources


def _adapt_source(source: Source) -> tuple[list[NormalizedJob], int, list[str]]:
    config = source.config_json or {}

    if source.type == "email_alert":
        result = parse_email_alert_jobs(source.name, config)
    elif source.type == "rss":
        result = parse_rss_jobs(source.name, config)
    elif source.type == "whitelist_career_page":
        result = parse_whitelist_page_jobs(source.name, config)
    else:
        return [], 0, []

    return result.jobs, result.seen, result.fetched_uids


def _persist_job(session: Session, source: Source, normalized_job: NormalizedJob) -> bool:
    canonical_url = canonicalize_url(normalized_job.url)
    description_hash = compute_description_hash(normalized_job.description_text)

    existing = session.execute(
        select(Job.id).where(Job.url == canonical_url, Job.description_hash == description_hash)
    ).scalar_one_or_none()

    if existing is not None:
        return False

    session.add(
        Job(
            source_id=source.id,
            title=normalized_job.title,
            company=normalized_job.company,
            location_text=normalized_job.location_text,
            uk_region=normalized_job.uk_region,
            work_mode=normalized_job.work_mode,
            salary_min=normalized_job.salary_min,
            salary_max=normalized_job.salary_max,
            contract_type=normalized_job.contract_type,
            url=canonical_url,
            posted_at=normalized_job.posted_at,
            description_text=normalized_job.description_text,
            description_hash=description_hash,
            requirements_text=normalized_job.requirements_text,
        )
    )
    return True


def run_ingest(
    session_factory: sessionmaker[Session],
    source_definitions: list[SourceDefinition] | None = None,
) -> IngestionRunResponse:
    jobs_seen = 0
    jobs_inserted = 0
    sources_processed = 0

    with session_factory() as session:
        if source_definitions:
            upsert_sources(session, source_definitions)
            session.commit()

        sources = list_enabled_sources(session)

        for source in sources:
            sources_processed += 1
            jobs, _seen, fetched_uids = _adapt_source(source)
            jobs_seen += len(jobs)
            for normalized_job in jobs:
                try:
                    inserted = _persist_job(session, source, normalized_job)
                    if inserted:
                        session.flush()
                        jobs_inserted += 1
                except IntegrityError:
                    # Concurrent insert beat us to it — treat as dedupe, not error.
                    session.rollback()

            # Persist IMAP UIDs so the next poll skips already-processed messages.
            if fetched_uids:
                existing_uids: list[str] = list((source.config_json or {}).get("seen_uids", []))
                source.config_json = {
                    **(source.config_json or {}),
                    "seen_uids": existing_uids + fetched_uids,
                }
                session.flush()

        session.commit()

    jobs_deduped = max(jobs_seen - jobs_inserted, 0)
    return IngestionRunResponse(
        sources_processed=sources_processed,
        jobs_seen=jobs_seen,
        jobs_inserted=jobs_inserted,
        jobs_deduped=jobs_deduped,
    )
