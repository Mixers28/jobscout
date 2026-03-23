# Invariants (Non-Negotiables)

- Use only safe-first ingestion sources (alerts, RSS, whitelisted pages).
- Never bypass CAPTCHAs or restricted platform controls.
- Do not auto-submit applications; human final submission is mandatory in v0.1.
- Every generated claim must be evidence-backed by `skills_profile.json` or `truth_bank.yml`.
- Unsupported or ambiguous answers must return `NEEDS_USER_INPUT`.
- Scoring decisions must be explainable (`top_reasons`, `missing_keywords`).
- File contracts are fixed and canonical; runtime must use the fixed names.
- Keep memory/context docs in plain Markdown and current.

Last reviewed: 2026-02-18
