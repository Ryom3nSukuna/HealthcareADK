# Skill: abnormal-labs

**Slash command:** `/abnormal-labs`
**Command file:** `.claude/commands/abnormal-labs.md`

## Purpose
Surface abnormal and critical lab results. Prioritises Critical rows and calls them out explicitly to support clinical triage workflows.

## MCP Tools Used
- `get_abnormal_labs` — primary data fetch (calls `dw.usp_GetAbnormalLabResults`)
- `execute_query` — aggregate fallback against `rpt.vw_LabResults` when result volume is too large

## Parameters
| Parameter | Type | Values |
|---|---|---|
| patient_id | UUID string | optional — scopes to one patient |
| start_date | YYYY-MM-DD | optional |
| end_date | YYYY-MM-DD | optional |
| flag | string | High, Low, Critical (omit for all abnormal) |
| top_n | int | default 200 |

## Output
- Markdown table: ResultDate | Patient | Test | Value | Unit | Flag (sorted by date desc)
- Summary line: Critical: N | High: N | Low: N | Total abnormal: N
- Critical callout: patient names + test names for all Critical rows (capped at top 5)

## Agent Scope
ClinicalAgent — read access to `rpt.*` views and `dw.usp_GetAbnormalLabResults`
