# Session Notes - Session Memory (SM)

> Rolling append-only log for this repository.

<!-- SUMMARY_START -->
**Latest Summary (auto-maintained by Agent):**
- 2026-02-20: Gmail IMAP auto-polling live. `fetch_imap_messages()` added to email adapter; `seen_uids` written back after each cycle. System email filter blocks Google housekeeping noise. `/ops` now has 6 sections including email-paste and IMAP auto-scan forms. Next.js startup fixed (Node 20 via nvm). Adzuna scraper junk cleaned. Gmail forwarding from `mixers28@gmail.com` confirmed active.
- 2026-02-20: Full codebase hardening pass: atomicity in `update_decision`, `response.ok` checks, DB uniqueness constraints (migration 0003), IntegrityError handling, YAML guardrail config (`prompt_guardrail.yml`), URL validation, notification counter fix. 39 tests passing.
- 2026-02-19: Enforced runtime contracts for `RUBRIC.md` and `prompt_guardrail.md`, and auto-generated packs when decisions change to `apply`.
- 2026-02-18: Normalized canonical file contracts and replaced stale scanner context docs with JobScout-specific context/hydration docs.
- Implemented Sprint 0-4 core surfaces (scaffolding, ingestion, scoring, pack generation, scheduling, notifications, tracking, analytics).
- Resolved API test harness deadlock and restored full passing quality gates (lint/typecheck/test).
<!-- SUMMARY_END -->

---

## Maintenance Rules
- Append-only entries; do not delete prior sessions.
- Keep entries concise and implementation-focused.
- Keep this file specific to JobScout work.

---

## Session Log

### 2026-02-18 (Web Ops Console for source setup and pipeline control)

**Participants:** User, Codex Agent
**Branch:** main

### What we worked on
- Added a simple operations page at `/ops` to reduce CLI/curl usage for daily workflow.
- Added web route handlers for:
  - source registration (`/api/sources/register`)
  - ingest trigger (`/api/sources/ingest-run`)
  - score trigger (`/api/sources/score-run`)
- Added dashboard shortcut link to open Ops Console.
- Updated README with `/ops` usage and workflow.
- Re-ran full quality checks after UI integration.

### Files touched
- apps/web/app/ops/page.tsx
- apps/web/app/api/sources/register/route.ts
- apps/web/app/api/sources/ingest-run/route.ts
- apps/web/app/api/sources/score-run/route.ts
- apps/web/app/page.tsx
- README.md
- docs/NOW.md
- docs/SESSION_NOTES.md

### Outcomes / Decisions
- Source onboarding and pipeline execution now have a clean web UI path.
- Quality checks remain green (`lint`, `typecheck`, `test`).

### 2026-02-18 (Discord setup + scheduler runtime polish)

**Participants:** User, Codex Agent
**Branch:** main

### What we worked on
- Added `.env.example` with scheduler and notification configuration keys.
- Expanded `README.md` with Discord-first setup steps and scheduler verification commands.
- Added Makefile targets:
  - `run-scheduler-once`
  - `run-scheduler-loop`
- Fixed worker CLI JSON serialization for slotted dataclasses (`--score`, `--pack`, `--schedule-once`, `--schedule-loop`).
- Fixed scheduler summary serialization so `scoring_summary` stays structured JSON.
- Validated scheduler one-shot execution and local quality gates.

### Files touched
- .env.example
- README.md
- Makefile
- apps/worker/worker/main.py
- apps/worker/worker/scheduler/pipeline.py
- docs/NOW.md
- docs/SESSION_NOTES.md

### Outcomes / Decisions
- Discord-first operational path is now documented and runnable.
- `worker.main --schedule-once` now returns structured JSON summary payloads.
- Quality checks remain green after operational updates.

### 2026-02-18 (Sprint 4 validation + API test harness fix)

**Participants:** User, Codex Agent
**Branch:** main

### What we worked on
- Diagnosed API test deadlock to FastAPI sync handler/dependency threadpool execution path in this environment.
- Replaced API tests from `fastapi.testclient.TestClient` to `httpx.AsyncClient + ASGITransport` with explicit lifespan context.
- Converted API router handlers and DB dependency to async to avoid threadpool deadlock path and stabilize local API execution.
- Fixed remaining repo quality gate issues:
  - lint failure in `handoffkit/__main__.py`
  - mypy typing issues in worker queue/ingest adapters
  - mypy import typing for `yaml` in pack pipeline
