# HealthcareADK

An end-to-end agentic data architecture project built on the Healthcare domain.

## What This Is

A fully integrated data + AI system demonstrating:

- Synthetic healthcare data generation (CSV, JSON, Excel)
- SQL Server Data Warehouse with star schema modelling
- ETL pipelines (raw → staging → DW)
- Power BI dashboards and analytics (YoY, KPIs, trends)
- Claude-powered multi-agent architecture for insights and automation

## Architecture at a Glance

```
Raw Data (CSV/JSON/Excel)
        │
        ▼
   Landing Zone
        │
   [ETL Agent]
        │
        ▼
  Staging Schema
        │
   [ETL Agent]
        │
        ▼
  Data Warehouse (Star Schema)
   ┌────┴────┐
   │  Facts  │  Claims, Encounters, Prescriptions, Financials
   │  Dims   │  Patient, Provider, Date, Facility, Payer
   └────┬────┘
        │
   ┌────┴──────────────┐
   │                   │
[Power BI]      [Claude AI Layer]
Dashboards       RAG · MCP Servers
YoY · KPIs       Skills · Hooks
                 Multi-Agent System
```

## Agent System

Six domain agents coordinated by an OrchestratorAgent. Each agent is permission-scoped to its own data domain. Token budgets enforced per agent to control cost.

See [CLAUDE.md](CLAUDE.md) for full agent roles, guardrails, and behavior rules.

## Project Status

Phases 1–8 complete. Phase 8 (Semantic Query Cache, Layer 3) — see [docs/phase8_design.md](docs/phase8_design.md). Phase 9 documents the playbook for adding a new domain end-to-end (e.g. Admissions) — see [docs/phase9_design.md](docs/phase9_design.md). See [docs/plan.md](docs/plan.md) for the detailed phase breakdown.

---

## Setup

### Prerequisites

- SQL Server (Express or Developer edition) with **Mixed Mode Authentication enabled**
  - In SSMS: right-click the server → Properties → Security → select **SQL Server and Windows Authentication mode** → OK → restart the service when prompted
  - Required because Phase 6 agents connect using SQL logins (`agent_claims`, `agent_clinical`, etc.)
- Python 3.10+
- ODBC Driver 17 for SQL Server
- Power BI Desktop (optional — for Phase 4 report viewing)

### 1. Install Python dependencies

```powershell
pip install -r requirements.txt
```

> **Note (Phase 8):** `requirements.txt` includes `sentence-transformers` for the semantic query cache (Layer 3). It pulls in `torch`, and the first call to the embedding model (`all-MiniLM-L6-v2`) downloads it (~80MB) to your local Hugging Face cache — needs internet access once.

### 2. Create a `.env` file

All configuration is environment-variable driven — no hardcoded paths or credentials anywhere in source. Create `.env` in the project root (it is gitignored and Claude cannot read it):

```
# SQL Server connection (used by agents, MCP servers, and tests)
HEALTHCAREADK_SQL_SERVER=.\SQLEXPRESS
HEALTHCAREADK_SQL_DB=HealthcareADK

# Anthropic API key
ANTHROPIC_API_KEY=sk-ant-...

# Agent login passwords (needed for deploy_agent_logins.py and permission tests)
HEALTHCAREADK_PWD_AGENT_ORCHESTRATOR=your-strong-password
HEALTHCAREADK_PWD_AGENT_CLAIMS=your-strong-password
HEALTHCAREADK_PWD_AGENT_CLINICAL=your-strong-password
HEALTHCAREADK_PWD_AGENT_FINANCIAL=your-strong-password
HEALTHCAREADK_PWD_AGENT_REPORTING=your-strong-password
HEALTHCAREADK_PWD_AGENT_ETL=your-strong-password
HEALTHCAREADK_PWD_AGENT_PROVIDER=your-strong-password

# Permission test gate (set to 1 only when running test_permissions.py)
HEALTHCAREADK_TEST_PERMISSIONS=0
```

All scripts call `load_dotenv()` at startup so values are picked up automatically. The `.env` file is protected by two layers: `.gitignore` (never committed) and a `guard_file_read.py` PreToolUse hook that blocks Claude from reading it even if asked.

