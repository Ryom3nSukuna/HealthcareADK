# HealthcareADK — Phase 6 Design: Multi-Agent Architecture

## Goal

Replace single-agent Claude sessions with a structured multi-agent system where a central OrchestratorAgent routes requests to scoped domain agents. Each agent operates with constrained tool access, schema-level DB permissions, and a per-session token budget.

---

## Architecture Overview

```
User Request
     │
     ▼
OrchestratorAgent          (routes, budgets, escalates)
     │
     ├──► ClaimsAgent       (claims schema, claims MCP tools)
     ├──► ClinicalAgent     (patients, labs, prescriptions)
     ├──► FinancialAgent    (financials schema)
     ├──► ReportingAgent    (rpt.* views, TMDL edits, pbi-tools)
     ├──► ETLAgent          (stg.* only, run_python_script, run_ssis_package)
     └──► ProviderAgent     (providers, facilities)
                │
                ▼
         BudgetTracker      (logs tokens → dw.AgentUsageLog)
```

Each domain agent:
- Makes its own Claude API call with a scoped system prompt
- Is given only the MCP tools its role requires
- Connects to SQL Server under a dedicated login with GRANT on its schema only
- Reports token usage to BudgetTracker after every call

---

## Agent Configs (`agents/config/`)

One YAML file per agent. Fields:

```yaml
name: ClaimsAgent
system_prompt: |
  You are the ClaimsAgent for HealthcareADK. You answer questions about
  claims processing, denial rates, payer mix, and claim status.
  You have read-only access to the claims and rpt schemas.
  Never query dw.*, stg.*, or any schema outside your scope.
  Always use search_schema before writing SQL.
allowed_tools:
  - mcp__sqlserver__execute_query
  - mcp__sqlserver__search_schema
  - mcp__sqlserver__get_claims_summary
  - mcp__sqlserver__get_schema
  - mcp__sqlserver__list_tables
db_schemas:
  - rpt
token_budget: 20000
```

### Agent → Tool Allowlist

| Agent | Allowed MCP Tools |
|---|---|
| OrchestratorAgent | `search_schema`, `list_tables` (read-only; delegates execution) |
| ClaimsAgent | `execute_query`, `search_schema`, `get_claims_summary`, `get_schema`, `list_tables` |
| ClinicalAgent | `execute_query`, `search_schema`, `get_abnormal_labs`, `get_patient_timeline`, `get_schema`, `list_tables` |
| FinancialAgent | `execute_query`, `search_schema`, `get_financial_yoy`, `get_schema`, `list_tables` |
| ReportingAgent | `execute_query`, `search_schema`, `list_tables`, `read_file`, `write_file`, `list_files`, `run_pbi_tools` |
| ETLAgent | `run_python_script`, `run_ssis_package`, `run_sql_script`, `execute_query` (stg.* only) |
| ProviderAgent | `execute_query`, `search_schema`, `get_provider_performance`, `get_schema`, `list_tables` |

### Agent → DB Schema Scope

| Agent | Allowed Schemas | SQL Server Login |
|---|---|---|
| OrchestratorAgent | `rpt` (read-only) | `agent_orchestrator` |
| ClaimsAgent | `rpt`, `dw` (SELECT only on claims tables) | `agent_claims` |
| ClinicalAgent | `rpt`, `dw` (SELECT only on patient/lab/rx tables) | `agent_clinical` |
| FinancialAgent | `rpt`, `dw` (SELECT only on financial tables) | `agent_financial` |
| ReportingAgent | `rpt` (read-only) | `agent_reporting` |
| ETLAgent | `stg` (full), `dw.ETLLog` (INSERT) | `agent_etl` |
| ProviderAgent | `rpt`, `dw` (SELECT only on provider/facility tables) | `agent_provider` |

---

## OrchestratorAgent (`agents/orchestrator.py`)

**Responsibility:** Parse user intent → select domain agent → call agent → return result.

### Routing Logic

Intent is matched by keyword scoring against a routing table:

```python
ROUTING_TABLE = {
    "ClaimsAgent":    ["claim", "denial", "billed", "payer", "adjudication", "837"],
    "ClinicalAgent":  ["patient", "lab", "prescription", "drug", "diagnosis", "clinical"],
    "FinancialAgent": ["revenue", "cost", "margin", "expense", "financial", "yoy"],
    "ReportingAgent": ["dashboard", "power bi", "report", "measure", "tmdl", "dax"],
    "ETLAgent":       ["etl", "load", "ingest", "pipeline", "staging", "ssis"],
    "ProviderAgent":  ["provider", "physician", "specialty", "facility", "encounter"],
}
```

If no single agent scores highest, OrchestratorAgent handles the query itself (read-only schema lookup).

### Budget Enforcement

Before dispatching to a domain agent, Orchestrator checks the agent's remaining budget for the session:

```python
if budget_tracker.remaining(agent_name) < MIN_BUDGET_THRESHOLD:
    return escalate(agent_name, user_request)
```

