"""Worker CLI entrypoint."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from jobscout_shared.db import make_engine, make_session_factory
from jobscout_shared.schemas import SourceDefinition
from jobscout_shared.settings import get_settings

from .ingest import run_ingest
from .jobs import run_hello_job
from .packs import run_pack_generation
from .queue import RedisQueue
from .scheduler import run_scheduled_cycle, run_scheduler_loop
from .scoring import run_scoring


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="JobScout worker")
    parser.add_argument(
        "--ingest",
        action="store_true",
        help="run one ingestion cycle using registered sources",
    )
    parser.add_argument(
        "--sources-file",
        type=Path,
        default=None,
        help="optional JSON file containing source definitions to upsert before ingest",
    )
    parser.add_argument(
        "--score",
        action="store_true",
        help="run scoring for all ingested jobs",
    )
    parser.add_argument(
        "--use-embeddings",
        action="store_true",
        help="enable optional embedding similarity hook (lexical fallback in v0.1)",
    )
    parser.add_argument(
        "--enqueue",
        action="store_true",
        help="enqueue a hello job payload into Redis instead of running immediately",
    )
    parser.add_argument(
        "--pack",
        action="store_true",
        help="generate and persist an application pack for one job",
    )
    parser.add_argument(
        "--job-id",
        type=int,
        default=None,
        help="job id used by --pack",
    )
    parser.add_argument(
        "--schedule-once",
        action="store_true",
        help="run scheduled ingest+score cycle with retry and notification logic",
    )
    parser.add_argument(
        "--schedule-loop",
        action="store_true",
        help="run scheduler loop (defaults to daily interval from settings)",
    )
    parser.add_argument(
        "--max-runs",
        type=int,
        default=None,
        help="optional max scheduler runs when using --schedule-loop",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    settings = get_settings()

    engine = make_engine(settings.database_url)
    session_factory = make_session_factory(engine)

    try:
        if args.ingest:
            source_defs: list[SourceDefinition] | None = None
            if args.sources_file:
                raw = json.loads(args.sources_file.read_text(encoding="utf-8"))
                source_defs = [SourceDefinition.model_validate(item) for item in raw]
            ingest_summary = run_ingest(session_factory, source_definitions=source_defs)
            print(ingest_summary.model_dump_json())
            return

        if args.score:
            score_summary = run_scoring(
                session_factory=session_factory,
                skills_profile_path=Path(settings.skills_profile_path),
                truth_bank_path=Path(settings.truth_bank_path),
                scoring_weights_path=Path(settings.scoring_weights_path),
                rubric_path=Path(settings.rubric_path),
                use_embeddings=args.use_embeddings,
            )
            print(json.dumps(asdict(score_summary)))
            return

        if args.pack:
            if args.job_id is None:
                raise SystemExit("--pack requires --job-id")
            pack_summary = run_pack_generation(
                session_factory=session_factory,
                job_id=args.job_id,
                skills_profile_path=Path(settings.skills_profile_path),
                truth_bank_path=Path(settings.truth_bank_path),
                prompt_guardrail_path=Path(settings.prompt_guardrail_path),
            )
            print(json.dumps(asdict(pack_summary)))
            return

        if args.schedule_once:
            scheduled = run_scheduled_cycle(
                session_factory=session_factory,
                settings=settings,
                trigger="cli",
            )
            print(json.dumps(asdict(scheduled), default=str))
            return

        if args.schedule_loop:
            if args.max_runs is not None and args.max_runs <= 0:
                raise SystemExit("--max-runs must be greater than zero")
            results = run_scheduler_loop(
                session_factory=session_factory,
                settings=settings,
                trigger="cli_loop",
                max_runs=args.max_runs,
            )
            print(json.dumps([asdict(result) for result in results], default=str))
            return

        if args.enqueue:
            queue = RedisQueue.from_settings(settings)
            queue.ping()
            queue.enqueue({"job": "hello"})
            print("enqueued hello job")
            return

        action_id = run_hello_job(session_factory)
        print(f"hello job wrote action_id={action_id}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
