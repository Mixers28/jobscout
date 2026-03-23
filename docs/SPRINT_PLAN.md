# JobScout v0.1 Coder Implementation Plan

Version: 1.1
Date: 2026-02-18
Canonical source: `SPEC.md`

## 1. Scope and Goal
This plan converts `SPEC.md` into ticket-sized implementation work for the Coder role, starting with Sprint 0 scaffolding and continuing through Sprint 4.

## 2. Delivery Profile (recommended)
To remove ambiguity and accelerate delivery, this plan assumes:
- Backend/API: FastAPI (Python)
- Web dashboard: Next.js App Router
- Worker: Python worker process with Redis queue semantics
- Database: Postgres + Alembic migrations

If backend stack changes, keep the same sprint outcomes and acceptance criteria.

## 3. Guardrails
- `SPEC.md` remains canonical for behavior and scope.
- Fixed artifact contracts must not change:
  - `SPEC.md`
  - `RUBRIC.md`
  - `BUILD_PLAN.md`
  - `skills_profile.json`
  - `truth_bank.yml`
  - `scoring_weights.yml`
  - `prompt_guardrail.md`
- No auto-submit ATS workflows.
- All generated claims require evidence mapping or `NEEDS_USER_INPUT`.

## 4. Context7 Anchors Used
This plan is grounded in Context7 outputs for:
- FastAPI: APIRouter modularization, `Depends`-based DI, and lifespan startup/shutdown patterns.
- Next.js: App Router server components, server-side `fetch`, and caching/revalidation behavior.

Note:
- Context7 returned a namespace collision for `alembic` (3D graphics Alembic, not DB migrations). Migration steps below are included as implementation assumptions and should be validated against the Python Alembic docs during coding.

## 5. Sprint 0 - Foundations and Scaffolding (1-2 days)

### S0-T1 Repository scaffold and package boundaries
- Create folders:
  - `apps/api`
  - `apps/worker`
  - `apps/web`
  - `packages/shared`
  - `infra`
- Add baseline readmes and placeholder modules.
- Add root task runner entry points (Makefile or npm/pnpm scripts + python commands).

Outputs:
- Folder skeleton committed.
- Local run instructions in `README.md` (or `docs/` if README not yet present).

Tests:
- Smoke import/build checks for each app.

Exit criteria:
- All scaffolded apps boot without runtime errors.

### S0-T2 API bootstrap (FastAPI)
- Implement FastAPI app with lifespan handler for startup/shutdown.
- Add modular router layout:
  - `apps/api/app/main.py`
  - `apps/api/app/routers/health.py`
  - `apps/api/app/dependencies.py`
- Expose `/health` endpoint.

Outputs:
- Running API with health check.

Tests:
- `TestClient` health test returns `200` + expected payload.

Exit criteria:
- `GET /health` stable locally and in CI.

### S0-T3 Database and migrations baseline
- Add DB config and connection management.
- Initialize migration toolchain under `infra/migrations`.
- Create first migration with core tables from `SPEC.md`:
  - `sources`
  - `jobs`
  - `job_matches`
  - `application_packs`
  - `actions`

Outputs:
- Initial schema migration committed.

Tests:
- Fresh DB migration apply test.
- Idempotent migration check on already-upgraded DB.

Exit criteria:
- Migration command applies cleanly in local + CI.

### S0-T4 Worker hello-job and Redis connectivity
- Create worker process entry point in `apps/worker`.
- Implement one smoke task that writes a heartbeat/hello row into DB.
- Wire Redis connection for queueing task execution.

Outputs:
- Worker receives and executes hello-job task.

Tests:
- Integration test enqueues task and verifies DB write.

Exit criteria:
- Worker pipeline is operational end-to-end.

### S0-T5 CI baseline and quality gates
- Add CI workflow (lint + typecheck + unit tests).
- Include migration validation and health endpoint test in CI.

Outputs:
- Passing CI on default branch.

Tests:
- CI workflow run with all checks green.

Exit criteria:
- Every PR must pass lint, typecheck, and tests.

## 6. Sprint 1 - Job Discovery and Normalization (3-5 days)

### S1-T1 Source registry and ingestion contracts
- Implement `sources` config loader and source enable/disable flags.
- Define normalized job DTO/schema shared between worker and API.

Outputs:
- Typed normalization contract in `packages/shared`.

Tests:
- Schema validation tests for valid/invalid source payloads.

Exit criteria:
- All adapters emit the same normalized job shape.

### S1-T2 Email alert ingestion
- Implement email connector (IMAP or provider API abstraction).
- Extract listings and canonical links from alert bodies.

Outputs:
- Email adapter producing normalized jobs.

Tests:
- Fixture-driven parsing tests for common alert formats.

Exit criteria:
- Stable parse for representative LinkedIn/Indeed sample fixtures.

### S1-T3 RSS ingestion
- Implement RSS feed poller + parser.
- Map RSS entries into normalized jobs.

Outputs:
- RSS adapter integrated into worker ingest cycle.

Tests:
- RSS fixture parsing and duplicate GUID handling.

Exit criteria:
- RSS ingest creates normalized jobs with required fields.

### S1-T4 Whitelisted pages ingestion
- Implement page fetcher for allowlisted domains.
- Extract text safely and map job metadata.

Outputs:
- Whitelist page adapter with domain allowlist enforcement.

Tests:
- Domain allowlist tests.
- HTML extraction fallback tests.

Exit criteria:
- Unsupported domains are rejected; supported pages ingest successfully.

