# Project Context - Long-Term Memory (LTM)

> High-level design, constraints, and project decisions.
> This file is the source of truth for context hydration.

<!-- SUMMARY_START -->
**Summary (auto-maintained by Agent):**
- Project is `JobScout Copilot`, focused on safe job ingestion, scoring, and truthful application-pack drafting.
- Canonical contracts are fixed: `SPEC.md`, `RUBRIC.md`, `BUILD_PLAN.md`, `skills_profile.json`, `truth_bank.yml`, `scoring_weights.yml`, `prompt_guardrail.md` / `prompt_guardrail.yml`.
- Human remains in the loop for final submission; no brittle auto-apply automation in v0.1.
- Evidence-backed generation is mandatory: unsupported outputs must return `NEEDS_USER_INPUT`.
- Current implementation status: Sprint 0-4 fully implemented, hardened, and runtime-validated. Gmail IMAP auto-polling live. Scheduler notification dedupe is in place. 46 tests passing.
<!-- SUMMARY_END -->

---

## 1. Project Overview
- **Name:** JobScout Copilot
- **Owner:** Michael Spiegelhoff
- **Purpose:** reduce manual job-hunt workload while keeping outputs truthful and auditable.
- **Primary Stack:** Node.js/TypeScript or Python/FastAPI backend, Next.js frontend, Postgres, Redis worker.
- **Target Market:** North/East Scotland + remote UK roles that do not require London presence.

---

## 2. Core Design Pillars
- Safe-first ingest from approved sources.
- Explainable scoring against explicit rubric and tunable weights.
- Strict evidence guardrails for generated content.
- Human-in-the-loop final submission.
- Context docs are local Markdown and must stay current.

---

## 3. Technical Decisions and Constraints
- Canonical spec: `SPEC.md`.
- Matching behavior reference: `RUBRIC.md`.
- Execution plan reference: `BUILD_PLAN.md`.
- Runtime artifacts use fixed names (no version-suffixed runtime filenames).
- Scoring weights are config-driven in `scoring_weights.yml`.
- `RUBRIC.md` is enforced at runtime by validating scoring config contracts.
- Guardrail contract is enforced at runtime via `prompt_guardrail.md`.
- No auto-submit or CAPTCHA bypass in v0.1.

---

## 4. Memory Hygiene (Drift Guards)
- Keep summary block current and concise.
- Keep `docs/NOW.md` focused on immediate implementation tasks.
- Keep `docs/SESSION_NOTES.md` append-only and relevant to this repo.
- Move stable decisions into this file; keep tactical detail in session notes.

---

## 5. Architecture Snapshot (v0.1)
- Ingestion worker pulls from email alerts (IMAP auto-poll or manual paste), RSS feeds, and whitelisted pages; normalizes and deduplicates jobs.
- Gmail IMAP auto-polling: `fetch_imap_messages()` uses stdlib `imaplib`; `seen_uids` persisted in `source.config_json` to avoid re-processing; system emails filtered.
- URL normalization strips common job-board tracking params so alert variants from Reed/Adzuna/Indeed collapse to one job identity when the underlying listing is the same.
- Matching engine applies hard filters + weighted scoring + explainability fields.
- Pack generator drafts CV/cover/Q&A with evidence map.
- Guardrail contract loaded from `prompt_guardrail.yml` (structured YAML) with `prompt_guardrail.md` markdown fallback.
- Guardrail validator blocks unsupported claims and emits `NEEDS_USER_INPUT` when required.
- Setting a job decision to `apply` auto-generates a fresh application pack for review (with rollback on pack failure).
- Scheduler runs ingest+score with retries/dead-letter logs and optional Discord/SMTP notifications.
- Notification dedupe uses `job_matches.notified_at` so already-delivered jobs are excluded from future candidate selection.
- Scheduler notification candidates also collapse duplicate rows by `description_hash`, which mitigates historical duplicate rows already present in the DB.
- Dashboard shows inbox, scores, tracking status, scheduler run logs, analytics, and generated pack artifacts.
- Ops Console has 6 sections: Quick Add Website, RSS, Email Paste, Auto-Scan IMAP, Run Pipeline, Advanced JSON.
- DB uniqueness constraints on `sources(name, type)` and `jobs(url, description_hash)` enforced at DB and application level.
- API test harness uses async HTTPX ASGI flow for stable local testing in this environment.
- Next.js dev server requires Node ≥20; `make run-web` uses nvm Node 20 automatically.

---

## 6. Links and Related Docs
- `SPEC.md`
- `RUBRIC.md`
- `BUILD_PLAN.md`
- `prompt_guardrail.md`
- `skills_profile.json`
- `truth_bank.yml`
- `scoring_weights.yml`
- `docs/AGENT_SESSION_PROTOCOL.md`
- `docs/INVARIANTS.md`

---

## 7. Change Log (high-level)
- `2026-02-18` - Normalized artifact contracts, replaced stale scanner memory docs, and added strict prompt guardrail + scoring weights config.
- `2026-02-18` - Implemented Sprint 1 ingestion and inbox workflow (source registry, adapters, dedupe, manual decision actions).
- `2026-02-18` - Implemented Sprint 2 scoring workflow (hard filters, weighted scoring, decisioning, explainability endpoints and score-sorted inbox).
- `2026-02-18` - Implemented Sprint 3 core pack workflow (generator + evidence guardrail + pack APIs + review UI).
- `2026-02-18` - Implemented Sprint 4 core workflow (scheduler reliability + notification templates + tracking transitions + analytics endpoints/UI).
- `2026-02-18` - Resolved API test harness deadlock and re-established full green quality gates (`lint`, `typecheck`, `test`).
- `2026-02-19` - Enforced runtime contracts for `RUBRIC.md` and `prompt_guardrail.md`, and enabled automatic pack generation when jobs are marked `apply`.
- `2026-02-19` - Improved ingestion UX with quick-add Website/RSS forms and URL-based source fetching for whitelisted pages and RSS feeds.
- `2026-02-20` - Hardening pass: atomic `update_decision`, `response.ok` checks, DB uniqueness constraints (migration 0003), IntegrityError race handling, YAML guardrail, URL validation, notification counter fix. 39 tests passing.
- `2026-02-20` - Gmail IMAP auto-polling live: `fetch_imap_messages()`, `seen_uids` write-back, system email filter, IMAP settings, `/ops` IMAP form, `make run-web` Node 20 fix.
- `2026-03-23` - Added Discord notification test action in Ops/API flow for quick webhook verification.
- `2026-03-28` - Added `notified_at` tracking (migration `20260326_0004`) so scheduler notifications skip already-notified jobs and only stamp successfully delivered events.
- `2026-03-28` - Fixed duplicate job alert noise by stripping common job-board tracking params during URL canonicalization, discarding obvious non-job redirect pages, and collapsing notification candidates by `description_hash`. 46 tests passing.
