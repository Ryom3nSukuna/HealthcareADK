# HealthcareADK — Detailed Project Plan

## Phase 1 — Foundation & Synthetic Data ✅ COMPLETE (2026-05-15)

**Goal:** Create the raw data layer and project scaffold.

### Tasks

- [x] Generate synthetic data: Patients — 50,000 rows → CSV
- [x] Generate synthetic data: Providers — 5,000 rows → CSV
- [x] Generate synthetic data: Claims — 50,000 rows → CSV + EDI X12 837 (50 batch files)
- [x] Generate synthetic data: Labs — 50,000 rows → CSV + JSON (5,000 nested) + 100 PDF reports
- [x] Generate synthetic data: Prescriptions — 50,000 rows → CSV + JSON
- [x] Generate synthetic data: Facilities — 500 rows → CSV
- [x] Generate synthetic data: Payers — 100 rows → CSV
- [x] Generate synthetic data: Financials — 50,000 rows → Excel (.xlsx)
- [x] Manifest schema (auto-generated on each run) → JSON
- [x] Finalize CLAUDE.md and README.md
- [ ] Install dependencies and run: `pip install -r requirements.txt && python scripts/generate_all.py`

### Deliverables

- Populated `landing_zone/` with realistic synthetic data files
- Data dictionary documenting every field

---

## Phase 2 — Data Warehouse Design ✅ COMPLETE (2026-05-18)
**Goal:** Design and create the SQL Server data warehouse.

### Tasks
- [x] Design star schema (constellation — 4 facts, 7 dims)
- [x] sql/00_create_database.sql — HealthcareADK database
- [x] sql/01_create_schemas.sql — stg / dw / rpt schemas
- [x] sql/02_stg_tables.sql — 8 staging tables (mirror landing zone)
- [x] sql/03_dw_dim_date.sql — DimDate pre-populated 2019-2030
- [x] sql/04_dw_dimensions.sql — DimPayer, DimFacility, DimProvider, DimPatient (SCD2), DimDiagnosis, DimProcedure, DimDrug
- [x] sql/05_dw_facts.sql — FactClaims, FactLabResults, FactPrescriptions, FactFinancials
- [x] sql/06_rpt_views.sql — 5 reporting views for Power BI
- [x] sql/07_stored_procedures.sql — 5 agent-ready SPs
- [ ] Run scripts in SSMS (order: 00 → 01 → 02 → 03 → 04 → 05 → 06 → 07)

### Key Tables
**Facts:** FactClaims, FactEncounters, FactPrescriptions, FactLabResults, FactFinancials
**Dims:** DimPatient, DimProvider, DimFacility, DimPayer, DimDate, DimDiagnosis, DimDrug

---

## Phase 3 — ETL Pipelines ✅ COMPLETE (2026-05-18)
**Goal:** Move data from landing zone through staging into the DW.
**Tooling chosen:** SSIS (SQL Server Integration Services)

### Tasks
- [x] ETL tooling: SSIS
- [x] sql/08_etl_stg_to_dw.sql — ETLLog table, fn_DateKey helper, 8 ETL SPs + usp_ETL_RunAll
- [x] ssis/SSIS_Design_Guide.md — full SSDT build guide for 3 packages
- [x] Build packages in SSDT: Package_Load_Staging, Package_Load_DW, Package_Master
- [x] Run Package_Master and verify row counts in SSMS

---

## Phase 4 — Power BI Reporting Layer ✅ COMPLETE (2026-05-19)
**Goal:** Visual dashboards connected to the DW.
**Mode:** Import (Power BI Desktop only)

### Deliverables
- [x] powerbi/PowerBI_Design_Guide.md — connection setup, data model, 6 page specs
- [x] powerbi/DAX_Measures.md — all DAX measures and Age Band calculated column

### Dashboards (build in Power BI Desktop per design guide)
- [x] Claims Overview (volume, denial rate, avg claim value)
- [x] Patient Demographics (age bands, geography, payer mix)
- [x] Provider Performance (encounters per provider, specialty breakdown)
- [x] Financial KPIs (revenue, cost, margin — YoY comparison)
- [x] Lab Trends (test volumes, abnormal result rates)
- [x] Prescription Analytics (top drugs, refill rates)

---

## Phase 5 — Claude AI Layer
**Goal:** Wire Claude into the data stack.
**Design:** See [docs/phase5_design.md](phase5_design.md) — agents edit SQL/TMDL not .dtsx/.pbix, MCP server list, TMDL workflow.

### Tasks
- [x] Set up MCP server: `mcp-sqlserver` — 8 tools, verified working ✅
- [x] Set up MCP server: `mcp-shell` — 4 tools, verified working ✅
- [x] Set up MCP server: `mcp-file` — 4 tools, verified working ✅
- [ ] Set up MCP server: `mcp-powerbi` — deferred ⏸ (Power BI Service requires work/school account)
- [x] Export Power BI data model to TMDL → save to `powerbi/tmdl/` ✅
- [x] Implement RAG over data dictionary + DW schema ✅ (`scripts/build_schema_kb.py` → `docs/schema_kb.json`; `search_schema` tool in mcp-sqlserver)
- [x] Write skills for common analytical patterns ✅ (3 slash commands: `/claims-summary`, `/financial-yoy`, `/abnormal-labs`; runnable via `.claude/commands/`, specs in `agents/skills/`)
- [x] Configure hooks ✅ — 5 hooks in `scripts/hooks/`, wired in `.claude/settings.json`:

  | Type | Matcher | Script | Purpose |
  |------|---------|--------|---------|
  | PreToolUse | `mcp__sqlserver__execute_query` | `guard_query.py` | Block DML/DDL on `dw.*`, DELETE without WHERE |
  | PreToolUse | `mcp__file__write_file` | `guard_file_write.py` | Block path traversal, credential files |
  | PostToolUse | `mcp__shell__run_python_script` | `on_data_drop.py` | `generate_all.py` → auto-run ETL |
  | PostToolUse | `mcp__shell__run_ssis_package` | `on_ssis_complete.py` | Query `dw.ETLLog` after SSIS run |
  | PostToolUse | `mcp__shell__run_pbi_tools` | `on_pbi_deploy.py` | Surface last 20 lines of pbi-tools output |
