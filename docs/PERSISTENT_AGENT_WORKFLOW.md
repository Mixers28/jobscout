# Persistent Agent Workflow Design

Version: 1.1
Owner: You

## Purpose
Define predictable start/end session rituals so human + agent collaboration stays consistent while building JobScout.

## Core Workflow
1. Start session with handoffkit context hydration.
2. Execute one focused implementation task.
3. Run relevant checks/tests.
4. Write back NOW + SESSION_NOTES updates.
5. End session with optional commit.

## Required Context Pack
- `SPEC.md`
- `docs/INVARIANTS.md`
- `docs/PROJECT_CONTEXT.md` summary
- `docs/NOW.md` summary
- recent `docs/SESSION_NOTES.md`
- relevant task artifacts (`RUBRIC.md`, `BUILD_PLAN.md`, `scoring_weights.yml`, `prompt_guardrail.md`)

## Session Commands
```bash
python3 -m handoffkit session start --agent-role Coder --open-docs
python3 -m handoffkit session end --commit
```

## Drift Controls
- Keep fixed filenames stable.
- If contracts change, update all linked docs in same commit.
- Do not leave stale cross-project context in memory docs.
