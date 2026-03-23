# Matching Rubric (v0.1)

## Step 1 - Hard Filters (fail-fast)
Auto-skip a job if any are true:
- Daily onsite presence is required outside Scotland and role is not remote
- Requires clearance the candidate does not have and is not willing to obtain
- Role family mismatch (for example pure software engineering or sales-only roles)

## Step 2 - Region-Aware Boosts
Apply targeted boosts for North/East Scotland context:
- Aberdeen roles mentioning energy, offshore, on-call, multi-site, ITIL-style operations
- Inverness/Highlands roles requiring broad onsite infrastructure ownership
- Public sector roles (council/NHS) emphasizing M365, endpoint, governance, change control

## Step 3 - Weighted Score (0-100)
### A) Microsoft 365 core (0-30)
- Exchange Online / mail flow / hybrid: +0..12
- SharePoint Online / migration: +0..10
- Teams administration: +0..8

### B) Backup / DR (0-25)
- Azure Backup: +0..10
- Veeam: +0..10
- NAS/Tape/Cold storage + restore testing: +0..5

### C) Ops / Service ownership (0-15)
- L3 support / incident ownership: +0..15

### D) Migrations / project delivery (0-15)
- On-prem to cloud migrations (Exchange/SharePoint/telco): +0..10
- Vendor management + delivery: +0..5

### E) Telco / Teams Voice (0-5)
- Avaya / SBC / SIP / Teams Phone: +0..5

### F) Location + work-mode fit (-10 to +10)
- Hybrid within preferred radius: +10
- Remote UK: +6
- Onsite within preferred radius: +6
- Onsite far outside preferred area: -10

## Decision Thresholds
- 80-100: `apply`
- 60-79: `review`
- below 60: `skip`

## Explainability Output (required)
For every scored job store:
- `top_reasons` (example: "Strong match: Veeam + Azure Backup")
- `missing_keywords` (example: "Intune, Conditional Access, PowerShell automation")
