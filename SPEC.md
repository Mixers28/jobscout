# JobScout Copilot v0.1

## Objective
Reduce the manual work of job hunting by:
- Ingesting jobs from safe sources (alerts + whitelisted pages)
- Scoring jobs against a fixed skills profile and rubric
- Generating an application pack (tailored CV bullets + cover letter + screening Q&A drafts)
- Enforcing evidence-backed claims only (no guessing)

## Non-goals (v0.1)
- Fully automated click-to-apply flows across ATS websites
- CAPTCHA bypassing or restricted-platform scraping
- Auto-answering questions that are not backed by `truth_bank.yml` or `skills_profile.json`

## Target Roles (initial)
- Microsoft 365 / O365 Engineer
- Infrastructure Engineer (M365/backup-heavy)
- Senior IT Support / L3 (M365 + projects)
- Systems Administrator (hybrid/migrations)

## Operating Region
North/East Scotland focus (Aberdeen / Inverness / Dundee + hybrid/onsite) and remote UK roles that do not require London presence.

## Assumed Stack
- Hosting: Railway
- DB: Postgres
- Cache/queue: Redis + worker
- Backend: Node.js (TypeScript) or Python (FastAPI)
- Frontend: Next.js (or equivalent)
- LLM: pluggable provider (OpenAI API or local Ollama)

## Fixed Artifact Contracts (required)
These names are fixed and must be treated as canonical inputs:
- `SPEC.md`
- `RUBRIC.md`
- `BUILD_PLAN.md`
- `skills_profile.json`
- `truth_bank.yml`
- `scoring_weights.yml`
- `prompt_guardrail.md`

## Data Model (v0.1)
### Core tables
- `sources`: `id`, `name`, `type (email_alert|rss|whitelist_career_page)`, `config_json`
- `jobs`: `id`, `source_id`, `title`, `company`, `location_text`, `uk_region`, `work_mode`, `salary_min`, `salary_max`, `contract_type`, `url`, `posted_at`, `fetched_at`, `description_text`, `description_hash`, `requirements_text`
- `job_matches`: `job_id`, `total_score`, `score_breakdown_json`, `reasons_json`, `missing_json`, `decision (skip|review|apply)`
- `application_packs`: `job_id`, `created_at`, `cv_variant_md`, `cover_letter_md`, `screening_answers_json`, `evidence_map_json`
- `actions` (audit trail): `timestamp`, `actor (system|user)`, `action_type`, `payload_json`

## Sprints (v0.1)
### Sprint 0 - Repo + foundations (1-2 days)
Deliverables:
- Monorepo layout:
  - `/apps/web`
  - `/apps/api`
  - `/apps/worker`
  - `/packages/shared`
  - `/infra`
  - `/docs`
- CI: lint + typecheck + unit tests
- Postgres migrations + Redis connection

Acceptance criteria:
- API health endpoint exists
- DB migrations apply cleanly
- Worker can run a hello-job and write to DB

### Sprint 1 - Job discovery + normalization (3-5 days)
Ingestion sources (safe-first):
- Email alerts (Gmail/Outlook via IMAP or API)
- RSS feeds
- Whitelisted employer pages

Pipeline:
- Fetch -> extract text -> normalize into `jobs` record -> dedupe by `description_hash` + canonical URL

UI:
- Inbox list: new deduped jobs with link-out

Acceptance criteria:
- Ingest 50+ jobs/week from alerts without duplicates
- Each job includes `title/company/location/url/description_text`
- Manual mark `skip|review|apply`

### Sprint 2 - Matching + scoring engine (3-5 days)
Inputs:
- `skills_profile.json`
- `truth_bank.yml`
- `scoring_weights.yml`
- `RUBRIC.md`

Scoring components:
- Hard filters (location/work mode/role family)
- Keyword + synonym match
- Optional embeddings similarity

Outputs:
- `job_matches` with total score, breakdown, top reasons, missing keywords

UI:
- Sort by score
- Explainability panel (why score was assigned)

Acceptance criteria:
- For each job: score + 5 reasons + 3 missing items
- Weight changes require no code changes

### Sprint 3 - Application pack generator (4-7 days)
Generate:
- Tailored CV variant (v0.1 Markdown)
- Cover letter (UK style, 150-250 words)
- Screening Q&A drafts

Evidence guardrail:
- Every generated claim must map to a `truth_bank.yml` field or `skills_profile.json` evidence line
- If unsupported, output `NEEDS_USER_INPUT`
- Guardrail behavior is defined in `prompt_guardrail.md`

Acceptance criteria:
- Generate pack returns CV variant + cover letter + Q&A JSON + evidence map
- Unsupported claims are flagged, not fabricated

### Sprint 4 - Scheduling, notifications, analytics (3-5 days)
Automation:
- Daily scheduled ingest + scoring
- Notifications for Top 5 and high-score new jobs

Tracking:
- Application tracker (`applied_date`, stage, reminders, outcome)
- Basic analytics (score vs callback, source conversion)

Acceptance criteria:
- Daily run is observable (logs + retries)
- Run status and failures are visible in UI/logs
