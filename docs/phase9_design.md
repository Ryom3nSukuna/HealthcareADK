# HealthcareADK — Phase 9 Design: Extensibility Playbook (New Domain Walkthrough)

## Goal

Document the repeatable, ordered process for adding a brand-new domain to HealthcareADK end-to-end — raw data through Power BI through the Claude agent layer — using a hypothetical **Admissions** domain as the worked example.

**Status:** 📘 Documented — methodology only. No Admissions code ships in this phase; this is the checklist to follow if/when it (or any other new domain) is actually built.

---

## Context

The natural question once the core system is built is "what does adding a new domain look like end to end?" The answer touches almost every earlier phase of the project, but **only one of the six stages below actually involves writing new Claude agent code** — everything else is deterministic data engineering. That distinction matters: it's easy to assume "agentic system" means an LLM is involved at every step, and it isn't. This phase exists to make the real shape of the work explicit, stage by stage, so a new domain can be scoped accurately instead of guessed at.

---

## The six stages

### Stage 1 — Raw data (Phase 1 equivalent)

Extend `scripts/generate_all.py` (or add a sibling generator) to produce synthetic Admissions records into a new `landing_zone/admissions/` folder, plus a manifest entry. **Plain Python — not an agent.**

### Stage 2 — DW design (Phase 2 equivalent)

New DDL: `stg.Admissions` (mirrors the landing-zone shape) and `dw.FactAdmissions`, reusing existing dimensions (`DimPatient`, `DimFacility`, `DimProvider`, `DimDate`) rather than duplicating them. **SQL DDL — not an agent.**

### Stage 3 — ETL (Phase 3 equivalent)

A new load step inside `dw.usp_ETL_RunAll` (`sql/08_etl_stg_to_dw.sql`), staging → DW only, per the project's standing rule that ETL never writes directly to `dw.*` from raw. The SSIS package wrapper stays a thin `EXEC` call, consistent with every other domain. **T-SQL + a thin SSIS wrapper — not an agent.**

### Stage 4 — Power BI (Phase 4 equivalent)

A new `rpt.vw_Admissions` view, TMDL edits in `powerbi/tmdl/` to add the table/relationships/measures, then a human builds the report visuals in Desktop — Claude edits the TMDL text, never the `.pbix` binary, per the project's core principle (agents edit text, not binary files). **TMDL text + a human step — not an agent.**

### Stage 5 — Claude AI layer (Phase 5/6 equivalent) — **the only stage that touches an agent**

Two ways to expose Admissions to natural-language queries:

- **Option A — extend an existing agent.** Add `get_admissions_summary` as a new tool on ClinicalAgent or ReportingAgent. Fast, no new SQL login, no new YAML — but blurs that agent's schema scope, since its prompt and permissions were written around its original domain.
- **Option B — stand up a new AdmissionsAgent.** Own `agents/config/admissions_agent.yaml`, own scoped SQL login (`agent_admissions`), own GRANT/DENY rows in `sql/10_agent_permissions.sql`, registered in `agents/orchestrator.py`'s `AGENT_MODULE_MAP`. The agent module itself is cheap — every existing domain agent (e.g. `claims_agent.py`) is ~9 lines wrapping the shared `run_agent` loop.

**Recommendation: Option B.** The project's actual selling point is per-agent least-privilege SQL access (see `CLAUDE.md` § Agent Roles), and Option A quietly erodes that by widening an existing agent's reach beyond what its prompt and grants were designed for. Standing up a full seventh agent is the version that proves the architecture scales cleanly to a new domain — which is exactly what's worth demonstrating.

### Stage 6 — Wiring and docs

- Rerun `scripts/build_schema_kb.py` so `search_schema` and the RAG knowledge base know about the new tables.
- Add `agent_admissions` to `sql/10_agent_permissions.sql` (login + GRANT/DENY), following the existing pattern.
- Update `CLAUDE.md`'s Agent Roles table and Directory Structure listing.
- Update `README.md`'s setup steps if a new SQL deploy file is added.

---

## Worked example: Admissions build checklist (if/when actually built)

- [ ] `landing_zone/admissions/` + generator extension in `scripts/generate_all.py`
- [ ] `sql/02_stg_tables.sql` — `stg.Admissions`
- [ ] `sql/05_dw_facts.sql` — `dw.FactAdmissions`
- [ ] `sql/08_etl_stg_to_dw.sql` — new load step in `dw.usp_ETL_RunAll`
- [ ] `sql/06_rpt_views.sql` — `rpt.vw_Admissions`
- [ ] `powerbi/tmdl/` — new table, relationships, measures + manual report build in Desktop
- [ ] `agents/config/admissions_agent.yaml` + `agents/admissions_agent.py`
- [ ] `sql/10_agent_permissions.sql` — `agent_admissions` login + GRANT/DENY
- [ ] `agents/orchestrator.py` — `AGENT_MODULE_MAP` entry + orchestrator routing prompt update
- [ ] `scripts/build_schema_kb.py` rerun
- [ ] `CLAUDE.md` / `README.md` updates

---

## Explicitly deferred

Admissions itself is **not** being built in Phase 9 — this phase is the playbook only. Actually building it (or any other new domain) is future work, undertaken as its own phase if/when there's a reason to.

---

## Tasks

See [docs/plan.md § Phase 9](plan.md) for the task checklist.
