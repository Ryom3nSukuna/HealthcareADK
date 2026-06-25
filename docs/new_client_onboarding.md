# New Client Onboarding Guide

How to replace the Healthcare client pack and point the engine at a new domain warehouse.

---

## The Engine / Client Split

The repository has two top-level directories that serve different purposes:

| Directory | Role | Rule |
|-----------|------|------|
| `engine/` | Reusable agentic framework — zero domain knowledge | **Never edit for domain reasons.** Copy wholesale to any new project. |
| `client/` | Healthcare domain pack — agents, SQL, MCP servers, frontend | **Replace entirely** for a new domain. |

The engine exposes three entry points that the client calls:

- `engine.base.run_agent(config, tools, request, session_id, client)` — runs a single agent's agentic loop
- `engine.budget_tracker.record/remaining/session_summary` — token usage logging
- `engine.cache.*` — Layer 2 (exact) + Layer 3 (semantic) response caching

Everything else — agents, SQL schema, MCP tools, prompts, permissions — lives in `client/` and is your responsibility to replace.

---

## What You Are Replacing

```
client/
├── agents/
│   ├── config/          ← one YAML per agent (system prompt, tools, budget, TTL)
│   ├── loader.py        ← unchanged — loads any YAML; no edits needed
│   ├── tools/           ← domain tool implementations (SQL, file, shell)
│   ├── orchestrator.py  ← one edit: AGENT_MODULE_MAP
│   ├── <agent>.py       ← one file per domain agent (4–10 lines each)
│   └── skills/          ← optional: skill specs for MCP-level queries
├── api/
│   ├── main.py          ← FastAPI app; update import paths for new module name
│   └── models.py        ← ChatRequest/ChatResponse — no changes needed
├── frontend/            ← drop-in replacement or keep as-is; no domain code
├── mcp/                 ← MCP server implementations; paths are self-healing
├── sql/                 ← domain DDL, ETL procedures, views, permissions
├── scripts/
│   ├── deploy_agent_logins.py ← update LOGINS list for your agents
│   └── hooks/           ← hook scripts are domain-agnostic; keep as-is
├── docs/                ← replace with your domain docs
├── powerbi/             ← replace with your domain reports
└── ssis/                ← replace with your domain ETL packages
```

---

## Step-by-Step

### 1. Copy the repository

```powershell
git clone <this-repo> <new-project>
cd <new-project>
```

Or, if starting from scratch: keep `engine/`, `tests/` (gut the test content), `CLAUDE.md`, `.claude/`, `.mcp.json`, and delete everything under `client/`.

---

### 2. Stand up your domain database

Create a SQL Server database for your new domain. The engine expects:

- A dedicated database name (goes in `HEALTHCAREADK_SQL_DB` → rename this var in your `.env`)
- A `dw.AgentUsageLog` table for budget tracking
- A `dw.QueryCache` table for Layer 2/3 caching
- An `agent_orchestrator` SQL Server login with SELECT/INSERT/DELETE on those two tables

The DDL for the last two is in `client/sql/09_agent_usage_log.sql`, `sql/12_query_cache.sql`, and `sql/13_semantic_cache.sql` — they are domain-agnostic and can be run against any database unchanged. The rest of the SQL (`00_` through `08_`) is healthcare-specific; replace it with your schema.

---

### 3. Decide on your agents

Typical pattern: one agent per major data domain, plus OrchestratorAgent.

Example for a Retail domain:

| Agent | Scope | DB login |
|-------|-------|---------|
| OrchestratorAgent | Routes only | `agent_orchestrator` |
| SalesAgent | Orders, revenue, promotions | `agent_sales` |
| InventoryAgent | Stock levels, warehouses | `agent_inventory` |
| CustomerAgent | Profiles, segments, churn | `agent_customer` |
| FinanceAgent | P&L, margins, budgets | `agent_finance` |

---

### 4. Create agent YAML configs

One YAML file per agent in `client/agents/config/`. Filename must be the snake_case version of the class name — `SalesAgent` → `sales_agent.yaml`.

**Template** (copy from any existing YAML and edit these fields):

