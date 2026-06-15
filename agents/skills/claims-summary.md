# Skill: claims-summary

**Slash command:** `/claims-summary`
**Command file:** `.claude/commands/claims-summary.md`

## Purpose
Summarise insurance claims from the HealthcareADK DW with optional filters. Returns a breakdown by payer type and claim status, plus aggregate totals.

## MCP Tools Used
- `get_claims_summary` — primary data fetch (calls `dw.usp_GetClaimsSummary`)
- `execute_query` — fallback aggregate query against `rpt.vw_ClaimsSummary` when row volume exceeds the SP's top_n

## Parameters
| Parameter | Type | Values |
|---|---|---|
| start_date | YYYY-MM-DD | e.g. 2024-01-01 |
| end_date | YYYY-MM-DD | e.g. 2024-12-31 |
| payer | string | Commercial, Medicare, Medicaid, Self-Pay |
| status | string | Approved, Denied, Pending, Appealed |
| state | string | 2-letter code e.g. TX |
| top_n | int | default 100 |

## Output
- Markdown table: ClaimStatus × PayerType cross-tab with row/column totals
- Summary line: Total claims | Total billed | Total paid | Denial rate %

## Agent Scope
ClaimsAgent — read access to `rpt.*` views and `dw.usp_GetClaimsSummary`