### S1-T5 Dedupe and inbox endpoints/UI
- Implement canonical URL normalization and description hash dedupe.
- Add inbox API endpoints (`list`, `mark skip/review/apply`).
- Build minimal inbox page in `apps/web` with filters.

Outputs:
- End-to-end ingest to inbox flow.

Tests:
- Duplicate suppression tests.
- API tests for status transitions.
- Web smoke test for inbox rendering and action buttons.

Exit criteria:
- 50+ jobs/week ingest target is measurable and duplicates are suppressed.

## 7. Sprint 2 - Matching and Scoring Engine (3-5 days)

### S2-T1 Scoring pipeline skeleton
- Build scoring service that reads:
  - `skills_profile.json`
  - `truth_bank.yml`
  - `scoring_weights.yml`
  - `RUBRIC.md`
- Implement hard filters first, then weighted components.

Outputs:
- Deterministic scorer function returning score + breakdown.

Tests:
- Unit tests per scoring component.

Exit criteria:
- Deterministic output for identical input.

### S2-T2 Keyword/synonym and optional embedding hooks
- Implement keyword and synonym matching layer.
- Add embedding similarity interface as optional toggle (no hard dependency).

Outputs:
- Keyword match results included in breakdown.

Tests:
- Synonym normalization tests (`O365` -> `Microsoft 365`, `Intra` -> `Entra ID`).

Exit criteria:
- Optional embeddings can be disabled without changing scoring core.

### S2-T3 Decisioning and explainability
- Compute decision bands (`apply/review/skip`) from thresholds.
- Persist `top_reasons` and `missing_keywords` in `job_matches`.

Outputs:
- Complete `job_matches` persistence pipeline.

Tests:
- Threshold boundary tests.
- Explainability output count tests (5 reasons, 3 missing).

Exit criteria:
- Every scored job has full explainability payload.

### S2-T4 UI score views
- Add score sorting, filters, and explainability panel in web dashboard.

Outputs:
- Score-first review workflow in UI.

Tests:
- UI test for sort order and explanation panel rendering.

Exit criteria:
- User can quickly triage by score and rationale.

## 8. Sprint 3 - Application Pack Generator and Guardrail (4-7 days)

### S3-T1 Pack generation service
- Implement generator service for:
  - `cv_variant_md`
  - `cover_letter_md`
  - `screening_answers_json`
- Scope to Markdown and JSON output (no DOCX/PDF).

Outputs:
- Generator API endpoint and worker task.

Tests:
- Contract tests for generated payload shape.

Exit criteria:
- Pack generation returns all required artifacts.

### S3-T2 Evidence map enforcement
- Implement claim extraction and evidence linking against:
  - `skills_profile.json` evidence lines
  - `truth_bank.yml` field paths
- Build `evidence_map_json` population logic.

Outputs:
- Evidence map persisted with each application pack.

Tests:
- Unsupported claim tests force `NEEDS_USER_INPUT`.
- Evidence path integrity tests.

Exit criteria:
- No claim can pass without evidence reference.

### S3-T3 Guardrail validator integration
- Enforce `prompt_guardrail.md` strict output contract.
- Validate word count for cover letter and evidence refs per claim.

Outputs:
- Validation layer before pack persistence/UI display.

Tests:
- Negative tests for missing evidence refs.
- Validation tests for malformed output payloads.

Exit criteria:
- Invalid payloads are blocked and surfaced as actionable errors.

### S3-T4 Review UI for generated pack
- Build UI to inspect:
  - generated drafts
  - evidence references
  - missing user input prompts

Outputs:
- Human review page for final copy/paste prep.

Tests:
- UI tests for unsupported-field highlighting.

Exit criteria:
- User can identify and resolve all `NEEDS_USER_INPUT` items before submission.

## 9. Sprint 4 - Scheduling, Notifications, Analytics (3-5 days)

### S4-T1 Scheduled runs and reliability
- Add daily scheduler for ingest + score pipeline.
- Add retries, dead-letter handling, and run logs.

Outputs:
- Scheduled background runs with observable status.

Tests:
- Scheduler trigger tests.
- Retry/backoff tests.

Exit criteria:
- Daily run executes reliably with failure visibility.

### S4-T2 Notifications
- Implement top jobs notification channel(s): email and/or Discord.
- Trigger notifications for:
  - Top 5 daily
  - new jobs above score threshold

Outputs:
- Notification sender with templates.

Tests:
- Notification payload formatting tests.
- Threshold trigger tests.

Exit criteria:
- Alerts are delivered for configured events only.

### S4-T3 Application tracking and analytics
- Add tracker fields and transitions:
  - applied date
  - stage
  - reminders
  - outcome
- Implement baseline analytics:
  - score vs callback
  - source conversion rates

Outputs:
- Tracker API + dashboard views.

Tests:
- Stage transition tests.
- Analytics query tests with fixtures.

Exit criteria:
- User can monitor pipeline outcomes and source quality.

## 10. Definition of Done per Ticket
A ticket is done only when all are true:
- Code implemented with tests.
- CI checks pass.
- API/worker/web contracts documented if changed.
- `docs/NOW.md` updated with next action.
- `docs/SESSION_NOTES.md` appended with what changed and why.

## 11. Suggested Execution Order (critical path)
1. S0-T1
2. S0-T2
3. S0-T3
4. S0-T4
5. S0-T5
6. Sprint 1 tickets in order (T1 -> T5)
7. Sprint 2 tickets in order (T1 -> T4)
8. Sprint 3 tickets in order (T1 -> T4)
9. Sprint 4 tickets in order (T1 -> T3)