```yaml
name: SalesAgent
description: Orders, revenue, channel mix, and promotion analysis.
model: claude-sonnet-4-6

system_prompt: |
  You are the SalesAgent for <Project>. You answer questions about...

  Always call search_schema before writing any SQL query to confirm column names.
  Present results as markdown tables. Keep responses concise.

  Scope rules:
  - Query only rpt.* views and the dw tables listed in db_tables below.
  - Never query stg.*, dw.Dim* tables outside the approved list, or any other schema.
  - Never issue INSERT, UPDATE, DELETE, DROP, CREATE, or ALTER statements.
  - If asked to modify data, respond: "SalesAgent is read-only. Escalate to ETLAgent."

allowed_tools:
  - mcp__sqlserver__execute_query
  - mcp__sqlserver__search_schema
  - mcp__sqlserver__get_schema
  - mcp__sqlserver__list_tables

db_login: agent_sales
db_schemas:
  - rpt
db_tables:
  - dw.FactOrders
  - dw.DimCustomer
  - dw.DimProduct
  - dw.DimDate

token_budget: 500000
cache_ttl_minutes: 30
```

Key rules:
- `allowed_tools` is enforced by `engine/base.py` — list only the MCP tool IDs the agent genuinely needs
- `db_login` matches the SQL Server login you will create in step 6
- `token_budget` is a per-session runaway guard, not a per-query limit; 500 000 is a safe default for Sonnet 4.6

Also create `orchestrator.yaml` — copy from the Healthcare version and rewrite:
- The list of domain agents and their scopes in `system_prompt`
- `db_login: agent_orchestrator` (unchanged)
- `token_budget: 150000` (unchanged)

---

### 5. Create agent Python files

Each domain agent is ~10 lines. Create `client/agents/<snake_name>.py`:

```python
from engine.base import run_agent
from client.agents.loader import load_config
from client.agents.tools.sql_tools import build_tools
from anthropic import Anthropic


def run(user_request: str, session_id: str, client: Anthropic) -> str:
    config = load_config("sales_agent")
    tools = build_tools(config["allowed_tools"], config["db_login"])
    return run_agent(config, tools, user_request, session_id, client)
```

No other changes needed per agent — all behaviour comes from the YAML config.

---

### 6. Update the orchestrator module map

In `client/agents/orchestrator.py`, update the two things that are domain-specific:

```python
# Line ~26: map class names → module filenames
AGENT_MODULE_MAP = {
    "SalesAgent":     "sales_agent",
    "InventoryAgent": "inventory_agent",
    "CustomerAgent":  "customer_agent",
    "FinanceAgent":   "finance_agent",
    "ETLAgent":       "etl_agent",
}
```

The rest of `orchestrator.py` (routing, cache layers, budget check, multi-hop merge) is domain-agnostic — leave it unchanged.

---

### 7. Deploy SQL Server agent logins

Update `LOGINS` in `client/scripts/deploy_agent_logins.py`:

```python
LOGINS = [
    ("agent_orchestrator", "MYPROJECT_PWD_AGENT_ORCHESTRATOR"),
    ("agent_sales",        "MYPROJECT_PWD_AGENT_SALES"),
    ("agent_inventory",    "MYPROJECT_PWD_AGENT_INVENTORY"),
    ("agent_customer",     "MYPROJECT_PWD_AGENT_CUSTOMER"),
    ("agent_finance",      "MYPROJECT_PWD_AGENT_FINANCE"),
    ("agent_etl",          "MYPROJECT_PWD_AGENT_ETL"),
]
```

The rest of the script (connection logic, idempotent CREATE/ALTER, password-in-memory approach) is domain-agnostic.

Run it after your `.env` is populated:

```powershell
python client/scripts/deploy_agent_logins.py
```

Then run your schema-permissions SQL in SSMS to create database users and apply GRANT/DENY per agent login.

---

### 8. Create your `.env`

```
# Database
MYPROJECT_SQL_SERVER=.\SQLEXPRESS
MYPROJECT_SQL_DB=MyProjectDB

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Chat API key
MYPROJECT_API_KEY=your-strong-api-key

# Agent passwords
MYPROJECT_PWD_AGENT_ORCHESTRATOR=...
MYPROJECT_PWD_AGENT_SALES=...
MYPROJECT_PWD_AGENT_INVENTORY=...
MYPROJECT_PWD_AGENT_CUSTOMER=...
MYPROJECT_PWD_AGENT_FINANCE=...
MYPROJECT_PWD_AGENT_ETL=...
```

