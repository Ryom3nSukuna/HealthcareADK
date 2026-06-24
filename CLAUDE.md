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
| 7 | Smart Caching + Chat Frontend | ✅ Complete (2026-06-20) |
| 8 | Semantic Query Cache (Layer 3) | ✅ Complete (2026-06-23) |

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
| PreToolUse | `mcp__file__write_file` | `guard_file_write.py` | Block path traversal, credential file writes, and writes outside `powerbi/tmdl/`/`sql/` |
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

Each domain agent connects to SQL Server as its own login (`agent_claims`, `agent_etl`, etc. — `db_login` in `agents/config/*.yaml`), not a shared trusted connection, so the schema-level GRANT/DENY rules in `sql/10_agent_permissions.sql` are enforced by SQL Server itself, not just by which tools an agent's config exposes.

---

## Smart Caching (Phase 7)

Two layers, both checked in `agents/orchestrator.py:_dispatch()`:

| Layer | What | Where | Coverage |
| --- | --- | --- | --- |
| 1 — Prompt caching | `cache_control: ephemeral` on each agent's system prompt | `agents/_base.py` | Only ClinicalAgent + ReportingAgent cross the real cacheable-prefix minimum (~1300–1400 tokens) — see `docs/phase7_design.md` |
| 2 — Response cache | `dw.QueryCache`, keyed by `SHA256(agent_name + query)`, per-agent TTL | `agents/cache.py` | All 7 agents — checked before the budget check, so a hit costs 0 tokens |

ETLAgent dispatch invalidates the `ETLAgent` + `ClinicalAgent` cache entries so stale pre-load answers aren't served after a fresh ETL run. Cache reads/writes/invalidation are centralized through `agent_orchestrator`'s own SQL login (`dw.QueryCache` grants live in `sql/12_query_cache.sql`).

---

## Semantic Caching (Phase 8)

