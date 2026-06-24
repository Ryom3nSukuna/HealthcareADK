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

**Live agent testing (2026-06-15) — bugs found and fixed:**

- [x] Orchestrator routing: Claude returns JSON wrapped in markdown fences → stripped before `json.loads`
- [x] ETLAgent budget check: `_agent_yaml_name("ETLAgent")` → `"e_t_l_agent"` (wrong); two-pass regex fix → `"etl_agent"`
- [x] `max_tokens` 4096 → 8192 in `_base.py` (ClinicalAgent truncated on large result sets)
- [x] CLI stdout encoding: `sys.stdout.reconfigure(encoding="utf-8")` to handle Unicode on Windows cp1252

---

## Phase 7 — Smart Caching + Chat Frontend

**Goal:** Eliminate redundant API calls for repeated queries; expose the agent system through a chat UI.

**Design:** See [docs/phase7_design.md](phase7_design.md)

### Tasks

#### 1 — Layer 1: Anthropic Prompt Caching ✅

- [x] Add `cache_control: {"type": "ephemeral"}` to system prompt block in `agents/_base.py`
- [x] Verify cache hit/miss in `response.usage` (`cache_read_input_tokens`, `cache_creation_input_tokens`) — live-tested all 7 agents
- [x] Log cache hits to `dw.AgentUsageLog` (`CachedTokens` column added to `09_agent_usage_log.sql`; surfaced in `11_agent_usage_views.sql`)
- **Finding:** only ClinicalAgent and ReportingAgent actually cross this account's real cacheable-prefix minimum (~1300–1400 tokens, higher than the commonly-cited 1024). ClaimsAgent/FinancialAgent/ProviderAgent/ETLAgent/orchestrator routing get no benefit from Layer 1 — see [phase7_design.md § Layer 1](phase7_design.md#layer-1--anthropic-prompt-caching) for the measured breakdown. Code left in place (harmless no-op below threshold); Layer 2 is the layer that matters for universal savings.

#### 2 — Layer 2: Response Cache (SQL Server) ✅