- Re-ran full local checks: lint, typecheck, and tests.

### Files touched
- tests/api/conftest.py
- tests/api/test_health.py
- tests/api/test_sources_and_inbox.py
- apps/api/app/dependencies.py
- apps/api/app/routers/health.py
- apps/api/app/routers/jobs.py
- apps/api/app/routers/sources.py
- apps/worker/worker/ingest/adapters.py
- apps/worker/worker/queue.py
- apps/worker/worker/packs/pipeline.py
- handoffkit/__main__.py
- docs/NOW.md
- docs/SESSION_NOTES.md

### Outcomes / Decisions
- API tests are now stable and passing under async client flow.
- Full quality gates pass locally:
  - `make lint`: pass
  - `make typecheck`: pass
  - `make test`: pass (`23 passed`)

### 2026-02-18 (Sprint 4 implementation)

**Participants:** User, Codex Agent
**Branch:** main

### What we worked on
- Implemented scheduler reliability pipeline with retries/backoff, dead-letter logging, and action-log observability.
- Added optional notification pipeline (top jobs daily + new high-score jobs) with message templates and optional Discord/SMTP senders.
- Added tracker fields in data model (`applied_at`, `stage`, `reminder_at`, `outcome`) and migration `20260218_0002`.
- Added API endpoints for:
  - scheduler run trigger + run history
  - tracking updates with stage transition validation
  - analytics summary (score vs callback + source conversion rates)
- Extended inbox payload and dashboard UI with tracker fields, analytics panel, and scheduled run visibility.
- Added worker tests for retry/dead-letter/notification filtering and API tests for tracking + analytics + schedule logs.

### Files touched
- infra/migrations/versions/20260218_0002_job_tracking_fields.py
- packages/shared/jobscout_shared/models.py
- packages/shared/jobscout_shared/schemas.py
- packages/shared/jobscout_shared/settings.py
- apps/worker/worker/scheduler/__init__.py
- apps/worker/worker/scheduler/pipeline.py
- apps/worker/worker/scheduler/notifications.py
- apps/worker/worker/main.py
- apps/api/app/routers/jobs.py
- apps/web/app/page.tsx
- apps/web/app/api/tracking/route.ts
- apps/web/app/api/schedule-run/route.ts
- tests/worker/test_scheduler_pipeline.py
- tests/api/test_sources_and_inbox.py
- docs/NOW.md
- docs/SESSION_NOTES.md

### Outcomes / Decisions
- Sprint 4 core code-level outcomes are implemented and validated with focused worker tests.
- `tests/worker/test_scheduler_pipeline.py` passes.
- API pytest execution remains blocked in this environment by a local `fastapi.testclient.TestClient` startup hang, so new API tests were added but not executed end-to-end here.

### 2026-02-18 (Sprint 3 implementation)

**Participants:** User, Codex Agent
**Branch:** main

### What we worked on
- Implemented Sprint 3 worker pack pipeline in `apps/worker/worker/packs/pipeline.py`:
  - generated `cv_variant_md`, `cover_letter_md`, and screening answers.
  - enforced evidence refs for claims and screening answers.
  - added guardrail validation for evidence-path integrity and 150-250 word cover-letter limits.
  - persisted `NEEDS_USER_INPUT` reasons into evidence map output.
- Added worker CLI support for pack generation (`--pack --job-id`).
- Added API endpoints for pack generation/retrieval:
  - `POST /jobs/{job_id}/pack/generate`
  - `GET /jobs/{job_id}/pack`
- Added shared response schemas for application packs and evidence payloads.
- Added web review route `apps/web/app/pack/[jobId]/page.tsx` and linked from inbox.
- Added Sprint 3 tests for worker pack generation and API pack endpoint contracts.

### Files touched
- apps/worker/worker/packs/__init__.py
- apps/worker/worker/packs/pipeline.py
- apps/worker/worker/main.py
- apps/api/app/routers/jobs.py
- apps/api/app/routers/sources.py
- packages/shared/jobscout_shared/schemas.py
- apps/web/app/page.tsx
- apps/web/app/pack/[jobId]/page.tsx
- tests/worker/test_pack_pipeline.py
- tests/api/test_sources_and_inbox.py
- docs/NOW.md
- docs/SESSION_NOTES.md

