# HealthcareADK — Phase 7 Design: Smart Caching + Chat Frontend

## Goal

Reduce token spend on repeated queries and expose the multi-agent system through a chat interface suitable for end-user consumption.

---

## Caching Architecture

Two complementary layers. Layer 1 is always active; Layer 2 is checked first and bypasses the API entirely on a hit.

```
User Request
     │
     ▼
[Layer 2] dw.QueryCache lookup  ──hit──► Return cached response (0 tokens)
     │ miss
     ▼
OrchestratorAgent
     │
     ▼
Domain Agent → Claude API call
     │         [Layer 1: system prompt cached by Anthropic — ~90% cheaper on cache hit]
     ▼
Response → write to dw.QueryCache with TTL
     │
     ▼
Return to user
```

---

## Layer 1 — Anthropic Prompt Caching

**Status:** ✅ Implemented in `agents/_base.py`, live-tested 2026-06-20 — **only benefits 2 of 7 agents** (see measured results below). Shipped anyway: it's a no-op (not a regression) for the other 5, costs nothing extra, and starts paying off automatically if their tool lists grow.

**What it does:** Marks the system prompt block with `cache_control: {"type": "ephemeral"}`. Anthropic caches the *cumulative prefix* (tool definitions + system prompt) for 5 minutes. On a cache hit, those tokens cost ~10% of normal.

**Where:** `agents/_base.py` — `client.messages.create()` call. The `system` parameter is a list with a cache_control block instead of a plain string:

```python
system=[{
    "type": "text",
    "text": config["system_prompt"],
    "cache_control": {"type": "ephemeral"},
}]
```

**Measured results (not the original estimate):** The original draft of this doc assumed all system prompts (300–800 tokens) would benefit, citing Anthropic's commonly-quoted 1024-token minimum. Live testing against the real `claude-sonnet-4-6` account showed the actual cacheable-prefix minimum for this account sits somewhere between ~1292 and ~1398 tokens — higher than the commonly-cited figure, and not explained by total `input_tokens` alone (confirmed via the `count_tokens` endpoint and repeated identical calls, ruling out flakiness):

| Agent | System+tools tokens | Caches? |
| --- | --- | --- |
| ClaimsAgent | 1,292 | ❌ No |
| FinancialAgent | 1,233 | ❌ No |
| ProviderAgent | 1,227 | ❌ No |
| ETLAgent | 1,236 | ❌ No |
| ClinicalAgent | 1,398 | ✅ Yes — `cache_read_input_tokens=1072` on repeat |
| ReportingAgent | 1,515 | ✅ Yes — `cache_read_input_tokens=1189` on repeat |
| OrchestratorAgent (routing call) | ~331, no tools sent | ❌ No |

So 4 of 6 domain agents plus the orchestrator's routing call get **zero** benefit from Layer 1 as currently scoped — their combined system+tools content is real but just under whatever this account's true cacheable-prefix floor is. Padding their prompts purely to cross that floor would be counterproductive (adds real tokens to every call to maybe save tokens on a cache hit). The code is left in place because it's harmless for the agents below threshold and immediately effective for the two above it — and because Layer 2 (below) provides universal savings regardless of size.

**Observability:** `response.usage.cache_read_input_tokens` is logged to `dw.AgentUsageLog` via the new `CachedTokens INT DEFAULT 0` column (`sql/09_agent_usage_log.sql`), surfaced in `rpt.vw_AgentUsage` as `CachedTokens` + a computed `CacheHitPct`, and in `dw.usp_GetAgentUsage`'s rollup as `TotalCachedTokens`.

---

## Layer 2 — Response Cache (SQL Server)

**Status:** ✅ Implemented and live-tested 2026-06-20. Unlike Layer 1, this benefits **all 7 agents uniformly** — there's no minimum-size threshold, so it's the layer that actually matters for cost reduction across ClaimsAgent/FinancialAgent/ProviderAgent/ETLAgent (the four that get nothing from Layer 1).

### `dw.QueryCache` Table (`sql/12_query_cache.sql`)