**PowerShell alternative** — if you prefer session-only vars without a file:

```powershell
$env:HEALTHCAREADK_SQL_SERVER = ".\SQLEXPRESS"
$env:HEALTHCAREADK_SQL_DB     = "HealthcareADK"
$env:ANTHROPIC_API_KEY        = "sk-ant-..."
$env:HEALTHCAREADK_PWD_AGENT_ORCHESTRATOR = "your-strong-password"
$env:HEALTHCAREADK_PWD_AGENT_CLAIMS       = "your-strong-password"
$env:HEALTHCAREADK_PWD_AGENT_CLINICAL     = "your-strong-password"
$env:HEALTHCAREADK_PWD_AGENT_FINANCIAL    = "your-strong-password"
$env:HEALTHCAREADK_PWD_AGENT_REPORTING    = "your-strong-password"
$env:HEALTHCAREADK_PWD_AGENT_ETL          = "your-strong-password"
$env:HEALTHCAREADK_PWD_AGENT_PROVIDER     = "your-strong-password"
$env:HEALTHCAREADK_TEST_PERMISSIONS       = "0"
```

### 3. Deploy the database

Run the SQL scripts in SSMS in order:

```
sql/00_create_database.sql
sql/01_create_schemas.sql
sql/02_stg_tables.sql
sql/03_dw_dim_date.sql
sql/04_dw_dimensions.sql
sql/05_dw_facts.sql
sql/06_rpt_views.sql
sql/07_stored_procedures.sql
sql/08_etl_stg_to_dw.sql
sql/09_agent_usage_log.sql
```

### 4. Create agent SQL Server logins

Passwords are never stored in source files. The deploy script reads them from env vars:

```powershell
python scripts/deploy_agent_logins.py
```

Then apply users, GRANTs, and DENYs in SSMS:

```
sql/10_agent_permissions.sql
sql/11_agent_usage_views.sql
sql/12_query_cache.sql
sql/13_semantic_cache.sql
```

### 5. Generate synthetic data and run ETL

```powershell
python scripts/generate_all.py   # populates landing_zone/
```

Then run the SSIS packages (see `ssis/SSIS_Design_Guide.md`) or call `EXEC dw.usp_ETL_RunAll` in SSMS after loading staging manually.

### 6. Run the chat UI (optional)

```powershell
uvicorn api.main:app --reload --port 8000
```

Then open `frontend/index.html` directly in a browser (no build step — `file://` works, CORS allows it). Type a question; the OrchestratorAgent routes it to the right domain agent(s) and the response renders as markdown.

---

## Testing

### Unit tests — no database or API key required

Tests the Python-level guardrails: agent routing, multi-hop dispatch, budget escalation, out-of-scope tool blocking, and the Layer 2 response cache (hit skips dispatch, miss writes with the agent's configured TTL). All Claude API calls and DB connections are mocked.

```powershell
pytest tests/test_phase6.py -v
```

### Integration tests — requires SQL deployed and agent logins created

Tests that each SQL Server agent login can only access its approved schemas and tables. Requires steps 3 and 4 above to be complete. Skipped automatically unless the env var is set.

```powershell
$env:HEALTHCAREADK_TEST_PERMISSIONS = "1"
pytest tests/test_permissions.py -v
```

Each test class maps to one agent login (`agent_claims`, `agent_clinical`, etc.) and verifies both what it **can** access and what it **cannot**.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Raw Data | Synthetic CSV / JSON / Excel |
| Database | SQL Server |
| ETL | Python / dbt (TBD) |
| BI | Power BI |
| AI | Claude (Anthropic) |
| Agent Framework | Claude Agent SDK + MCP |
| Caching | Anthropic prompt caching (`cache_control`) + SQL Server response cache (`dw.QueryCache`) + local-embedding semantic cache (`sentence-transformers` + Claude Haiku verification) |
| Chat API / Frontend | FastAPI + vanilla HTML/JS (marked.js + DOMPurify) |
| Dev Environment | VS Code + Claude Code |