### Outcomes / Decisions
- Sprint 3 core deliverables are implemented at code level (generator, guardrail, evidence map, API/UI surfaces).
- `tests/worker/test_pack_pipeline.py` passes locally.
- Full API test execution remains blocked by a local `fastapi.testclient.TestClient` startup hang in this environment (hang occurs during `TestClient.__enter__`, independent of Sprint 3 endpoint logic).

### 2026-02-18 (Sprint 2 implementation)

**Participants:** User, Codex Agent
**Branch:** main

### What we worked on
- Implemented Sprint 2 scoring pipeline with hard filters, weighted scoring, region boost, synonym-aware keyword matching, and optional embedding hook.
- Added scoring persistence into `job_matches` (`total_score`, breakdown, top reasons, missing keywords, decision).
- Added scoring API surfaces:
  - `POST /jobs/score/run`
  - `GET /jobs/{job_id}/explain`
  - `GET /jobs/inbox?sort_by=score|fetched_at`
- Extended web inbox to display score, reasons, and missing keywords and default to score sorting.
- Added Sprint 2 tests for scoring pipeline persistence/hard-filter behavior and API score/explainability flow.

### Files touched
- requirements.txt
- packages/shared/jobscout_shared/settings.py
- packages/shared/jobscout_shared/schemas.py
- apps/worker/worker/main.py
- apps/worker/worker/scoring/__init__.py
- apps/worker/worker/scoring/pipeline.py
- apps/api/app/routers/jobs.py
- apps/web/app/page.tsx
- tests/api/test_sources_and_inbox.py
- tests/worker/test_scoring_pipeline.py
- docs/NOW.md
- docs/SESSION_NOTES.md

### Outcomes / Decisions
- Sprint 2 code-level deliverables are complete and compile cleanly.
- Full runtime test execution still requires dependency installation in `.venv` on a network-enabled shell.

### 2026-02-18 (Sprint 1 implementation)

**Participants:** User, Codex Agent
**Branch:** main

### What we worked on
- Implemented source registry contracts and APIs (`register`, `list`, `enabled toggle`) with enable/disable support in source config.
- Implemented worker ingestion adapters for email alerts, RSS feeds, and whitelisted pages, including allowlist enforcement for page sources.
- Implemented canonical URL + description hash dedupe pipeline and persisted normalized jobs to `jobs`.
- Added ingest trigger endpoint and inbox endpoints for listing jobs and manually setting `skip|review|apply` decision.
- Updated web dashboard inbox view to fetch live inbox data with `cache: no-store`, filter by decision, and submit manual decision actions.
- Added Sprint 1 test coverage for adapters, ingest dedupe behavior, source registry, and inbox decision updates.

### Files touched
- packages/shared/jobscout_shared/schemas.py
- packages/shared/jobscout_shared/normalization.py
- apps/worker/worker/main.py
- apps/worker/worker/ingest/__init__.py
- apps/worker/worker/ingest/adapters.py
- apps/worker/worker/ingest/registry.py
- apps/worker/worker/ingest/pipeline.py
- apps/api/app/main.py
- apps/api/app/routers/jobs.py
- apps/api/app/routers/sources.py
- apps/web/app/page.tsx
- apps/web/app/api/decision/route.ts
- tests/api/conftest.py
- tests/api/test_sources_and_inbox.py
- tests/worker/test_ingest_adapters.py
- tests/worker/test_ingest_pipeline.py
- docs/NOW.md
- docs/SESSION_NOTES.md

### Outcomes / Decisions
- Sprint 1 code-level deliverables are implemented and compile cleanly.
- Full runtime/test validation is still blocked in this sandbox until dependencies are installed in `.venv` on a network-enabled shell.

### 2026-02-18 (PEP 668 environment fix)

**Participants:** User, Codex Agent
**Branch:** main

### What we worked on
- Diagnosed package install/runtime failures as PEP 668 externally-managed Python behavior.
- Updated `Makefile` to use `.venv` python/pip and added `make bootstrap`.
- Updated `README.md` quick-start to call `make bootstrap` first.
- Ran bootstrap and verified `.venv` creation; dependency install then failed in this sandbox due no network access to package index.

### Files touched
- Makefile
- README.md
- docs/NOW.md
- docs/SESSION_NOTES.md