```sql
CREATE TABLE dw.QueryCache (
    CacheID      INT IDENTITY(1,1) PRIMARY KEY,
    CacheKey     CHAR(64)      NOT NULL,        -- SHA-256 hex of agent_name + normalized query
    AgentName    VARCHAR(50)   NOT NULL,
    Query        VARCHAR(2000) NOT NULL,
    Response     NVARCHAR(MAX) NOT NULL,
    CreatedAt    DATETIME2     NOT NULL DEFAULT SYSDATETIME(),
    ExpiresAt    DATETIME2     NOT NULL,
    INDEX IX_QueryCache_Key (CacheKey, ExpiresAt)
);
```

`agent_orchestrator` is the only login granted `SELECT, INSERT, DELETE` on this table — cache reads/writes/invalidation are centralized in `agents/cache.py`, rather than granting every domain agent its own DELETE rights. Connects via SQL auth (`UID=agent_orchestrator`), consistent with the rest of the agent fleet — no `Trusted_Connection`.

### Cache Key (`agents/cache.py`)

```python
import hashlib
key = hashlib.sha256(f"{agent_name}::{query.strip().lower()}".encode()).hexdigest()
```

### TTL Per Agent

Configured in each `agents/config/*.yaml` as `cache_ttl_minutes` (read by the orchestrator via `config.get("cache_ttl_minutes", 30)`):

| Agent | TTL | Rationale |
| --- | --- | --- |
| ETLAgent | 15 min | ETL state changes on every pipeline run |
| ClinicalAgent | 15 min | Lab/prescription data updated frequently |
| ClaimsAgent | 30 min | Claims volume changes intra-day |
| ProviderAgent | 30 min | Provider metrics relatively stable intra-day |
| FinancialAgent | 60 min | YoY/KPI numbers change only on ETL runs |
| ReportingAgent | 60 min | View definitions rarely change |

OrchestratorAgent's own routing call is never cached — routing decisions must reflect the current request, not a 30-minute-stale one.

### Cache Flow (`agents/orchestrator.py:_dispatch()`)

The cache check lives inside `_dispatch()` itself (not a separate wrapper around it), so it applies uniformly to both single-agent and multi-hop dispatch — each leg of a multi-hop request is checked/cached independently, keyed by its own `(agent_name, query)` pair:

```python
def _dispatch(agent_name, user_request, session_id, client):
    cached = cache_get(agent_name, user_request)
    if cached is not None:
        return cached                              # 0 tokens, instant — budget check never runs

    budget_msg = _check_budget(agent_name, session_id)
    if budget_msg:
        return f"[OrchestratorAgent] {budget_msg}"

    result = module.run(user_request, session_id, client)

    config = _load_config(module_key)
    cache_set(agent_name, user_request, result, config.get("cache_ttl_minutes", 30))

    if agent_name == "ETLAgent":
        cache_invalidate(["ETLAgent", "ClinicalAgent"])

    return result
```

### Cache Invalidation

Triggered from `orchestrator.py` itself (not `etl_agent.py` as originally sketched) immediately after a successful ETLAgent dispatch — this avoids needing to grant `agent_etl` its own DELETE rights on `dw.QueryCache`, keeping cache ownership centralized in the orchestrator.

### Live verification (2026-06-20)

- Identical query run twice via `python -m agents.orchestrator`: second call returned byte-identical output, `dw.AgentUsageLog` showed only **1** row for the session (the domain agent's `client.messages.create` was never invoked on the hit), and `dw.QueryCache.ExpiresAt` matched `CreatedAt + 30 min` exactly (ClaimsAgent's configured TTL).
- ETLAgent dispatch confirmed to purge `ClinicalAgent`'s cache row (count went 1 → 0 immediately after).

---

## Layer 1 + Layer 2 Combined Savings Estimate

Layer 1's effect is agent-dependent (see measured results above) — ClinicalAgent/ReportingAgent get the discount shown below; ClaimsAgent/FinancialAgent/ProviderAgent/ETLAgent currently get none from Layer 1 and rely entirely on Layer 2.

| Scenario | Without caching | With Layer 1 only (Clinical/Reporting) | With Layer 1 only (other 4 agents) | With Layer 1 + Layer 2 |
| --- | --- | --- | --- | --- |
| Same query repeated in 5 min | 100% tokens | ~20% tokens | 100% tokens | 0 tokens |
| Same query repeated in 30 min | 100% tokens | 100% tokens | 100% tokens | 0 tokens (within TTL) |
| New query, warm cache | 100% tokens | ~20% tokens (system+tools) | 100% tokens | ~20% / 100% (agent-dependent) |

