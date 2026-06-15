# HealthcareADK — Claude AI Constitution

## Project Overview
End-to-end agentic data architecture using the **Healthcare domain**.
Raw data → ETL → SQL Server Data Warehouse → Power BI → Multi-Agent AI layer.

## Domain
Healthcare: Patients, Providers, Claims, Labs, Prescriptions, Facilities, Payers, Financials.

---

## Project Phases

| Phase | Name | Status |
|-------|------|--------|
| 1 | Foundation & Synthetic Data | ✅ Complete (2026-05-15) |
| 2 | Data Warehouse Design | ✅ Complete (2026-05-18) |
| 3 | ETL Pipelines | ✅ Complete (2026-05-18) |
| 4 | Power BI Reporting Layer | ✅ Complete (2026-05-19) |
| 5 | Claude AI Layer (RAG, MCP, Skills, Hooks) | ✅ Complete (2026-06-14) |
| 6 | Multi-Agent Architecture | ✅ Complete (2026-06-15) |
| 7 | Smart Caching + Chat Frontend | 🔜 Planned |

---

## Phase 5 — Claude AI Layer Design

### Core Principle: Agents Edit Text, Not Binary Files

`.pbix` (Power BI) and `.dtsx` (SSIS) are binary/opaque — Claude cannot edit them directly.
All real logic lives in text files that Claude controls:

- **ETL logic** → `sql/08_etl_stg_to_dw.sql` (stored procedures). The `.dtsx` packages are thin wrappers that call `EXEC dw.usp_ETL_RunAll`.
- **Power BI data model** → `powerbi/tmdl/` (TMDL text files). Report visuals remain human-built in Desktop.

### MCP Servers

| MCP Server | Purpose | Status |
| --- | --- | --- |
| `mcp-sqlserver` | Execute queries and SPs against HealthcareADK DW | ✅ Live (`mcp/sqlserver/server.py`, 9 tools) |
| `mcp-shell` | Run `dtexec`, `pbi-tools deploy`, Python scripts | ✅ Live (`mcp/shell/server.py`, 4 tools) |
| `mcp-file` | Read/write `.sql`, `.tmdl`, `.csv`, `.json` files | ✅ Live (`mcp/file/server.py`, 4 tools) |
| `mcp-powerbi` | Trigger dataset refresh, update parameters via REST API | ⏸ Deferred (requires work/school account for Power BI Service) |

### Hooks

7 hooks wired in `.claude/settings.json`, scripts in `scripts/hooks/`:

| Type | Matcher | Script | Purpose |
| --- | --- | --- | --- |
| PreToolUse | `Read` | `guard_file_read.py` | Block reads of `.env`, credential files |
| PreToolUse | `mcp__file__read_file` | `guard_file_read.py` | Block reads of `.env`, credential files (MCP path) |
| PreToolUse | `mcp__sqlserver__execute_query` | `guard_query.py` | Block DML/DDL on `dw.*`, DELETE without WHERE |
| PreToolUse | `mcp__file__write_file` | `guard_file_write.py` | Block path traversal, credential file writes |
| PostToolUse | `mcp__shell__run_python_script` | `on_data_drop.py` | `generate_all.py` → auto-run ETL |
| PostToolUse | `mcp__shell__run_ssis_package` | `on_ssis_complete.py` | Query `dw.ETLLog` after SSIS run |
| PostToolUse | `mcp__shell__run_pbi_tools` | `on_pbi_deploy.py` | Surface last 20 lines of pbi-tools output |

### TMDL Workflow

Export Power BI data model → `powerbi/tmdl/` → Claude edits `.tmdl` files → redeploy via `pbi-tools` CLI.

---

## Agent Roles (Phase 6)

| Agent | Scope | DB Access |
|-------|-------|-----------|
| OrchestratorAgent | Routes tasks, manages budget | Read-only across all schemas |
| ETLAgent | Ingestion, transformation | Staging schema only |
| ClaimsAgent | Claims processing & analysis | claims schema only |
| ClinicalAgent | Patient & clinical data | patients, labs, prescriptions schemas |
| FinancialAgent | Revenue, costs, KPIs | financials schema only |
| ReportingAgent | Power BI refresh, report generation | Read-only DW views |
| ProviderAgent | Provider & facility data | providers, facilities schemas |

---

## Guardrails

### Access Control
- Agents are scoped to their assigned schema — no cross-domain DB access.
- Permissions enforced at both MCP server level and SQL Server schema level.
- Principle of least privilege throughout.

### Token Budget
- Each agent has a per-session token budget.
- Agents must escalate to OrchestratorAgent before exceeding budget.
- All token usage is logged.

