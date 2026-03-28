# JobScout Copilot v0.1

Job ingestion, scoring, application pack generation, scheduler reliability, and notifications.

Runtime contracts:
- Scoring enforces `RUBRIC.md` against `scoring_weights.yml` at run time.
- Pack generation enforces `prompt_guardrail.md` at run time.
- Marking a job `apply` auto-generates a fresh application pack.

## Quick start (Docker — recommended)

Requires [Docker Desktop](https://www.docker.com/products/docker-desktop/) or Docker Engine + Compose v2.

```bash
cp .env.example .env
# Optional: fill in IMAP / Discord / SMTP values in .env
docker compose up --build
```

- Dashboard: http://localhost:3001
- Ops Console: http://localhost:3001/ops
- API: http://localhost:8001

All services (Postgres, Redis, API, worker scheduler, web UI) start automatically.
The API container runs database migrations on first boot.

Useful commands:
```bash
make docker-down    # stop and remove containers
make docker-logs    # tail all container logs
make docker-up      # rebuild and restart in background
```

## Coolify deployment (Git-backed Docker Compose)

For a local Coolify machine, use this repository as a Git-backed `Docker Compose` application.

1. Put this project in a Git repository and push it to a provider Coolify can access.
2. In Coolify, create a new `Application`.
3. Select the repository and choose the `Docker Compose` build pack.
4. Point Coolify at `docker-compose.coolify.yml` in the repository root.
5. Expose the `web` service publicly and keep `api`, `worker`, `postgres`, and `redis` internal.
6. Add environment variables from `.env.example`, especially:
   - `JOBSCOUT_DATABASE_URL=postgresql+psycopg://jobscout:jobscout@postgres:5432/jobscout`
   - `JOBSCOUT_REDIS_URL=redis://redis:6379/0`
   - any `JOBSCOUT_IMAP_*`, Discord, or SMTP secrets you want enabled

Notes:
- The web container now runs a production Next.js build and reaches the API over the internal Docker network using `API_BASE_URL=http://api:8000`.
- Use `docker-compose.coolify.yml` in Coolify to avoid host-port conflicts on the server. Keep `docker-compose.yml` for direct local Docker use on your workstation.
- See `COOLIFY.md` for the full deployment checklist.

## Quick start (local / without Docker)
0. Create a local env file:
   - `cp .env.example .env`
1. Create virtual environment and install dependencies:
   - `make bootstrap`
2. Run migrations:
   - `make migrate-up`
3. Start API:
   - `make run-api`
4. Run worker hello job:
   - `make run-worker`
5. Run quality checks:
   - `make lint`
   - `make typecheck`
   - `make test`

## Sprint 4 operations
### Discord-first notifications (recommended)
1. Set your webhook in `.env`:
   - `JOBSCOUT_DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...`
2. Run one scheduled cycle:
   - `PYTHONPATH=packages/shared:apps/api:apps/worker .venv/bin/python -m worker.main --schedule-once`
3. Verify run visibility:
   - `GET /jobs/schedule/runs`
   - dashboard scheduled runs panel
   - or open `http://127.0.0.1:3001/ops` in Docker mode, or `http://127.0.0.1:3000/ops` with `make run-web`

Notes:
- Notifications are only sent when candidates match rules:
  - top jobs daily (top `JOBSCOUT_NOTIFICATION_TOP_N`)
  - new jobs above `JOBSCOUT_NOTIFICATION_SCORE_THRESHOLD` within `JOBSCOUT_NOTIFICATION_LOOKBACK_HOURS`
- Once a job has been delivered successfully, scheduler notifications stamp `job_matches.notified_at` and skip it on future runs.
- Ingest normalization strips common job-board tracking params so Reed/Adzuna/Indeed alert variants collapse to one stored job when the underlying listing is the same.
- If no webhook is set, scheduler still runs ingest + scoring + logs, but skips Discord delivery.

### Optional scheduler loop
- Run loop mode (daily by default from `.env`):
  - `PYTHONPATH=packages/shared:apps/api:apps/worker .venv/bin/python -m worker.main --schedule-loop`
- Run bounded loop for smoke:
  - `PYTHONPATH=packages/shared:apps/api:apps/worker .venv/bin/python -m worker.main --schedule-loop --max-runs 1`

## Web Ops UI
- Open: `http://127.0.0.1:3001/ops` in Docker mode, or `http://127.0.0.1:3000/ops` with `make run-web`
- Use it to:
  - quick-add website sources with careers page URL + allowed domain
  - quick-add RSS sources with feed URL
  - register sources from JSON (advanced mode)
  - run ingest
  - run scoring
  - run one scheduled cycle
  - inspect configured sources and recent run logs

## Structure
- `apps/api` FastAPI service
- `apps/worker` worker process and queue hooks
- `apps/web` Next.js App Router scaffold
- `packages/shared` shared Python settings/models/schemas
- `infra/migrations` Alembic migration scripts
