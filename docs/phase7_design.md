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

**What it does:** Marks the system prompt block with `cache_control: {"type": "ephemeral"}`. Anthropic caches the compiled prompt for 5 minutes. On a cache hit, input tokens for the system prompt cost ~10% of normal.

**Where:** `agents/_base.py` — `client.messages.create()` call. Change the `system` parameter from a plain string to a list with a cache_control block:

```python
system=[{
    "type": "text",
    "text": config["system_prompt"],
    "cache_control": {"type": "ephemeral"},
}]
```

**Savings:** System prompts are 300–800 tokens each. Every agent call within a 5-minute window pays ~10% on those tokens instead of 100%.

**Observability:** `response.usage` gains a `cache_read_input_tokens` field when the cache is hit. Log this to `dw.AgentUsageLog` via a new `CachedTokens INT DEFAULT 0` column (`sql/09_agent_usage_log.sql` update).

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

| Scenario | Without caching | With Layer 1 only | With Layer 1 + Layer 2 |
| --- | --- | --- | --- |
| Same query repeated in 5 min | 100% tokens | ~20% tokens | 0 tokens |
| Same query repeated in 30 min | 100% tokens | 100% tokens | 0 tokens (within TTL) |
| New query, warm cache | 100% tokens | ~20% tokens (system prompt) | ~20% tokens |

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
