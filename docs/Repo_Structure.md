JobScout/
├── .github/
│   └── workflows/
│       └── ci.yml
├── .vscode/
│   ├── settings.json
│   └── tasks.json
├── apps/
│   ├── api/
│   │   ├── README.md
│   │   └── app/
│   │       ├── main.py
│   │       ├── dependencies.py
│   │       └── routers/
│   │           ├── health.py
│   │           ├── jobs.py
│   │           └── sources.py
│   ├── web/
│   │   ├── README.md
│   │   ├── package.json
│   │   └── app/
│   │       ├── layout.tsx
│   │       ├── page.tsx
│   │       ├── ops/
│   │       │   └── page.tsx                  # Ops Console (6 sections incl. IMAP + email paste)
│   │       ├── pack/
│   │       │   └── [jobId]/page.tsx          # Application pack review
│   │       └── api/
│   │           ├── decision/route.ts
│   │           ├── tracking/route.ts
│   │           ├── schedule-run/route.ts
│   │           └── sources/
│   │               ├── register/route.ts     # Advanced JSON bulk register
│   │               ├── register-site/route.ts
│   │               ├── register-rss/route.ts
│   │               ├── register-email/route.ts  # Manual email paste
│   │               ├── register-imap/route.ts   # Gmail IMAP auto-scan
│   │               ├── ingest-run/route.ts
│   │               └── score-run/route.ts
│   └── worker/
│       ├── README.md
│       └── worker/
│           ├── main.py
│           ├── jobs.py
│           ├── queue.py
│           ├── ingest/
│           │   ├── adapters.py               # email/RSS/page adapters + IMAP fetch + system email filter
│           │   ├── registry.py
│           │   └── pipeline.py               # dedupe, IntegrityError handling, seen_uids write-back
│           ├── scoring/
│           │   └── pipeline.py
│           ├── packs/
│           │   └── pipeline.py               # YAML guardrail loading
│           └── scheduler/
│               ├── pipeline.py
│               └── notifications.py
├── docs/
│   ├── AGENT_SESSION_PROTOCOL.md
│   ├── INVARIANTS.md
│   ├── MCP_LOCAL_DESIGN.md
│   ├── NOW.md
│   ├── PERSISTENT_AGENT_WORKFLOW.md
│   ├── PROJECT_CONTEXT.md
│   ├── Repo_Structure.md
│   ├── SESSION_NOTES.md
│   └── SPRINT_PLAN.md
├── handoffkit/
│   ├── __main__.py
│   ├── handoffkit.config.json
│   └── templates/
│       ├── architect.md
│       ├── coder.md
│       ├── reviewer.md
│       ├── qa_tester.md
│       └── polish.md
├── infra/
│   ├── README.md
│   └── migrations/
│       ├── env.py
│       └── versions/
│           ├── 20260218_0001_initial_schema.py
│           ├── 20260218_0002_job_tracking_fields.py
│           └── 20260220_0003_uniqueness_constraints.py
├── packages/
│   └── shared/
│       ├── README.md
│       └── jobscout_shared/
│           ├── settings.py                   # includes IMAP_* settings
│           ├── db.py
│           ├── models.py                     # UniqueConstraints on sources + jobs
│           ├── schemas.py                    # URL validation on SourceDefinition
│           └── normalization.py
├── tests/
│   ├── api/
│   │   ├── conftest.py
│   │   └── test_sources_and_inbox.py
│   ├── infra/
│   │   └── test_migrations.py
│   └── worker/
│       ├── test_hello_job.py
│       ├── test_ingest_adapters.py
│       ├── test_ingest_pipeline.py           # includes 5 IMAP unit tests
│       ├── test_pack_pipeline.py
│       ├── test_scheduler_pipeline.py
│       └── test_scoring_pipeline.py
├── SPEC.md
├── RUBRIC.md
├── BUILD_PLAN.md
├── prompt_guardrail.md
├── prompt_guardrail.yml                      # structured YAML guardrail (primary)
├── scoring_weights.yml
├── skills_profile.json
├── truth_bank.yml
├── alembic.ini
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
├── .env.example                              # includes IMAP_* vars
├── .env                                      # local overrides (gitignored)
└── Makefile                                  # includes run-web (Node 20 via nvm)

Notes:
- All sprints (0-4) implemented and runtime-validated. 39 tests passing.
- Gmail IMAP auto-polling live: `fetch_imap_messages()` in adapters.py, `seen_uids` write-back in pipeline.py.
- System email filter (`_is_system_email`) blocks Google setup/security emails from ingest.
- DB uniqueness constraints enforced at migration + ORM level.
- Next.js requires Node ≥20; use `make run-web` (uses nvm Node 20) or run manually:
    cd apps/web && ~/.nvm/versions/node/v20.*/bin/node node_modules/.bin/next dev