Escalation writes a log entry and returns a structured message to the user explaining the budget limit.

### Multi-Hop Example

```
User: "Show the denial rate trend and refresh the Power BI dashboard."
  → OrchestratorAgent detects two intents
  → Step 1: ClaimsAgent → denial rate query
  → Step 2: ReportingAgent → TMDL check + pbi-tools run
  → OrchestratorAgent merges results and responds
```

---

## Domain Agents

Each domain agent is a thin Python module with a single `run(user_request, session_id)` function:

1. Load config from `agents/config/<name>.yaml`
2. Call Anthropic API with scoped system prompt + allowed tools
3. Execute tool calls (MCP calls routed through the appropriate server)
4. Record token usage via `BudgetTracker`
5. Return result to OrchestratorAgent

```python
# agents/claims_agent.py
def run(user_request: str, session_id: str) -> str:
    config = load_config("claims_agent.yaml")
    result = call_claude(config, user_request)
    budget_tracker.record(config.name, session_id, result.usage)
    return result.content
```

---

## Budget Tracker (`agents/budget_tracker.py`)

Wraps every Claude API call and logs token counts to `dw.AgentUsageLog`.

### `dw.AgentUsageLog` Schema

```sql
CREATE TABLE dw.AgentUsageLog (
    LogID           INT IDENTITY(1,1) PRIMARY KEY,
    AgentName       VARCHAR(50)  NOT NULL,
    SessionID       VARCHAR(100) NOT NULL,
    InputTokens     INT          NOT NULL DEFAULT 0,
    OutputTokens    INT          NOT NULL DEFAULT 0,
    ToolCalls       INT          NOT NULL DEFAULT 0,
    ModelID         VARCHAR(100) NULL,
    RequestTimestamp DATETIME2   NOT NULL DEFAULT SYSDATETIME(),
    Notes           VARCHAR(500) NULL
);
```

### BudgetTracker API

```python
budget_tracker.record(agent_name, session_id, usage, tool_calls=0, notes=None)
budget_tracker.remaining(agent_name, session_id)  # tokens left vs config budget
budget_tracker.session_summary(session_id)        # total across all agents
```

---

## SQL Artifacts

| File | Purpose |
|---|---|
| `sql/09_agent_usage_log.sql` | DDL for `dw.AgentUsageLog` |
| `sql/10_agent_permissions.sql` | SQL Server logins, users, schema-level GRANTs per agent |
| `sql/11_agent_usage_views.sql` | `rpt.vw_AgentUsage` view + `dw.usp_GetAgentUsage` SP |

---

## Directory Structure (additions)

```
agents/
├── config/
│   ├── orchestrator.yaml
│   ├── claims_agent.yaml
│   ├── clinical_agent.yaml
│   ├── financial_agent.yaml
│   ├── reporting_agent.yaml
│   ├── etl_agent.yaml
│   └── provider_agent.yaml
├── orchestrator.py
├── claims_agent.py
├── clinical_agent.py
├── financial_agent.py
├── reporting_agent.py
├── etl_agent.py
├── provider_agent.py
├── budget_tracker.py
└── skills/                    ← existing (Phase 5 slash command specs)

sql/
├── ...                        ← existing (00–08)
├── 09_agent_usage_log.sql     ← new
├── 10_agent_permissions.sql   ← new
└── 11_agent_usage_views.sql   ← new
```

---

## Tasks

- [x] Agent config specs — 7 YAML files in `agents/config/` ✅
- [x] OrchestratorAgent — `agents/orchestrator.py` (intent router, budget enforcement, multi-hop dispatch) ✅
- [x] Domain agents — `agents/{claims,clinical,financial,reporting,etl,provider}_agent.py` + `agents/_base.py` + `agents/tools/{sql,file,shell}_tools.py` ✅
- [x] Budget tracker — `agents/budget_tracker.py` + `sql/09_agent_usage_log.sql` ✅
- [x] SQL Server schema-level permissions — `sql/10_agent_permissions.sql` ✅
- [x] Usage dashboard — `sql/11_agent_usage_views.sql` + `dw.usp_GetAgentUsage` ✅
- [x] End-to-end tests — routing, multi-hop, budget limit, out-of-scope tool block ✅

---

## Testing

Phase 6 has two test suites with different prerequisites.

---

### Suite 1 — Unit tests (`tests/test_phase6.py`)

**What it covers:** Python-level guardrails only. No database connection, no Claude API key needed.

| Test class | What it verifies |
|---|---|
| `TestSingleAgentRouting` | Claim keywords → ClaimsAgent; financial keywords → FinancialAgent |
| `TestMultiHopDispatch` | Two matched agents both called; results merged with `### AgentName` headers |
| `TestBudgetEscalation` | Agent below threshold → no Claude call, "budget" in response; above threshold → normal call |
| `TestToolIsolation` | ClaimsAgent, ETLAgent, ReportingAgent each receive an out-of-scope tool use block and return "not available" in the tool result |

