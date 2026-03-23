# Build Plan (v0.1)

## Ingestion (daily)
- Pull jobs from email alerts (LinkedIn/Indeed/others)
- Pull jobs from whitelisted sources (MyJobScotland, NHS Scotland, Civil Service Jobs, selected employer pages)
- Parse each listing into a normalized Job object: title, company, location, salary, link, description

## Matching
- Compute score using `skills_profile.json`, `RUBRIC.md`, and `scoring_weights.yml`
- Deduplicate reposted jobs using canonical URL + description hash

## Application Pack Generator
For each `apply` job:
- Tailor CV bullets
- Generate cover letter
- Draft screening answers from `truth_bank.yml`
- Produce submission checklist for missing inputs
- Enforce `prompt_guardrail.md` before final output

## Submission (human-in-the-loop)
- Open job link for manual submission
- Provide copy/paste-ready answers and final review page
- User performs final submit action
