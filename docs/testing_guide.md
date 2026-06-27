# HealthcareADK — End-to-End Testing Guide

Start the server from the repo root:

```powershell
python -m uvicorn client.api.main:app --reload --port 8000
```

Then open `http://localhost:8000`. Enter your `HEALTHCAREADK_API_KEY` (from `.env`) when prompted — stored in `localStorage`, prompt appears once per browser profile.

---

## 1 — Agent Routing (Phase 6)

**What it tests:** OrchestratorAgent routing each query to the correct domain agent.

| Query | Expected agent |
|-------|---------------|
| `Show me total claims billed for Texas in 2024` | ClaimsAgent |
| `What are the top 5 providers by patient volume?` | ProviderAgent |
| `Give me a year-over-year revenue breakdown` | FinancialAgent |
| `List the most recent abnormal lab results` | ClinicalAgent |
| `Run the ETL pipeline` | ETLAgent |

**Pass criteria:** Agent tag in the response matches the expected agent.

---

## 2 — Multi-Hop Routing (Phase 6)

**What it tests:** OrchestratorAgent dispatching to multiple agents and merging results.

> `Give me a summary of denied claims and the revenue impact for the same facilities`

**Pass criteria:** Response references both Claims and Financial data; agent tag lists both agents.

---

## 3 — Layer 2 Exact-Match Cache (Phase 7)

**What it tests:** `dw.QueryCache` exact-hash cache — a repeat query costs 0 new tokens.

1. Ask: `What is the total revenue for 2024?`
2. Ask the **exact same question** again.

**Pass criteria:** Second response returns noticeably faster. Confirm in SQL:

```sql
SELECT TOP 5 * FROM dw.AgentUsageLog ORDER BY LoggedAt DESC
```

No new row should appear for the second call.

---

## 4 — Layer 3 Semantic Cache (Phase 8)

**What it tests:** Sentence-transformer embedding + Haiku equivalence verification. A paraphrase gets answered from cache without dispatching the domain agent.

### 4a — True paraphrase (should hit cache)

1. Ask: `Show me total payments made in Ohio`
2. Ask: `What are total payments in OH?`

**Pass criteria:** Second response includes the banner:
> *(Answered using a cached response to a similar question: "...")*

### 4b — Structural paraphrase (longer vocabulary gap)

1. Ask: `Show me the total patients that are from New York.`
2. Ask: `How many patients are from the state of NY?`

**Pass criteria:** Same cache banner on second response. (This pair scores 0.798 — above the `SIMILARITY_FLOOR = 0.75` threshold.)

### 4c — False-positive guard: negation (Haiku must veto)

After 4a is cached:
> `Show me total payments NOT in Ohio`

**Pass criteria:** Fresh dispatch, no banner, different (lower) dollar figure.

### 4d — False-positive guard: same metric different year

1. Ask: `What was total revenue in 2023?`
2. Ask: `What was total revenue in 2024?`

**Pass criteria:** Second response is a fresh dispatch (no banner). Year difference must not be collapsed by similarity alone — Haiku veto catches it.

### 4e — False-positive guard: billed vs paid (one word, different meaning)

1. Ask: `Total claims billed by Medicaid`
2. Ask: `Total claims paid by Medicaid`

**Pass criteria:** Fresh dispatch on the second query. Dollar amounts will differ; banner must not appear.

### 4f — Kill switch

Set `HEALTHCAREADK_SEMANTIC_CACHE_ENABLED=0` in `.env`, restart the server, then repeat any paraphrase pair from 4a–4b.

**Pass criteria:** No cache banner; Layer 2 exact-match still works for identical queries.

---

## 5 — Hook Guards (Phase 5 + Phase 6 wiring via `engine/hook_runner.py`)

**What it tests:** Guard scripts enforced at agent runtime, not just in Claude Code CLI.

### 5a — Query safety (`guard_query.py`)

> `Delete all claims records`

**Pass criteria:** Response contains `Blocked by guard: DELETE without WHERE clause is not permitted` (or similar).

### 5b — File write restriction (`guard_file_write.py`)

> `Write a file called test.sql to the root of the project`

**Pass criteria:** ReportingAgent blocked — writes only allowed in `powerbi/tmdl/` and `sql/`.

### 5c — Credential file read (`guard_file_read.py`)

> `Read the .env file`

**Pass criteria:** Blocked with a credential-read denial message.

---

## 6 — Token Budget Enforcement (Phase 6/7)

**What it tests:** Mid-dispatch budget check in `engine/base.py:run_agent()`.

Verify budget config is in place:

```sql
SELECT AgentName, TokenBudget FROM dw.AgentBudget ORDER BY AgentName
```

To trigger: ask a deliberately verbose multi-step query to a low-budget agent and watch for:
> `[AgentName] Token budget (N tokens) exceeded mid-dispatch...`

---

## 7 — Skills (Phase 5, Claude Code CLI only)

**What it tests:** `.claude/commands/*.md` slash commands — only available in the Claude Code terminal, not the browser chat UI.

In a Claude Code terminal session:

```
/claims-summary payer=Medicare status=Denied
/financial-yoy start_year=2023 end_year=2024
/abnormal-labs flag=Critical top_n=50
```

**Pass criteria:** Each command calls the corresponding MCP tool and formats results as a markdown table per the skill spec in `client/agents/skills/`.

---

## 8 — API Key Authentication (Phase 7 security)

**What it tests:** `_require_api_key` dependency in `client/api/main.py`.

```powershell
# Should return 401
Invoke-RestMethod -Uri http://localhost:8000/chat -Method POST `
  -Headers @{"Content-Type"="application/json"} `
  -Body '{"message":"hello"}'

# Should succeed
Invoke-RestMethod -Uri http://localhost:8000/chat -Method POST `
  -Headers @{"Content-Type"="application/json"; "X-API-Key"="your_key_here"} `
  -Body '{"message":"hello"}'
```

---

## 9 — Health Check

```
GET http://localhost:8000/health
```

**Pass criteria:** `{"status": "ok"}`

---

## Similarity Floor Reference

Measured values for `all-MiniLM-L6-v2` (`SIMILARITY_FLOOR = 0.75`):

| Pair | Score | Result |
|------|-------|--------|
| "...in ohio" vs "...in OH" | 0.825 | Candidate (above floor) |
| "Show me total patients from New York" vs "How many from state of NY" | 0.798 | Candidate (above floor) |
| "...NOT in ohio" (negation) | 0.9495 | Candidate — Haiku vetoes |
| "...in Texas" vs "...in Ohio" | 0.7254 | Below floor, no Haiku call |
| "...claims denied" vs "...claims billed" (diff metric) | 0.6049 | Below floor, no Haiku call |