Layer 2 is the layer that benefits all 7 agents uniformly — it's the higher-priority piece for actual cost reduction here.

---

## Chat Frontend

**Status:** ✅ Implemented and live-tested 2026-06-20.

### API Layer (`api/`)

**FastAPI** wraps `agents.orchestrator.run_with_meta()` (not `run()`) with a single endpoint, since the chat API needs the agent list and the resolved session_id, not just the response text. `run()` is kept as a thin wrapper around `run_with_meta()` for the CLI and existing tests — its signature didn't change.

```
POST /chat
Body: {"message": "...", "session_id": "..." | null}
Response: {"response": "...", "session_id": "...", "agents": ["..."]}
```

- `session_id` is `null` on the first message; the server generates one and returns it. The client stores it (`localStorage`) and passes it back on every subsequent turn — this keeps budget tracking and Layer 2 caching scoped per user session.
- `/chat` is a **sync** endpoint (`def chat(...)`, not `async def`) so FastAPI runs it in its worker thread pool — `run_with_meta()` makes blocking Anthropic API and pyodbc calls and must not run on the event loop.
- CORS is wide open (`allow_origins=["*"]`) — fine for local dev where the frontend is opened via `file://` or a different local port, but should be tightened before any real deployment.

### Directory Structure (additions)

```
api/
├── main.py          ← FastAPI app, POST /chat, CORS, GET /health
└── models.py        ← ChatRequest / ChatResponse Pydantic models

frontend/
├── index.html       ← Chat UI shell (loads marked.js + DOMPurify from CDN)
├── app.js           ← Fetch /chat, render markdown, session persistence via localStorage
└── style.css        ← Minimal dark-theme chat styling
```

### Security note: markdown rendering

`marked.js` does not sanitize its HTML output, and chat responses are inserted via `innerHTML`. Since a response is ultimately LLM-generated text that could echo back unusual content from the database, `app.js` runs every rendered response through **DOMPurify** before insertion (`DOMPurify.sanitize(marked.parse(text))`) to rule out script injection via a malicious or unexpected markdown/HTML payload.

### Running Locally

```powershell
pip install fastapi uvicorn
uvicorn api.main:app --reload --port 8000
# Open frontend/index.html directly in a browser (file:// works — CORS allows it)
```

### Bug found during live testing: redundant multi-hop dispatch

Testing the real chat UI surfaced a routing quality issue, not a frontend bug: `orchestrator.yaml`'s system prompt said "When the request spans multiple domains, list all relevant agents in priority order," which made the routing model over-eager. For *"How many patients were prescribed Amoxicillin in 2025 and who paid for them?"*, it dispatched **both** ClinicalAgent and ClaimsAgent — but `rpt.vw_Prescriptions` already joins in `PayerName`, `PayerType`, `CostToPayer`, `CostToPatient` (see `sql/06_rpt_views.sql`), so ClinicalAgent alone could fully answer the question. The result was two largely-overlapping tables concatenated into one oversized response.

**Fix:** `agents/config/orchestrator.yaml` now explicitly defaults to single-agent routing, calls out that ClinicalAgent's prescriptions/labs views already carry payer/cost columns, and instructs the router not to add ClaimsAgent just because a question mentions "paid" or "payer." Multi-hop is reserved for requests that genuinely need separate systems (the doc's own example — denial rate query + Power BI refresh — still correctly routes to `["ClaimsAgent", "ReportingAgent"]`, verified live after the prompt change).

This is a useful reminder for future routing-prompt edits: multi-hop responses are concatenated verbatim with no de-duplication, so an overly permissive router silently produces redundant, oversized answers rather than an obvious error.

---

## SQL Artifacts

| File | Purpose | Status |
| --- | --- | --- |
| `sql/12_query_cache.sql` | `dw.QueryCache` DDL + indexes + `agent_orchestrator` grants | ✅ Deployed |
| `sql/09_agent_usage_log.sql` | `CachedTokens INT DEFAULT 0` column (idempotent `ALTER`) | ✅ Deployed |
| `sql/11_agent_usage_views.sql` | `rpt.vw_AgentUsage` + `CacheHitPct`; `dw.usp_GetAgentUsage` rollup `TotalCachedTokens` | ✅ Deployed |

---

## Tasks

See [docs/plan.md § Phase 7](plan.md) for the full task checklist.
