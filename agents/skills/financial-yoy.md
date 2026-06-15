# Skill: financial-yoy

**Slash command:** `/financial-yoy`
**Command file:** `.claude/commands/financial-yoy.md`

## Purpose
Year-over-year revenue vs expense comparison across all facilities or scoped to one. Computes net margin per year and calls out best/worst year.

## MCP Tools Used
- `get_financial_yoy` — primary data fetch (calls `dw.usp_GetFinancialYoY`)
- `execute_query` — aggregate fallback against `rpt.vw_FinancialKPIs` when result is too large

## Parameters
| Parameter | Type | Values |
|---|---|---|
| start_year | int | e.g. 2022 |
| end_year | int | e.g. 2025 |
| facility_id | UUID string | optional — scopes to one facility |

## Output
- Markdown table: FiscalYear | Revenue | Expense | Net Income | Margin %
- YoY delta table: Revenue Δ and Expense Δ (amount + %) for each consecutive year pair
- One-line callout: best and worst margin year

## Agent Scope
FinancialAgent — read access to `rpt.*` views and `dw.usp_GetFinancialYoY`