### Data Sensitivity
- All synthetic data — no real PII.
- Even so, treat patient-adjacent data as sensitive in architecture decisions.

---

## Directory Structure

```
HealthcareADK/
├── CLAUDE.md                  ← You are here
├── README.md                  ← Project overview
├── .env                       ← Local secrets (gitignored — never committed)
├── .gitignore                 ← Ignores .env, landing_zone/, __pycache__/, schema_kb.json
├── .mcp.json                  ← MCP server registry
├── docs/
│   ├── plan.md                ← Detailed phase plan
│   ├── phase5_design.md       ← Phase 5 architecture (agents, TMDL, MCP)
│   ├── phase6_design.md       ← Phase 6 architecture (multi-agent, orchestrator, budget tracker)
│   └── schema_kb.json         ← RAG knowledge base (tables, columns, SPs) — built by scripts/build_schema_kb.py
├── landing_zone/              ← Raw data drop zone
│   ├── claims/
│   ├── facilities/
│   ├── financials/
│   ├── labs/
│   ├── manifest/
│   ├── patients/
│   ├── payers/
│   ├── prescriptions/
│   └── providers/
├── scripts/                   ← ETL and utility scripts
│   ├── deploy_agent_logins.py ← Creates SQL Server logins from env vars (no passwords in source)
│   ├── build_schema_kb.py     ← Rebuilds docs/schema_kb.json RAG index
│   ├── generate_all.py        ← Synthetic data generation
│   └── hooks/                 ← Claude hook scripts
│       ├── guard_file_read.py ← Block reads of .env / credential files (Read + mcp__file__read_file)
│       ├── guard_file_write.py← Block writes to credential files / path traversal
│       ├── guard_query.py     ← Block DML/DDL on dw.*, DELETE without WHERE
│       ├── on_data_drop.py    ← Auto-run ETL after generate_all.py
│       ├── on_ssis_complete.py← Query dw.ETLLog after SSIS run
│       └── on_pbi_deploy.py   ← Surface pbi-tools output
├── sql/                       ← DDL, stored procedures, views (00–11)
├── tests/                     ← Phase 6 pytest suites
│   ├── test_phase6.py         ← Unit tests: routing, multi-hop, budget, tool isolation (no DB needed)
│   └── test_permissions.py    ← Integration tests: SQL Server schema permissions per agent login
│                                 Skipped unless HEALTHCAREADK_TEST_PERMISSIONS=1
├── ssis/                      ← SSIS package design guides
├── agents/
│   ├── config/                ← Agent YAML configs (system prompt, tool allowlist, schema scope, token budget)
│   ├── tools/
│   │   ├── sql_tools.py       ← pyodbc SQL tools + Anthropic API definitions (all SQL agents)
│   │   ├── file_tools.py      ← File I/O tools + write guard (ReportingAgent)
│   │   └── shell_tools.py     ← Subprocess tools: dtexec, python, pbi-tools, sqlcmd (ETL + Reporting)
│   ├── _base.py               ← Shared agentic loop (tool execution, iteration cap, budget recording)
│   ├── orchestrator.py        ← OrchestratorAgent: routes requests, enforces budgets, merges multi-hop results
│   ├── claims_agent.py        ← ClaimsAgent
│   ├── clinical_agent.py      ← ClinicalAgent
│   ├── financial_agent.py     ← FinancialAgent
│   ├── reporting_agent.py     ← ReportingAgent
│   ├── etl_agent.py           ← ETLAgent
│   ├── provider_agent.py      ← ProviderAgent
│   ├── budget_tracker.py      ← Token usage logger → dw.AgentUsageLog
│   └── skills/                ← Skill specs: claims-summary, financial-yoy, abnormal-labs
├── mcp/
│   ├── sqlserver/             ← mcp-sqlserver (FastMCP, 9 tools) ✅ Live
│   ├── shell/                 ← mcp-shell (FastMCP, 4 tools) ✅ Live
│   ├── file/                  ← mcp-file (FastMCP, 4 tools) ✅ Live
│   └── powerbi/               ← mcp-powerbi (FastMCP, 4 tools) ⏸ Deferred
├── powerbi/
│   ├── tmdl/                  ← TMDL export (source of truth for data model)
│   └── *.md                   ← Design guides and DAX reference
```

---

## Claude Behavior in This Project
- Always reference domain context (healthcare) when making architectural suggestions.
- Do not generate code until the relevant phase is explicitly approved.
- Prefer concise, targeted tool calls — respect token budgets.
- When an agent boundary question arises, default to more restrictive access.
- All ETL logic must go through the staging layer — never write directly to DW from raw.
