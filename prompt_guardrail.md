# Prompt Guardrail Contract (v0.1)

Purpose: prevent unsupported claims in cover letters, CV variants, and screening answers.

## Required Inputs
- `job`: normalized job object (`title`, `company`, `description_text`, `requirements_text`, `url`)
- `skills_profile`: from `skills_profile.json`
- `truth_bank`: from `truth_bank.yml`
- `missing_requirements`: optional list from matcher

If any required input is missing, return `status: NEEDS_USER_INPUT`.

## Non-Negotiable Rules
1. Never invent facts, metrics, dates, cert status, or tool depth.
2. Every claim must include at least one evidence reference.
3. Evidence references must point to either:
   - `skills_profile` evidence line(s), or
   - specific `truth_bank` field path(s).
4. If evidence is unavailable or ambiguous, use `NEEDS_USER_INPUT` for that field.
5. Do not claim legal/work authorization beyond explicit `truth_bank.identity.right_to_work_uk` content.
6. Use UK English tone and keep cover letters between 150 and 250 words.

## Output Contract (strict JSON)
Return only JSON with this shape:

```json
{
  "status": "OK | NEEDS_USER_INPUT",
  "cv_variant_md": "string",
  "cover_letter_md": "string",
  "screening_answers": [
    {
      "question": "string",
      "answer": "string | NEEDS_USER_INPUT",
      "evidence_refs": [
        {
          "source": "skills_profile | truth_bank",
          "path": "jsonpath-or-yaml-path",
          "quote": "short supporting excerpt"
        }
      ]
    }
  ],
  "claims": [
    {
      "id": "claim_001",
      "text": "string",
      "evidence_refs": [
        {
          "source": "skills_profile | truth_bank",
          "path": "jsonpath-or-yaml-path",
          "quote": "short supporting excerpt"
        }
      ],
      "supported": true
    }
  ],
  "needs_user_input": [
    {
      "field": "string",
      "reason": "string"
    }
  ]
}
```

## Validation Checklist
Before returning output:
- Reject any claim without `evidence_refs`
- Reject any evidence ref with empty `path`
- Reject if `cover_letter_md` is outside 150-250 words
- Set `status: NEEDS_USER_INPUT` when `needs_user_input` is non-empty

## Failure Behavior
If validation fails:
- Return partial output
- Mark unresolved fields with `NEEDS_USER_INPUT`
- Add reasons in `needs_user_input`
