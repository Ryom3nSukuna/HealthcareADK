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

### Cache Key

```python
import hashlib
key = hashlib.sha256(f"{agent_name}::{query.strip().lower()}".encode()).hexdigest()
```

### TTL Per Agent

Configured in each `agents/config/*.yaml` as `cache_ttl_minutes`:

| Agent | TTL | Rationale |
| --- | --- | --- |
| ETLAgent | 15 min | ETL state changes on every pipeline run |
| ClinicalAgent | 15 min | Lab/prescription data updated frequently |
| ClaimsAgent | 30 min | Claims volume changes intra-day |
| ProviderAgent | 30 min | Provider metrics relatively stable intra-day |
| FinancialAgent | 60 min | YoY/KPI numbers change only on ETL runs |
| ReportingAgent | 60 min | View definitions rarely change |
| OrchestratorAgent | 30 min | Default for schema lookups |

### Cache Flow in Orchestrator

```python
# Before dispatch
cached = cache_get(agent_name, query)
if cached:
    return cached          # 0 tokens, instant

# After dispatch
result = _dispatch(agent_name, query, session_id, client)
cache_set(agent_name, query, result, ttl_minutes)
return result
```

### Cache Invalidation

When ETLAgent runs successfully, flush stale entries:

```python
# In etl_agent.py after a successful run
cache_invalidate(["ETLAgent", "ClinicalAgent"])
```

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

### API Layer (`api/`)

**FastAPI** wraps `orchestrator.run()` with a single endpoint:

```
POST /chat
Body: {"message": "...", "session_id": "..."}
Response: {"response": "...", "session_id": "...", "agent": "..."}
```

- `session_id` is generated client-side on first message and passed back on every subsequent turn — this keeps budget tracking per user session working correctly
- Responses are markdown; the frontend renders them

### Directory Structure (additions)

```
api/
├── main.py          ← FastAPI app, POST /chat, CORS
└── models.py        ← ChatRequest / ChatResponse Pydantic models

frontend/
├── index.html       ← Chat UI shell
├── app.js           ← Fetch /chat, render markdown (marked.js)
└── style.css        ← Minimal styling
```

### Running Locally

```powershell
pip install fastapi uvicorn
uvicorn api.main:app --reload --port 8000
# Open frontend/index.html in browser (or serve via uvicorn static files)
```

---

## SQL Artifacts

| File | Purpose |
| --- | --- |
| `sql/12_query_cache.sql` | `dw.QueryCache` DDL + index |
| Update `sql/09_agent_usage_log.sql` | Add `CachedTokens INT DEFAULT 0` column |

---

## Tasks

See [docs/plan.md § Phase 7](plan.md) for the full task checklist.