- [x] `sql/12_query_cache.sql` — `dw.QueryCache` table: `CacheKey`, `AgentName`, `Query`, `Response`, `CreatedAt`, `ExpiresAt`; `agent_orchestrator` granted SELECT/INSERT/DELETE
- [x] `agents/cache.py` — `cache_get`/`cache_set`/`cache_invalidate`; key = `SHA256(agent_name + "::" + lower(strip(query)))`; connects via `agent_orchestrator`'s own SQL login, not trusted auth
- [x] TTL per agent added to `agents/config/*.yaml` as `cache_ttl_minutes`: ETLAgent/ClinicalAgent = 15 min, ClaimsAgent/ProviderAgent = 30 min, FinancialAgent/ReportingAgent = 60 min
- [x] Cache check inside `agents/orchestrator.py:_dispatch()` — applies per-leg to both single-agent and multi-hop dispatch; on hit, returns immediately, budget check never runs
- [x] Cache write inside `_dispatch()` after a fresh dispatch, using the agent's configured TTL
- [x] Cache invalidation — ETLAgent dispatch flushes `ETLAgent` + `ClinicalAgent` cache entries (implemented in `orchestrator.py`, not `etl_agent.py`, to keep cache ownership/DB grants centralized to `agent_orchestrator`)
- [x] 2 new unit tests (`TestResponseCache`) + autouse fixture so the other 9 tests don't hit real DB through the new cache calls — 11/11 passing
- [x] Live-verified: identical query run twice → second call returned byte-identical output with `AgentUsageLog` showing only 1 row for the session (0 tokens on the hit); `ExpiresAt` matched `CreatedAt + 30 min` exactly; ETLAgent dispatch confirmed to purge ClinicalAgent's cache row
- **Known limitation (by design, not a bug):** cache key is exact-text-match, not semantic — "total payments in ohio" vs "total payments in OH" hash differently and create separate cache entries. Confirmed live 2026-06-20. Documented in [phase7_design.md § Cache Key](phase7_design.md#cache-key-agentscachepy); decided to leave as-is rather than add semantic (embedding-based) caching, which would bring real false-positive risk for a materially bigger feature.

#### 3 — Chat Frontend (FastAPI + UI) ✅

- [x] `agents/orchestrator.py` — added `run_with_meta()` returning `(text, agents, session_id)`; `run()` kept unchanged as a thin wrapper so the CLI and existing tests are unaffected
- [x] `api/main.py` — FastAPI app with `POST /chat` (sync endpoint, calls `run_with_meta()`) + `GET /health`
- [x] `api/models.py` — `ChatRequest` / `ChatResponse` Pydantic models
- [x] `frontend/` — HTML/JS chat UI (`index.html`, `app.js`, `style.css`) that POSTs to `/chat` and renders markdown via marked.js, sanitized with DOMPurify before `innerHTML` insertion
- [x] Session ID generated server-side on first message, returned to the client, persisted in `localStorage`, and passed back on every subsequent turn — budget tracking and Layer 2 caching stay scoped per session
- [x] CORS configured (`allow_origins=["*"]`, local dev only)
- [x] `fastapi` + `uvicorn` added to `requirements.txt`
- [x] Live-tested: `/chat`, CORS preflight, session continuity, and cache hits all verified via curl; real browser session tested by the user, who caught a routing quality bug (see below) — fixed and re-verified
- **Bug found + fixed during live testing:** `orchestrator.yaml`'s routing prompt was too eager to multi-hop — a single-domain question ("who was prescribed Amoxicillin and who paid for it") was dispatched to both ClinicalAgent and ClaimsAgent even though `rpt.vw_Prescriptions` already carries payer/cost columns, producing two overlapping tables concatenated into one oversized response. Fixed by tightening the routing prompt to default to single-agent and reserve multi-hop for requests needing genuinely separate systems. Verified: the overlapping case now routes to `["ClinicalAgent"]` alone; the doc's own multi-hop example (denial rate + dashboard refresh) still correctly routes to `["ClaimsAgent", "ReportingAgent"]`. See [phase7_design.md § Chat Frontend](phase7_design.md#chat-frontend) for detail.

---

## Phase 8 — Semantic Query Cache (Layer 3) ✅ COMPLETE (2026-06-23)

**Goal:** Catch paraphrased repeat queries (synonyms, abbreviations, rewording) that Layer 2's exact-text-match cache misses — e.g. "total payments in ohio" vs "...in OH" — without ever risking a wrong answer served from a merely-similar cached response.

**Design:** See [docs/phase8_design.md](phase8_design.md).

**Decisions confirmed before implementation:**

- Embeddings: local model (`sentence-transformers`, `all-MiniLM-L6-v2`) — no new vendor/API key, consistent with this project depending only on Anthropic for AI.
- Scope: all 6 domain agents (no carve-out for ClinicalAgent).
- **Zero-false-positive design principle:** embedding similarity only ever produces a *candidate*; a candidate is never served without a dedicated, strict Claude Haiku verification call (`verify_equivalence()`) that defaults to "NO" on any doubt about scope, filters, time period, or interpretation. No similarity-only shortcut exists, even at very high scores.

**Live-testing finding (not the original speculative value):** the design originally specified a `0.85` similarity floor; live calibration against the real model found the motivating "ohio" vs "OH" paraphrase only scores **0.825** — a `0.85` floor would have missed the exact case this phase exists to catch. Floor lowered to **`0.80`**. Also found that a negation ("...NOT made in ohio") scores **0.9495** — *higher* than the true paraphrase — and was live-verified to reach `verify_equivalence()` and be correctly rejected there. Full numbers in `docs/phase8_design.md`.

### Tasks

- [x] `requirements.txt` — add `sentence-transformers`
- [x] `agents/embeddings.py` — lazy-loaded local model singleton, `embed(text) -> np.ndarray` (unit-normalized)
- [x] `sql/13_semantic_cache.sql` — idempotent `ALTER TABLE dw.QueryCache ADD Embedding VARBINARY(MAX) NULL`
- [x] `agents/cache.py` — `cache_set()` also stores the query's embedding (fails soft on write); new `cache_get_semantic(agent_name, query)` (brute-force cosine scan over non-expired, non-null-embedding rows for that agent, `SIMILARITY_FLOOR = 0.80`); new `verify_equivalence(client, new_query, candidate_query)` (Haiku call, fail-closed parsing); `HEALTHCAREADK_SEMANTIC_CACHE_ENABLED` env-var kill switch (default `"1"`)
- [x] `agents/orchestrator.py:_dispatch()` — semantic-candidate + verify step inserted between the exact-match check and the budget check; on a verified hit, appends a transparency note to the returned text
- [x] `tests/test_phase6.py` — extended the `_no_real_cache` autouse fixture to also patch `cache_get_semantic`/`verify_equivalence`; new `TestSemanticCache` + `TestSemanticCacheScoring` classes (18/18 passing)
- [x] Deployed `sql/13_semantic_cache.sql`; live-tested: ohio/OH semantic hit (zero new FinancialAgent rows in `dw.AgentUsageLog`), negation near-miss correctly rejected by `verify_equivalence()` despite clearing the floor, kill switch confirmed to skip the DB entirely
- [x] Updated `docs/phase8_design.md`, `CLAUDE.md` (phase table + short blurb), `README.md` (new dependency, one-time model download note)

**Explicitly deferred:** per-agent opt-out config (not needed — scope is all 6 agents by decision), a real vector index (unnecessary at this scale), logging verification-call token cost as its own `dw.AgentUsageLog` line item.