- [x] Test Claude querying DW via natural language ✅
- [x] Test Reporting Agent: DAX measure change via TMDL ✅ (deploy to Desktop pending mcp-powerbi / manual ALM step)

---

## Phase 6 — Multi-Agent Architecture
**Goal:** Agents that collaborate, respect permissions, and manage cost.
**Design:** See [docs/phase6_design.md](phase6_design.md) — agent configs, orchestrator, budget tracking, inter-agent comms.

### Tasks

#### 1 — Agent Config Specs ✅

- [x] Create `agents/config/` directory
- [x] Write YAML config for each agent (system prompt, tool allowlist, schema scope, token budget)
  - [x] `orchestrator.yaml`
  - [x] `claims_agent.yaml`
  - [x] `clinical_agent.yaml`
  - [x] `financial_agent.yaml`
  - [x] `reporting_agent.yaml`
  - [x] `etl_agent.yaml`
  - [x] `provider_agent.yaml`

#### 2 — OrchestratorAgent ✅

- [x] `agents/orchestrator.py` — intent router; pattern-matches user request → picks domain agent
- [x] Routing table: keyword/domain → agent name
- [x] Budget enforcement: reject requests that would exceed per-agent budget
- [x] Escalation path: log and surface when budget is exceeded

#### 3 — Domain Agents ✅

- [x] `agents/claims_agent.py` — ClaimsAgent (claims schema, claims MCP tools)
- [x] `agents/clinical_agent.py` — ClinicalAgent (patients, labs, prescriptions)
- [x] `agents/financial_agent.py` — FinancialAgent (financials schema)
- [x] `agents/reporting_agent.py` — ReportingAgent (rpt.* views, TMDL edits, pbi-tools)
- [x] `agents/etl_agent.py` — ETLAgent (stg.* only, run_python_script, run_ssis_package)
- [x] `agents/provider_agent.py` — ProviderAgent (providers, facilities)
- [x] `agents/_base.py` — shared agentic loop (tool execution, MAX_ITERATIONS cap, budget recorder)
- [x] `agents/tools/sql_tools.py` — pyodbc SQL tools + Anthropic API definitions
- [x] `agents/tools/file_tools.py` — file I/O tools + write guard
- [x] `agents/tools/shell_tools.py` — subprocess tools (dtexec, python, pbi-tools, sqlcmd)

#### 4 — Budget Tracker ✅

- [x] `agents/budget_tracker.py` — wraps every Claude API call; logs token counts
- [x] SQL table: `dw.AgentUsageLog` (AgentName, SessionID, InputTokens, OutputTokens, ToolCalls, RequestTimestamp)
- [x] Write SQL DDL for `AgentUsageLog` → `sql/09_agent_usage_log.sql`

#### 5 — SQL Server Schema-Level Permissions ✅

- [x] `scripts/deploy_agent_logins.py` — creates or resets 7 SQL Server logins from env vars (`HEALTHCAREADK_PWD_AGENT_*`); no passwords in any source file; uses ALTER LOGIN for existing logins so `.env` stays in sync
- [x] `sql/10_agent_permissions.sql` — CREATE USER per agent login; GRANT SELECT on scoped schemas; explicit DENY cross-schema (run after `deploy_agent_logins.py`)
- **Prerequisite:** SQL Server instance must have **Mixed Mode Authentication** enabled. SSMS → right-click server → Properties → Security → "SQL Server and Windows Authentication mode" → restart service. Required because all agent logins use SQL auth.

#### 6 — Usage Dashboard ✅

- [x] `sql/11_agent_usage_views.sql` — reporting view over `dw.AgentUsageLog`
- [x] Stored procedure: `dw.usp_GetAgentUsage` (filters by agent, date range)
- [x] Register view in `docs/schema_kb.json` (rebuild RAG index — descriptions added to `scripts/build_schema_kb.py`; run after SQL deployment)

#### 7 — End-to-End Tests ✅

Two test suites — see [docs/phase6_design.md § Testing](phase6_design.md) for full details.

**Unit tests (no DB or API key required):**
- [x] User query → OrchestratorAgent routes → ClaimsAgent → result
- [x] OrchestratorAgent → FinancialAgent → ReportingAgent (multi-hop, merged result)
- [x] Budget limit hit → escalation logged, no agent call made
- [x] Agent receives out-of-scope tool use block → "not available" returned
- Run: `pytest tests/test_phase6.py -v`

**Permission integration tests (requires SQL deployed + agent logins created):**
- [x] Each agent login can SELECT only its approved schemas/tables
- [x] Each agent login is denied access to all other schemas (DENY enforced)
- [x] ETLAgent can INSERT into `dw.ETLLog` but not `dw.FactClaims`
- [x] Stored procedure EXECUTE grants verified per agent
- Run: `$env:HEALTHCAREADK_TEST_PERMISSIONS=1; pytest tests/test_permissions.py -v`
- Prerequisite env vars: `HEALTHCAREADK_PWD_AGENT_ORCHESTRATOR`, `_CLAIMS`, `_CLINICAL`, `_FINANCIAL`, `_REPORTING`, `_ETL`, `_PROVIDER`
