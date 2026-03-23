# Local Context Design - Files as Memory

Version: 0.3
Owner: You

## Purpose
Use local Markdown files plus Git as a transparent memory layer for JobScout development.

## Memory Layers
- LTM: `docs/PROJECT_CONTEXT.md`
- WM: `docs/NOW.md`
- SM: `docs/SESSION_NOTES.md`

## JobScout Context Payload
Hydration should prioritize:
1. `SPEC.md`
2. `docs/INVARIANTS.md`
3. LTM/WM summaries
4. Recent SM entries
5. Task-specific contracts (`RUBRIC.md`, `BUILD_PLAN.md`, `scoring_weights.yml`, `prompt_guardrail.md`)

## Summary Block Convention
```markdown
<!-- SUMMARY_START -->
...summary content...
<!-- SUMMARY_END -->
```
- Keep to concise bullets.
- Agent-maintained by default.

## Writeback Rules
- `NOW.md`: current status + next action
- `SESSION_NOTES.md`: append what changed and why
- `PROJECT_CONTEXT.md`: only when high-level decisions changed

## Design Principles
- Local and inspectable.
- Explicit rituals for start/end session.
- Minimal hidden state.
- Fast recovery after pauses.
