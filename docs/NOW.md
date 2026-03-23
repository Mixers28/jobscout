# NOW - Working Memory (WM)

> This file tracks current focus and next executable tasks.

<!-- SUMMARY_START -->
**Current Focus (auto-maintained by Agent):**
- Gmail IMAP polling is live: job-alert emails are fetched automatically on every ingest cycle.
- Email forwarding from `mixers28@gmail.com` → `jobscout.alerts@gmail.com` is confirmed and active.
- System email noise (Google security alerts, welcome emails) is filtered before ingest.
- Ops Console now has 6 sections: Quick Add Website, RSS, Email Paste, Auto-Scan IMAP, Run Pipeline, Advanced JSON.
- Next.js dev server requires Node 20 (`make run-web` now uses nvm Node 20 automatically).
- All 39 tests passing. DB is clean (270 Adzuna scraper junk jobs removed, scraper disabled).
- Waiting for first real job-alert emails to arrive from Reed/Adzuna/LinkedIn saved searches.
<!-- SUMMARY_END -->

---

## Current Objective
Receive and process first real job alert emails; validate end-to-end ingest → score → inbox workflow with live data.

---

## Active Branch
- `main`

---

## What We Are Working On Right Now
- [x] Normalize file contracts (`SPEC.md`, `RUBRIC.md`, `BUILD_PLAN.md`, `skills_profile.json`, `truth_bank.yml`, `prompt_guardrail.md`).
- [x] Add `scoring_weights.yml` and align with rubric thresholds.
- [x] Update hydration docs from legacy scanner context to JobScout context.
- [x] Expand `docs/SPRINT_PLAN.md` into coder-ready implementation tickets across all sprints.
- [x] Create monorepo app/package folders from Sprint 0.
- [x] Add lint/typecheck/unit-test CI baseline.
- [x] Add first DB migration and worker hello-job path.
- [x] Update Makefile/README to use `.venv` and `make bootstrap`.
- [x] Implement Sprint 1 source registry and ingestion adapters.
- [x] Implement Sprint 1 dedupe + inbox API + manual decision update flow.
- [x] Implement Sprint 2 scoring pipeline and `job_matches` persistence.
- [x] Implement Sprint 2 score sorting + explainability API and UI integration.
- [x] Implement Sprint 3 pack generator worker pipeline (`cv_variant_md`, `cover_letter_md`, `screening_answers_json`).
- [x] Implement Sprint 3 evidence map + guardrail validator and `NEEDS_USER_INPUT` handling.
- [x] Implement Sprint 3 API pack routes and pack review UI page.
- [x] Add Sprint 3 worker/API tests for pack contracts and evidence refs.
- [x] Implement Sprint 4 scheduler/retry/dead-letter pipeline with run logging.
- [x] Implement Sprint 4 notification candidate selection and sender templates (Discord/SMTP optional config).
- [x] Implement Sprint 4 tracking fields + transitions and analytics API.
- [x] Implement Sprint 4 dashboard views for run logs/analytics/tracking updates.
- [x] Add Sprint 4 worker and API tests for reliability, thresholds, transitions, and analytics.
- [x] Resolve local API test harness deadlock and migrate tests to async client flow.
- [x] Run `make lint`, `make typecheck`, and `make test` successfully.
- [x] Add Discord-first operational setup (`.env.example`, README run instructions, scheduler make targets).
- [x] Validate `--schedule-once` runtime path and JSON summaries.
- [x] Add web Ops Console for source registration and one-click ingest/score/schedule actions.
- [x] Enforce scoring runtime contract against `RUBRIC.md`.
- [x] Enforce pack runtime contract against `prompt_guardrail.md`.
- [x] Auto-generate application packs when decision changes to `apply`.
- [x] Add and pass regression tests for rubric/guardrail enforcement and auto-pack behavior.
- [x] Make source ingestion UX user-friendly in `/ops` (quick-add Website/RSS/Email-paste/IMAP forms).
- [x] Support URL-based RSS and whitelisted-page ingestion without requiring pasted feed XML or page HTML.
- [x] Harden codebase: atomicity in `update_decision`, `response.ok` checks in frontend routes, DB uniqueness constraints, migration 0003, IntegrityError handling, YAML guardrail config, URL validation in schemas/adapters, notification counter fix. (39 tests passing)
- [x] Add email alert paste form to `/ops` (section 3) with API route `/api/sources/register-email`.
- [x] Add Gmail IMAP auto-scan source (section 4) with `fetch_imap_messages()` adapter, `seen_uids` write-back, and `/api/sources/register-imap` API route.
- [x] Add IMAP settings (`JOBSCOUT_IMAP_*`) to `settings.py` and `.env.example`.
- [x] Filter system/housekeeping emails (Google alerts, forwarding confirmations) from ingest.
- [x] Fix Next.js startup: `make run-web` target uses nvm Node 20 to satisfy Next.js >=20.9.0 requirement.
- [x] Clean up 270 Adzuna scraper junk jobs; disable Adzuna whitelist source (was scraping nav links, not jobs).
- [x] Confirm Gmail forwarding from `mixers28@gmail.com` active.

---

## Next Small Deliverables
- Subscribe to job alerts on Reed, Adzuna, LinkedIn, CWJobs using `mixers28@gmail.com` as notification address.
- Wait for first forwarded alert emails; run ingest and confirm real jobs appear in the dashboard.
- Configure `JOBSCOUT_DISCORD_WEBHOOK_URL` in `.env` to enable daily Discord notifications.
- Run one full end-to-end workflow: ingest → score → auto-pack on apply → tracking update → analytics review.

---

## Drift Guards
- Keep NOW to active tasks only.
- Update NOW + SESSION_NOTES after each significant step.
- Reflect only stable decisions in `PROJECT_CONTEXT.md`.