A third cache layer, checked only on a Layer 2 exact-match miss inside `agents/orchestrator.py:_dispatch()`: embed the query locally (`sentence-transformers`, `all-MiniLM-L6-v2`), find the best cosine-similarity candidate in `dw.QueryCache` (`agents/cache.py:cache_get_semantic()`), then require a mandatory Claude Haiku equivalence check (`verify_equivalence()`) before ever serving it — a candidate is never reused on similarity score alone. Fails closed at every stage. `SIMILARITY_FLOOR` (`0.80`) was set from live measurement, not guessed — the motivating "ohio" vs "OH" paraphrase scores 0.825, and a negation scores *higher* (0.9495) than the true paraphrase, which is exactly why the floor only ever produces a candidate and `verify_equivalence()` is the sole authority on reuse. See `docs/phase8_design.md` for the full design and live-test results, and `docs/plan.md § Phase 8` for the task checklist.

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
├── .gitignore
├── .mcp.json                  ← MCP server registry (points into client/mcp/)
│
├── engine/                    ← REUSABLE FRAMEWORK — zero domain knowledge
│   │                             Copy wholesale to any new client; never edit for domain reasons
│   ├── base.py                ← Shared agentic loop (tool execution, iteration cap, budget recording)
│   ├── budget_tracker.py      ← Token usage logger → dw.AgentUsageLog
│   ├── cache.py               ← Layer 2 response cache + Layer 3 semantic cache
│   └── embeddings.py          ← Layer 3: lazy sentence-transformers singleton, embed()
│
├── tests/                     ← Test suites (no DB needed for unit tests)
│   ├── test_phase6.py         ← Unit tests: routing, multi-hop, budget, tool isolation, caching
│   └── test_permissions.py    ← Integration tests: SQL Server schema permissions per agent login
│                                 Skipped unless HEALTHCAREADK_TEST_PERMISSIONS=1
│
└── client/                    ← CLIENT-PACK — healthcare domain
    │                             Replace this entire directory for a new client domain
    ├── agents/
    │   ├── config/            ← Agent YAML configs (system prompt, tool allowlist, schema scope, token budget)
    │   ├── loader.py          ← load_config() helper — loads YAML from client/agents/config/
    │   ├── tools/
    │   │   ├── sql_tools.py   ← pyodbc SQL tools + Anthropic API definitions (all SQL agents)
    │   │   ├── file_tools.py  ← File I/O tools + write guard (ReportingAgent)
    │   │   └── shell_tools.py ← Subprocess tools: dtexec, python, pbi-tools, sqlcmd (ETL + Reporting)
    │   ├── orchestrator.py    ← OrchestratorAgent: routes requests, enforces budgets, merges multi-hop results
    │   ├── claims_agent.py    ← ClaimsAgent
    │   ├── clinical_agent.py  ← ClinicalAgent
    │   ├── financial_agent.py ← FinancialAgent
    │   ├── reporting_agent.py ← ReportingAgent
    │   ├── etl_agent.py       ← ETLAgent
    │   ├── provider_agent.py  ← ProviderAgent
    │   └── skills/            ← Skill specs: claims-summary, financial-yoy, abnormal-labs
    ├── api/
    │   ├── main.py            ← FastAPI app: POST /chat, GET /health, serves frontend/
    │   └── models.py          ← ChatRequest / ChatResponse Pydantic models
    ├── frontend/
    │   ├── index.html         ← Chat UI shell (marked.js + DOMPurify via CDN)
    │   ├── app.js             ← Fetch /chat, render + sanitize markdown, session persistence
    │   └── style.css          ← Minimal dark-theme chat styling
    ├── mcp/
    │   ├── sqlserver/         ← mcp-sqlserver (FastMCP, 9 tools) ✅ Live
    │   ├── shell/             ← mcp-shell (FastMCP, 4 tools) ✅ Live
    │   ├── file/              ← mcp-file (FastMCP, 4 tools) ✅ Live
    │   └── powerbi/           ← mcp-powerbi (FastMCP, 4 tools) ⏸ Deferred
    ├── sql/                   ← DDL, stored procedures, views (00–13)
    ├── scripts/               ← ETL and utility scripts
    │   ├── deploy_agent_logins.py ← Creates SQL Server logins from env vars (no passwords in source)
    │   ├── build_schema_kb.py     ← Rebuilds client/docs/schema_kb.json RAG index
    │   ├── generate_all.py        ← Synthetic data generation
    │   └── hooks/             ← Claude hook scripts
    │       ├── guard_file_read.py  ← Block reads of .env / credential files
    │       ├── guard_file_write.py ← Block writes outside powerbi/tmdl/ and sql/
    │       ├── guard_query.py      ← Block DML/DDL on dw.*, DELETE without WHERE
    │       ├── on_data_drop.py     ← Auto-run ETL after generate_all.py
    │       ├── on_ssis_complete.py ← Query dw.ETLLog after SSIS run
    │       └── on_pbi_deploy.py    ← Surface pbi-tools output
    ├── docs/
    │   ├── plan.md            ← Detailed phase plan
    │   ├── phase5_design.md   ← Phase 5 architecture
    │   ├── phase6_design.md   ← Phase 6 architecture
    │   ├── phase7_design.md   ← Phase 7 architecture
    │   ├── phase8_design.md   ← Phase 8 architecture
    │   └── schema_kb.json     ← RAG knowledge base (gitignored — rebuilt from live DB)
    ├── powerbi/
    │   ├── tmdl/              ← TMDL export (source of truth for data model)
    │   └── *.md               ← Design guides and DAX reference
    ├── ssis/                  ← SSIS package design guides
    └── landing_zone/          ← Raw data drop zone (gitignored)
```

---

## Claude Behavior in This Project
- Always reference domain context (healthcare) when making architectural suggestions.
- Do not generate code until the relevant phase is explicitly approved.
- Prefer concise, targeted tool calls — respect token budgets.
- When an agent boundary question arises, default to more restrictive access.
- All ETL logic must go through the staging layer — never write directly to DW from raw.