### Outcomes / Decisions
- Local workflow is now correct for Debian/Ubuntu PEP 668 systems.
- Remaining failures (`No module named ...`) are caused by dependency download failure, not by Makefile/python-path issues.

### 2026-02-18 (Sprint 0 implementation)

**Participants:** User, Codex Agent
**Branch:** main

### What we worked on
- Executed Sprint 0 from `docs/SPRINT_PLAN.md` with a concrete scaffold across `apps/api`, `apps/worker`, `apps/web`, `packages/shared`, and `infra`.
- Implemented FastAPI app bootstrap with lifespan handling and modular router endpoints (`/health`, `/health/db`) following Context7 FastAPI patterns.
- Added shared SQLAlchemy 2.0 models/settings/db helpers and an Alembic migration baseline for core `SPEC.md` tables.
- Implemented worker hello-job handler that writes to `actions` and Redis queue connectivity hooks (`from_url`, `ping`, enqueue/dequeue).
- Added test baseline (API health, migration apply, worker DB write), Makefile commands, dependency manifests, and GitHub Actions CI workflow.
- Added Next.js App Router scaffold (`app/layout.tsx`, `app/page.tsx`) based on Context7 App Router conventions.

### Files touched
- pyproject.toml
- requirements.txt
- requirements-dev.txt
- Makefile
- .gitignore
- README.md
- alembic.ini
- apps/api/README.md
- apps/api/app/__init__.py
- apps/api/app/main.py
- apps/api/app/dependencies.py
- apps/api/app/routers/__init__.py
- apps/api/app/routers/health.py
- apps/worker/README.md
- apps/worker/worker/__init__.py
- apps/worker/worker/main.py
- apps/worker/worker/jobs.py
- apps/worker/worker/queue.py
- apps/web/README.md
- apps/web/package.json
- apps/web/tsconfig.json
- apps/web/next-env.d.ts
- apps/web/next.config.mjs
- apps/web/app/layout.tsx
- apps/web/app/page.tsx
- packages/shared/README.md
- packages/shared/jobscout_shared/__init__.py
- packages/shared/jobscout_shared/settings.py
- packages/shared/jobscout_shared/db.py
- packages/shared/jobscout_shared/models.py
- packages/shared/jobscout_shared/schemas.py
- infra/README.md
- infra/migrations/README.md
- infra/migrations/env.py
- infra/migrations/script.py.mako
- infra/migrations/versions/20260218_0001_initial_schema.py
- tests/api/test_health.py
- tests/infra/test_migrations.py
- tests/worker/test_hello_job.py
- .github/workflows/ci.yml
- docs/NOW.md
- docs/SESSION_NOTES.md

### Outcomes / Decisions
- Sprint 0 scaffolding and deliverables are implemented at code level.
- Context7 Alembic namespace mismatch remains noted; migration flow is implemented using standard Python Alembic patterns and requires local dependency install for full execution.
- Local test execution is pending dependency install (`pytest` missing in current environment).

### 2026-02-18 (Implementation plan update)

**Participants:** User, Codex Agent
**Branch:** main

### What we worked on
- Built a detailed coder implementation plan from `SPEC.md`, starting with Sprint 0 scaffolding and continuing through Sprint 4.
- Upgraded `docs/SPRINT_PLAN.md` from high-level bullets to ticketized execution units with outputs, tests, and exit criteria.
- Incorporated Context7 guidance for FastAPI router/dependency/lifespan patterns and Next.js App Router data-fetch/caching patterns.
- Documented Context7 Alembic namespace mismatch and marked migration workflow assumptions for in-sprint validation.

### Files touched
- docs/SPRINT_PLAN.md
- docs/NOW.md
- docs/SESSION_NOTES.md

### Outcomes / Decisions
- Sprint execution now has a single coder-ready plan with a critical-path order.
- Recommended delivery profile is FastAPI + Next.js App Router + Redis worker + Postgres migrations.

### 2026-02-18

**Participants:** User, Codex Agent
**Branch:** main

### What we worked on
- Performed repository cleanup pass from review findings.
- Normalized fixed artifact names and updated cross-file references.
- Added missing scoring config artifact and strengthened generation guardrails.
- Replaced stale scanner memory docs with JobScout context, sprint, and workflow documents.

