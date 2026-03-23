# Repository Guidelines

## Project Structure & Module Organization
`apps/api` contains the FastAPI service and routers, `apps/worker` contains ingest, scoring, pack-generation, and scheduler pipelines, and `apps/web` is the Next.js App Router UI. Shared Python settings, schemas, DB helpers, and models live in `packages/shared/jobscout_shared`. Database migrations are in `infra/migrations`, and tests mirror the app layout under `tests/api`, `tests/worker`, and `tests/infra`.

## Build, Test, and Development Commands
Use the Makefile for the standard Python workflow:

- `make bootstrap`: create `.venv` and install `requirements-dev.txt`
- `make run-api`: start FastAPI with reload
- `make run-worker`: run the worker CLI
- `make run-scheduler-once` / `make run-scheduler-loop`: execute scheduler flows
- `make migrate-up`: apply Alembic migrations
- `make lint`, `make typecheck`, `make test`: run Ruff, mypy, and pytest
- `make docker-up` / `make docker-down`: full stack via Docker Compose

For the web app, work in `apps/web`: `npm run dev`, `npm run build`, `npm run typecheck`.

## Coding Style & Naming Conventions
Target Python 3.11 with 4-space indentation and a 100-character line limit enforced by Ruff. Follow existing Python patterns: `snake_case` for functions/modules, `PascalCase` for classes, and explicit type hints on public functions. In `apps/web`, keep TypeScript components and type aliases in `PascalCase`, route folders in Next.js conventions (`app/ops`, `app/api/...`), and use the existing semicolon-terminated style.

## Testing Guidelines
Place tests under the matching domain folder and name files `test_*.py`. Prefer focused pytest tests that exercise public API routes, worker pipelines, and migration behavior. Run `make test` before opening a PR; when touching the UI, also run `npm run build` or `npm run typecheck` in `apps/web`.

## Commit & Pull Request Guidelines
This checkout does not include `.git`, so project-specific commit history could not be inspected. Use short imperative commit subjects, ideally scoped, for example `api: add inbox filter` or `worker: harden scheduler retry`. PRs should describe behavior changes, list commands run, note schema or env changes, and include screenshots for `apps/web` updates.

## Security & Configuration Tips
Copy `.env.example` to `.env` and keep secrets out of version control. Environment variables use the `JOBSCOUT_` prefix. Treat `RUBRIC.md`, `scoring_weights.yml`, `prompt_guardrail.md`, and `truth_bank.yml` as runtime contract files: update them deliberately and mention any changes in the PR.