All Claude API calls and `budget_tracker` DB calls are mocked via `unittest.mock.patch`.

**Run:**
```powershell
pytest tests/test_phase6.py -v
```

---

### Suite 2 — Permission integration tests (`tests/test_permissions.py`)

**What it covers:** SQL Server schema-level enforcement. Connects as each agent login and verifies SELECT, EXECUTE, and INSERT permissions match the GRANT/DENY rules in `sql/10_agent_permissions.sql`.

**Prerequisites — must be done in order:**
0. **SQL Server Mixed Mode Authentication** must be enabled: SSMS → right-click server → Properties → Security → "SQL Server and Windows Authentication mode" → OK → restart the service. All agent logins use SQL auth; this setting is required for them to connect.
1. `sql/09_agent_usage_log.sql` deployed in SSMS
2. All 7 `HEALTHCAREADK_PWD_AGENT_*` env vars set in `.env`
3. `python scripts/deploy_agent_logins.py` — creates or resets the 7 SQL Server logins from env vars (uses ALTER LOGIN if login already exists, so passwords stay in sync with `.env`)
4. `sql/10_agent_permissions.sql` deployed in SSMS — creates database users, GRANTs, DENYs
5. `sql/11_agent_usage_views.sql` deployed in SSMS

**Run:**
```powershell
$env:HEALTHCAREADK_TEST_PERMISSIONS = "1"
pytest tests/test_permissions.py -v
```

Tests skip automatically if `HEALTHCAREADK_TEST_PERMISSIONS` is not `"1"`.

| Test class | Login | Positive checks | Negative checks |
|---|---|---|---|
| `TestOrchestratorPermissions` | `agent_orchestrator` | `rpt.*`, `dw.AgentUsageLog` | `dw.FactClaims`, `stg.*` |
| `TestClaimsPermissions` | `agent_claims` | `dw.FactClaims`, `dw.DimPayer`, `rpt.*`, `EXECUTE usp_GetClaimsSummary` | `stg.*`, `dw.FactFinancials`, `dw.FactLabResults` |
| `TestClinicalPermissions` | `agent_clinical` | `dw.FactLabResults`, `dw.FactPrescriptions`, `dw.DimPatient`, `rpt.*`, 2 SPs | `stg.*`, `dw.FactFinancials`, `dw.FactClaims` |
| `TestFinancialPermissions` | `agent_financial` | `dw.FactFinancials`, `dw.DimFacility`, `rpt.*`, `EXECUTE usp_GetFinancialYoY` | `stg.*`, `dw.FactClaims`, `dw.DimPatient`, labs, rx |
| `TestReportingPermissions` | `agent_reporting` | `rpt.*`, `dw.AgentUsageLog`, `EXECUTE usp_GetAgentUsage` | `dw.FactClaims`, `stg.*` |
| `TestETLPermissions` | `agent_etl` | `stg.*`, `dw.*` SELECT, `dw.ETLLog` INSERT, `EXECUTE usp_ETL_RunAll` | `dw.FactClaims` INSERT, `dw.FactClaims` DELETE |
| `TestProviderPermissions` | `agent_provider` | `dw.DimProvider`, `dw.DimFacility`, `rpt.*`, `EXECUTE usp_GetProviderPerformance` | `stg.*`, `dw.FactFinancials`, labs, rx |

---

## Live Testing Bug Fixes (2026-06-15)

Bugs discovered during end-to-end live testing after initial deployment:

| Bug | Root Cause | Fix |
| --- | --- | --- |
| Routing parse error on every query | Claude wraps JSON in markdown code fences; `json.loads` fails at char 0 | Strip fences before parse in `_route()` — split on first newline, strip trailing fence |
| ETLAgent crashes on budget check | Single-pass snake_case regex splits each capital: `ETLAgent` → `e_t_l_agent` | Two-pass regex in `_agent_yaml_name()`: acronym boundary first, then lowercase→uppercase |
| ClinicalAgent truncated on large result sets | `max_tokens=4096` in `_base.py` insufficient for 200-row lab tables | Raised to `max_tokens=8192` |
| Unicode crash on Windows CLI | `print()` uses cp1252; Claude responses contain non-cp1252 characters | `sys.stdout.reconfigure(encoding="utf-8")` in `orchestrator.main()` |

---

## Guardrails Summary

| Guardrail | Enforcement Point |
|---|---|
| Agent sees only its allowed tools | OrchestratorAgent passes only the tool list from config |
| Agent queries only its schema | SQL Server login has no GRANT on other schemas |
| No DML/DDL on `dw.*` | `guard_query.py` PreToolUse hook |
| No writes to credential files or path traversal | `guard_file_write.py` PreToolUse hook (`mcp__file__write_file`) |
| No reads of `.env` or credential files | `guard_file_read.py` PreToolUse hook (`Read` + `mcp__file__read_file`) |
| Token budget per agent | BudgetTracker checks remaining before each call |
| Escalation on budget exceeded | Orchestrator writes log entry, returns structured error |
