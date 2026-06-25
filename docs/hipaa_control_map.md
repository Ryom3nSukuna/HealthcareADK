# HealthcareADK — HIPAA Security Rule Control Map

Maps every built feature to the HIPAA Security Rule safeguard (45 CFR Part 164) it satisfies.
All data in this project is **synthetic** — no real ePHI exists. The controls below demonstrate the
architecture a production deployment would require, and are implemented in full.

---

## Technical Safeguards — § 164.312

### Access Control — § 164.312(a)(1)

| Feature | File / Location | Safeguard |
|---------|----------------|-----------|
| Each agent connects as its own SQL Server login (`agent_claims`, `agent_clinical`, etc.) — no shared trusted connection | `client/agents/config/*.yaml` (`db_login`), `client/scripts/deploy_agent_logins.py` | **§ 164.312(a)(2)(i) Unique User Identification** — each agent identity is individually trackable in SQL Server audit logs |
| Schema-level GRANT/DENY per agent login — ClaimsAgent sees only `claims` schema, ClinicalAgent sees only `patients`/`labs`/`prescriptions`, etc. | `client/sql/10_agent_permissions.sql` | **§ 164.312(a)(1) Access Control** — minimum necessary access enforced by the database engine, not application logic |
| OrchestratorAgent uses its own login (`agent_orchestrator`) with access limited to `dw.QueryCache` and `dw.AgentUsageLog` | `engine/budget_tracker.py`, `client/agents/cache.py` | **§ 164.312(a)(1) Access Control** — coordination layer cannot read any clinical or financial ePHI directly |
| File write guard restricts writes to `powerbi/tmdl/` and `sql/` only — blocks any path-traversal attempt | `client/agents/tools/file_tools.py`, `client/mcp/file/server.py`, `client/scripts/hooks/guard_file_write.py` | **§ 164.312(a)(1) Access Control** — prevents agents from writing outside their designated directories |
| API key required on `POST /chat` — unauthenticated requests rejected with 401 | `client/api/main.py` | **§ 164.312(d) Person or Entity Authentication** |
| Session registry tracks active sessions; requests with unknown session IDs are rejected | `client/api/main.py` | **§ 164.312(a)(1) Access Control** — orphaned or replayed sessions cannot reuse an agent context |
| CORS origins restricted to `http://localhost:8000` (dev) and configurable via `HEALTHCAREADK_CORS_ORIGINS` env var | `client/api/main.py` | **§ 164.312(e)(1) Transmission Security** — browser-side network isolation prevents cross-origin data exfiltration |

---

### Audit Controls — § 164.312(b)

| Feature | File / Location | Safeguard |
|---------|----------------|-----------|
| Every agent call writes a row to `dw.AgentUsageLog` (agent name, session ID, input/output tokens, tool calls, model, timestamp) | `engine/budget_tracker.py`, `client/sql/11_agent_usage_log.sql` | **§ 164.312(b) Audit Controls** — full record of which agent accessed which resource in which session |
| `dw.QueryCache` records every cached query with `AgentName`, `Query`, `CachedAt`, `ExpiresAt` — a de facto query access log with TTL | `client/agents/cache.py`, `client/sql/12_query_cache.sql` | **§ 164.312(b) Audit Controls** — even cache hits leave a trace of what was asked |
| Hook `on_ssis_complete.py` queries `dw.ETLLog` after every SSIS run — surfaces rows loaded and any errors | `client/scripts/hooks/on_ssis_complete.py` | **§ 164.312(b) Audit Controls** — ETL activity is reviewed automatically, not silently swallowed |
| SQL query guard hook (`guard_query.py`) blocks DML/DDL on `dw.*` and DELETE without WHERE — enforced before every MCP query | `client/scripts/hooks/guard_query.py`, `.claude/settings.json` | **§ 164.312(c)(1) Integrity** — prevents bulk deletion or schema mutation of ePHI tables |

---

### Integrity — § 164.312(c)

| Feature | File / Location | Safeguard |
|---------|----------------|-----------|
| Semantic cache requires mandatory LLM equivalence verification (`verify_equivalence()`) before serving any cached response — fails closed; similarity score alone never authorizes reuse | `engine/cache.py` | **§ 164.312(c)(1) Integrity** — ensures cached answers are only reused when provably equivalent; prevents misleading outputs |
| `HEALTHCAREADK_SEMANTIC_CACHE_ENABLED` kill switch immediately disables Layer 3 without code change | `engine/cache.py` | **§ 164.312(c)(1) Integrity** — operational control to turn off a trust-sensitive feature if a false positive is ever observed |
| ETL always loads through the staging layer (`stg.*`) — never writes directly to `dw.*` from raw files | `client/sql/08_etl_stg_to_dw.sql`, ETLAgent YAML tool allowlist | **§ 164.312(c)(1) Integrity** — staged transformation provides a validation checkpoint before data reaches the warehouse |
| File read guard (`guard_file_read.py`) blocks reads of `.env` and credential files — Claude itself cannot exfiltrate secrets | `client/scripts/hooks/guard_file_read.py`, `.claude/settings.json` | **§ 164.312(c)(1) Integrity / § 164.312(d) Authentication** — secrets cannot leak through the AI layer |