### Files touched
- SPEC.md
- RUBRIC.md
- BUILD_PLAN.md
- prompt_guardrail.md
- scoring_weights.yml
- skills_profile.json
- truth_bank.yml
- docs/PROJECT_CONTEXT.md
- docs/NOW.md
- docs/INVARIANTS.md
- docs/AGENT_SESSION_PROTOCOL.md
- docs/Repo_Structure.md
- docs/SPRINT_PLAN.md
- docs/PERSISTENT_AGENT_WORKFLOW.md
- docs/MCP_LOCAL_DESIGN.md
- docs/SESSION_NOTES.md

### Outcomes / Decisions
- Fixed artifact contracts are now enforced by file naming and references.
- Guardrail behavior now uses a strict JSON contract with evidence refs.
- Hydration docs now match the actual JobScout project scope.

### 2026-02-19 (Runtime contract enforcement + auto-pack on apply)

**Participants:** User, Codex Agent
**Branch:** main

### What we worked on
- Enforced scoring runtime contract against `RUBRIC.md` by parsing rubric thresholds/weights and validating `scoring_weights.yml` before scoring runs.
- Enforced pack runtime contract against `prompt_guardrail.md` by loading guardrail rules (required inputs, evidence path checks, cover-letter bounds) at generation time.
- Updated decision workflow so `POST /jobs/{job_id}/decision` auto-generates a pack when a job transitions to `apply`.
- Propagated new contract paths through settings/env (`JOBSCOUT_RUBRIC_PATH`, `JOBSCOUT_PROMPT_GUARDRAIL_PATH`) and worker/api call sites.
- Added regression tests for rubric drift rejection, guardrail contract requirement, and apply-decision auto-pack behavior.
- Re-ran quality gates and full test suite.

### Files touched
- packages/shared/jobscout_shared/settings.py
- apps/worker/worker/scoring/pipeline.py
- apps/worker/worker/packs/pipeline.py
- apps/worker/worker/main.py
- apps/worker/worker/scheduler/pipeline.py
- apps/api/app/routers/jobs.py
- tests/worker/test_scoring_pipeline.py
- tests/worker/test_pack_pipeline.py
- tests/api/test_sources_and_inbox.py
- .env.example
- README.md
- docs/PROJECT_CONTEXT.md
- docs/NOW.md
- docs/SESSION_NOTES.md

### Outcomes / Decisions
- Runtime now fails fast when scoring config drifts from rubric contract.
- Pack generation now requires and follows `prompt_guardrail.md` contract at runtime.
- Jobs marked `apply` immediately receive a generated application pack for review.
- Local quality gates remain green (`make lint`, `make typecheck`, `make test` -> `25 passed`).

### 2026-02-20 (Gmail IMAP auto-polling + ops improvements)

**Participants:** User, Codex Agent
**Branch:** main

### What we worked on
- Added `fetch_imap_messages()` to `adapters.py` using stdlib `imaplib.IMAP4_SSL` — no new dependencies.
- Added `seen_uids` write-back in `pipeline.py` so previously processed messages are never re-fetched.
- Added system email filter (`_is_system_email`) to block Google security alerts, forwarding confirmations, and welcome emails from being ingested as fake jobs.
- Added `JOBSCOUT_IMAP_*` settings to `settings.py` and `.env.example`.
- Added `/api/sources/register-imap` Next.js API route and section 4 "Auto-Scan Gmail / IMAP Mailbox" form in `/ops` with inline setup instructions.
- Added `/api/sources/register-email` Next.js API route and section 3 "Quick Add Email Alert" paste form in `/ops`.
- Fixed Next.js startup: system Node is v18 (too old); added `make run-web` Makefile target using nvm Node 20 (`~/.nvm/versions/node/v20.*/bin/node`).
- Registered Gmail IMAP source (`jobscout.alerts@gmail.com`) and ran first ingest — 8 emails fetched, all Google setup noise.
- Confirmed Gmail forwarding from `mixers28@gmail.com` active (confirmation link clicked).
- Cleaned up 270 junk jobs generated by Adzuna whitelist scraper (was scraping salary filter nav links); disabled that source.
- Added 5 new IMAP unit tests (all mocked, no network); 39 tests passing.

### Files touched
- apps/worker/worker/ingest/adapters.py
- apps/worker/worker/ingest/pipeline.py
- packages/shared/jobscout_shared/settings.py
- .env.example
- Makefile
- apps/web/app/ops/page.tsx
- apps/web/app/api/sources/register-email/route.ts
- apps/web/app/api/sources/register-imap/route.ts
- tests/worker/test_ingest_pipeline.py
- docs/NOW.md
- docs/SESSION_NOTES.md