If you rename the env var prefix (e.g. `HEALTHCAREADK_` → `MYPROJECT_`), update the matching `os.environ["..."]` references in:
- `engine/budget_tracker.py` — `HEALTHCAREADK_SQL_SERVER`, `HEALTHCAREADK_SQL_DB`, `HEALTHCAREADK_PWD_AGENT_ORCHESTRATOR`
- `client/api/main.py` — `HEALTHCAREADK_API_KEY`, `HEALTHCAREADK_CORS_ORIGINS`
- `client/agents/tools/sql_tools.py` — connection string env vars
- `client/mcp/sqlserver/server.py` — connection string env vars

Or keep the `HEALTHCAREADK_` prefix and just change the values — less churn, same result.

---

### 9. MCP servers — no code changes needed

The three MCP servers (`client/mcp/sqlserver/`, `client/mcp/shell/`, `client/mcp/file/`) resolve paths using `Path(__file__).resolve().parent.parent.parent`, which always points to the `client/` root regardless of domain. SQL schema names, tool implementations, and connection strings come from env vars or YAML configs.

The only change needed is in `.mcp.json` — already updated to `./client/mcp/*/server.py` and requires no further edits.

---

### 10. Update the chat API import paths

If you rename the project module (e.g. from `client` to something else — not recommended), update `client/api/main.py`:

```python
# Keep these two lines pointing to your orchestrator and models:
from client.agents.orchestrator import run_with_meta
from client.api.models import ChatRequest, ChatResponse
```

If the module stays `client`, no change needed.

---

### 11. Update CLAUDE.md

Rewrite the Agent Roles table, directory structure, and phase descriptions for your new domain. The guardrails section and Claude behavior rules are domain-agnostic and can stay as-is.

---

### 12. Run the tests

The unit tests in `tests/test_phase6.py` mock all DB and API calls. After updating the import paths for your new agent module names, they should pass without a live DB:

```powershell
pytest tests/test_phase6.py -v
```

The integration tests in `tests/test_permissions.py` verify schema-level DB isolation per agent login — run these after step 7:

```powershell
$env:MYPROJECT_TEST_PERMISSIONS = "1"
pytest tests/test_permissions.py -v
```

---

### 13. Start the server

```powershell
uvicorn client.api.main:app --reload --port 8000
```

Open `http://localhost:8000`. Type a question in your new domain. OrchestratorAgent routes it.

---

## What You Must Not Change in `engine/`

| File | Why it's off-limits |
|------|-------------------|
| `engine/base.py` | Shared agentic loop — tool execution, iteration cap, budget recording. Changes here affect every client. |
| `engine/budget_tracker.py` | Token logging and `remaining()` check. The path override (`HEALTHCAREADK_AGENT_CONFIG_DIR`) lets you remap config location without touching the file. |
| `engine/cache.py` | Layer 2 exact + Layer 3 semantic cache. All domain-specific values (TTL, agent name, query) are passed in as parameters. |
| `engine/embeddings.py` | Lazy sentence-transformers singleton. Model choice (`all-MiniLM-L6-v2`) is intentional — changing it silently invalidates all stored embeddings. |

The only legitimate reason to edit `engine/` is a framework-level bug fix or a new capability that benefits all clients.

---

## Checklist

- [ ] Domain database created and connection confirmed
- [ ] `dw.AgentUsageLog`, `dw.QueryCache`, and `dw.SemanticCache` (Embedding column) deployed
- [ ] Agent YAML configs created (one per agent + orchestrator)
- [ ] Agent `.py` files created (one per agent)
- [ ] `AGENT_MODULE_MAP` updated in `orchestrator.py`
- [ ] `LOGINS` list updated in `deploy_agent_logins.py`
- [ ] `deploy_agent_logins.py` run successfully
- [ ] Schema permissions SQL run in SSMS
- [ ] `.env` populated with all agent passwords
- [ ] Unit tests passing (`pytest tests/test_phase6.py -v`)
- [ ] Integration tests passing (`MYPROJECT_TEST_PERMISSIONS=1 pytest tests/test_permissions.py -v`)
- [ ] Server starts at `http://localhost:8000`
- [ ] First question routed correctly and answered