---

### Person or Entity Authentication — § 164.312(d)

| Feature | File / Location | Safeguard |
|---------|----------------|-----------|
| API key (`HEALTHCAREADK_API_KEY`) stored only in `.env` — never committed to source control | `.gitignore` (blocks `.env`), `client/api/main.py` | **§ 164.312(d)** — client identity verified before any agent interaction |
| SQL Server agent logins authenticated by individual passwords (`HEALTHCAREADK_PWD_AGENT_*` env vars) — no Windows integrated auth sharing one identity | `client/scripts/deploy_agent_logins.py` | **§ 164.312(d)** — each agent has its own credential; a compromised single agent credential cannot impersonate another |

---

### Transmission Security — § 164.312(e)

| Feature | File / Location | Safeguard |
|---------|----------------|-----------|
| `ANTHROPIC_API_KEY` in `.env` only — never in source or logs | `.gitignore`, `client/api/main.py` | **§ 164.312(e)(2)(ii) Encryption** — API key protects data in transit to Anthropic; key itself is never exposed |
| SQL Server connection strings assembled from env vars at runtime — no hardcoded credentials anywhere in source | All agent `.yaml` configs, `engine/budget_tracker.py`, `client/agents/tools/sql_tools.py` | **§ 164.312(e)(2)(ii) Encryption** — credentials for database connections are not readable from the codebase |
| `sqlcmd` passwords passed via `SQLCMDPASSWORD` env var, never via `-P` CLI flag | `client/agents/tools/shell_tools.py` | **§ 164.312(e)(2)(ii) Encryption** — passwords do not appear in process argument lists or shell history |

---

## Administrative Safeguards — § 164.308

### Information Access Management — § 164.308(a)(4)

| Feature | File / Location | Safeguard |
|---------|----------------|-----------|
| Principle of least privilege documented and enforced: each agent's YAML `tool_allowlist` limits which tools it can call; SQL GRANT/DENY limits which schemas it can query | `client/agents/config/*.yaml`, `client/sql/10_agent_permissions.sql` | **§ 164.308(a)(4)(ii)(B) Access Authorization** |
| Agent roles defined and scope documented in CLAUDE.md | `CLAUDE.md` (Agent Roles table) | **§ 164.308(a)(4)(ii)(C) Access Establishment** — role boundaries are specified and version-controlled |

---

### Security Management Process — § 164.308(a)(1)

| Feature | File / Location | Safeguard |
|---------|----------------|-----------|
| Per-agent token budget in YAML config (`token_budget`) acts as a runaway-guard; orchestrator enforces it before dispatch and mid-loop | `client/agents/config/*.yaml`, `client/agents/orchestrator.py`, `engine/base.py` | **§ 164.308(a)(1)(ii)(B) Risk Management** — bounds the blast radius of a misbehaving agent |
| `dw.AgentUsageLog` enables post-hoc review of all agent activity for anomaly detection | `engine/budget_tracker.py` | **§ 164.308(a)(1)(ii)(D) Information System Activity Review** |
| Guard hooks run automatically on every relevant tool call — not an opt-in review step | `.claude/settings.json` PreToolUse hooks | **§ 164.308(a)(1)(ii)(B) Risk Management** — policy enforcement is structural, not procedural |

---

### Workforce Security — § 164.308(a)(3)

| Feature | File / Location | Safeguard |
|---------|----------------|-----------|
| `deploy_agent_logins.py` creates agent SQL logins from env vars — removing an env var and re-running effectively revokes an agent's DB access without touching source code | `client/scripts/deploy_agent_logins.py` | **§ 164.308(a)(3)(ii)(C) Termination Procedures** — agent credentials can be rotated or revoked independently |

---

## Physical Safeguards — § 164.310

Physical safeguards (workstation controls, device media controls, facility access) are out of scope for this software project and must be addressed by the hosting environment (cloud provider, on-premises data center) in a production deployment.

---

## Control Coverage Summary

| Safeguard Category | Rule Sections Addressed | Notes |
|--------------------|------------------------|-------|
| Technical — Access Control | § 164.312(a)(1), (a)(2)(i) | Schema-level DB isolation + API auth + session registry |
| Technical — Audit Controls | § 164.312(b) | `dw.AgentUsageLog`, `dw.QueryCache`, ETLLog hook |
| Technical — Integrity | § 164.312(c)(1) | Semantic cache fail-closed, ETL staging, query guard |
| Technical — Authentication | § 164.312(d) | Per-agent SQL logins + API key auth |
| Technical — Transmission Security | § 164.312(e)(1), (e)(2)(ii) | CORS, secrets in env vars only, `SQLCMDPASSWORD` |
| Administrative — Access Mgmt | § 164.308(a)(4)(ii)(B), (C) | YAML tool allowlist + SQL GRANT/DENY + CLAUDE.md roles |
| Administrative — Security Mgmt | § 164.308(a)(1)(ii)(B), (D) | Token budget guard + usage log + structural hooks |
| Administrative — Workforce | § 164.308(a)(3)(ii)(C) | Per-agent SQL credential rotation via env vars |
| Physical | § 164.310 | Delegated to hosting environment — out of scope for this codebase |
