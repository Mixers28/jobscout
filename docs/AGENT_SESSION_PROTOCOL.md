# Agent Session Protocol

Version: 1.1
Owner: You

## Purpose
Define how humans and agents coordinate with local context hydration + writeback so each session starts with accurate state and ends with durable updates.

## Memory Files
- Long-term memory (LTM): `docs/PROJECT_CONTEXT.md`
- Working memory (WM): `docs/NOW.md`
- Session memory (SM): `docs/SESSION_NOTES.md`
- Design notes: `docs/MCP_LOCAL_DESIGN.md`

## Canonical Artifacts
- `SPEC.md` is the implementation source of truth.
- `RUBRIC.md`, `BUILD_PLAN.md`, `scoring_weights.yml`, and `prompt_guardrail.md` must stay aligned with `SPEC.md`.

## Start Session (Context Hydration)
Preferred command:
```bash
python3 -m handoffkit session start --agent-role Coder --open-docs
```

Hydration order:
1. `SPEC.md`
2. `docs/INVARIANTS.md`
3. `docs/PROJECT_CONTEXT.md` summary
4. `docs/NOW.md` summary
5. Recent `docs/SESSION_NOTES.md`
6. Task-relevant artifacts (`RUBRIC.md`, `BUILD_PLAN.md`, `skills_profile.json`, `truth_bank.yml`, `scoring_weights.yml`, `prompt_guardrail.md`)

## End Session (Writeback + Checkpoint)
Preferred command:
```bash
python3 -m handoffkit session end --commit
```

Minimum writeback:
- Update `docs/NOW.md` progress and next action.
- Append a concise entry to `docs/SESSION_NOTES.md`.
- Update `docs/PROJECT_CONTEXT.md` only if high-level constraints changed.

## Hard Anti-Drift Rules
- Do not proceed to a new ticket before context writeback.
- Keep summary blocks concise and current.
- If artifacts are renamed, update all references in the same change.