### Outcomes / Decisions
- IMAP polling is operational: each ingest cycle fetches unseen emails from Gmail, filters system noise, extracts job URLs, and deduplicates.
- `seen_uids` are persisted in `source.config_json` so emails are never double-processed.
- System emails (Google security/setup/forwarding) are silently skipped; only real job alert emails are ingested.
- Gmail forwarding confirmed — future alerts from `mixers28@gmail.com` will route to `jobscout.alerts@gmail.com` automatically.
- Node 20 required for Next.js; `make run-web` now handles this automatically.
- Quality gates remain green: 39 passed.

### 2026-02-20 (Codebase hardening pass)

**Participants:** User, Codex Agent
**Branch:** main

### What we worked on
- Made `update_decision` in `jobs.py` atomic: pack generation failure rolls back the decision and returns HTTP 500.
- Added `response.ok` checks to all three frontend API routes (`decision`, `tracking`, `schedule-run`).
- Added DB uniqueness constraints: `sources(name, type)` and `jobs(url, description_hash)` via Alembic migration `20260220_0003` (batch mode for SQLite).
- Added `IntegrityError` catch-and-rollback in ingest pipeline for concurrent insert race conditions.
- Replaced brittle markdown-string guardrail parsing with structured YAML (`prompt_guardrail.yml`); markdown fallback retained.
- Added URL validation via Pydantic `model_validator` on `SourceDefinition`; added `http/https` scheme enforcement and 5 MB size cap in adapters.
- Fixed notification `sent` counter to count messages (≥1 channel ok) not raw channel successes.
- Extended tests in `test_sources_and_inbox.py`, `test_ingest_pipeline.py`, `test_scheduler_pipeline.py`.

### Files touched
- apps/api/app/routers/jobs.py
- apps/web/app/api/decision/route.ts
- apps/web/app/api/tracking/route.ts
- apps/web/app/api/schedule-run/route.ts
- packages/shared/jobscout_shared/models.py
- packages/shared/jobscout_shared/schemas.py
- infra/migrations/versions/20260220_0003_uniqueness_constraints.py
- apps/worker/worker/ingest/pipeline.py
- apps/worker/worker/ingest/adapters.py
- apps/worker/worker/packs/pipeline.py
- apps/worker/worker/scheduler/notifications.py
- prompt_guardrail.yml
- tests/api/test_sources_and_inbox.py
- tests/worker/test_ingest_pipeline.py
- tests/worker/test_scheduler_pipeline.py

### Outcomes / Decisions
- Decision rollback on pack failure prevents partial state in DB.
- DB constraints enforce data integrity at the database level.
- Structured YAML guardrail is more robust than regex-parsing markdown.
- All 39 tests passing after hardening.

### 2026-02-19 (User-friendly source ingestion UX)

**Participants:** User, Codex Agent
**Branch:** main

### What we worked on
- Reworked `/ops` source onboarding to be form-first instead of JSON-first.
- Added quick-add forms for:
  - Website sources (careers page URL + allowed domain)
  - RSS sources (feed URL)
- Kept advanced JSON registration as an optional fallback.
- Added web route handlers for form-based source registration:
  - `/api/sources/register-site`
  - `/api/sources/register-rss`
- Extended ingestion adapters to support URL-based fetching:
  - RSS supports `feed_url` when `feed_xml` is not provided.
  - Whitelist pages support `page_urls` and fetch HTML at ingest time when inline HTML is not provided.
- Added adapter tests for URL-based RSS/page ingestion paths and re-ran quality checks.

### Files touched
- apps/web/app/ops/page.tsx
- apps/web/app/api/sources/register-site/route.ts
- apps/web/app/api/sources/register-rss/route.ts
- apps/worker/worker/ingest/adapters.py
- tests/worker/test_ingest_adapters.py
- README.md
- docs/NOW.md
- docs/SESSION_NOTES.md

### Outcomes / Decisions
- Source registration for day-to-day use no longer requires users to craft raw JSON or paste HTML/XML.
- Ingestion pipeline now supports more realistic URL-driven source configs while preserving existing test/config compatibility.
- Quality gates remain green (`make lint`, `make typecheck`, `make test` -> `27 passed`).
