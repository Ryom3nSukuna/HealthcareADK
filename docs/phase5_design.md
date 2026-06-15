# HealthcareADK — Phase 5 Design: Claude AI Layer

## Guiding Principle: Agents Edit Text, Not Binary Files

`.pbix` (Power BI) and `.dtsx` (SSIS) are binary or opaque formats — Claude cannot meaningfully edit them.
The architecture is designed so these files are thin deployment artifacts and all real logic lives in text files Claude controls.

---

## ETL Agent

**What it edits:** `.sql` files in `sql/` — stored procedures, views, staging transforms.

**Why this works:**
- `Package_Load_DW.dtsx` is a single `EXEC dw.usp_ETL_RunAll` call — all logic is in `sql/08_etl_stg_to_dw.sql`
- `Package_Load_Staging.dtsx` maps CSV columns to staging tables — rarely changes
- The ETL Agent never needs to touch a `.dtsx` file for routine changes

**How ETL Agent triggers a run:**
- Via MCP SQL Server tool: call stored procedures directly
- Via `dtexec` CLI (command line SSIS runner): trigger `Package_Master.dtsx` as a shell command
- Via SQL Server Agent Job: schedule or trigger a pre-configured job

**DB access scope:** Staging schema only (`stg.*`) — per agent permission model in CLAUDE.md.

---

## Reporting Agent (BI Agent)

**What it edits:** TMDL files in `powerbi/tmdl/` — plain text representation of the Power BI data model.

**Why TMDL:**
- `.pbix` is a binary ZIP — not editable by Claude
- TMDL (Tabular Model Definition Language) exports the entire Power BI data model as a folder of human-readable `.tmdl` text files (one per table, measures, relationships, etc.)
- Claude can read, diff, and edit TMDL files like any source file
- TMDL is deployed back to Power BI via the `pbi-tools` or Tabular Editor CLI

**Reporting Agent capabilities via Power BI REST API:**

| Task | Method |
|---|---|
| Refresh the dataset | `POST /datasets/{id}/refreshes` |
| Update parameters | `PATCH /datasets/{id}/parameters` |
| Check refresh status | `GET /datasets/{id}/refreshes` |
| Add/modify DAX measures | Edit `powerbi/tmdl/tables/_Measures.tmdl` → redeploy |
| Add a calculated column | Edit `powerbi/tmdl/tables/vw_ClaimsSummary.tmdl` → redeploy |

**DB access scope:** Read-only against `rpt.*` views — per agent permission model in CLAUDE.md.

---

## Source of Truth

| Layer | Source of truth | Deployment artifact |
|---|---|---|
| ETL logic | `sql/08_etl_stg_to_dw.sql` | `.dtsx` packages (built once in SSDT) |
| Power BI data model | `powerbi/tmdl/` | `.pbix` file |
| Power BI report visuals | `.pbix` file (human-built) | Deployed to Power BI Service |

> Report visuals (page layouts, charts, slicers) remain human-built in Power BI Desktop.
> Agents operate on the data model layer (measures, columns, relationships) and the data refresh layer (API).

---

## MCP Servers Required

| MCP Server | Purpose | Agent(s) | Status |
| --- | --- | --- | --- |
| `mcp-sqlserver` | Execute queries and SPs against HealthcareADK | All agents | ✅ Live |
| `mcp-shell` | Run `dtexec`, `pbi-tools deploy`, Python scripts | ETL Agent, Reporting Agent | ✅ Live (`mcp/shell/server.py`, 4 tools) |
| `mcp-file` | Read/write `.sql`, `.tmdl`, `.csv`, `.json` files | ETL Agent, Reporting Agent | ✅ Live (`mcp/file/server.py`, 4 tools) |
| `mcp-powerbi` | Trigger refresh, update parameters via REST API | Reporting Agent | Pending |

---

## mcp-shell Design

**Location:** `mcp/shell/server.py`

### Security Model: Allowlist

Shell execution is high-risk. `mcp-shell` uses an explicit allowlist — only registered executables can be called. Arbitrary shell strings are rejected.

### Tools

| Tool | Signature | Purpose |
| --- | --- | --- |
| `run_ssis_package` | `(package_path, config_path=None)` | Run an SSIS package via `dtexec` |
| `run_python_script` | `(script_name, args=[])` | Run a script from `scripts/` directory |
| `run_pbi_tools` | `(subcommand, args=[])` | Run `pbi-tools` (deploy, extract, etc.) |
| `run_sql_script` | `(script_path)` | Run a `.sql` file via `sqlcmd` against HealthcareADK |

### Allowlisted Executables

```python
ALLOWED_EXECUTABLES = {"dtexec", "python", "pbi-tools", "sqlcmd"}
```

### Path Scoping

- `run_python_script` — resolves relative to `scripts/` only; `..` traversal rejected
- `run_ssis_package` — resolves relative to `ssis/` only
- `run_sql_script` — resolves relative to `sql/` only
- `run_pbi_tools` — no path args (subcommand + flags only)

### Return Format

All tools return `{"returncode": int, "stdout": str, "stderr": str}`.

---

## mcp-file Design

**Location:** `mcp/file/server.py`

### Security Model: Extension Allowlist + Root Containment

File I/O is scoped to the project root. Only explicitly permitted extensions may be read or written.

### Tools

| Tool | Signature | Purpose |
| --- | --- | --- |
| `read_file` | `(path)` | Read a text file; path relative to project root |
| `write_file` | `(path, content)` | Write/overwrite a file; creates parent dirs as needed |
| `list_files` | `(directory=".", extension=None)` | List files recursively; optional extension filter |
| `append_file` | `(path, content)` | Append to a file; creates it if it doesn't exist |

### Allowed Extensions

```python
ALLOWED_EXTENSIONS = {".sql", ".tmdl", ".csv", ".json", ".md", ".py"}
```

### Response Format

- `read_file` → `{"content": str}`
- `write_file` → `{"written": int}` (bytes)
- `list_files` → `{"files": [{"path": str, "size": int, "modified": str}]}`
- `append_file` → `{"appended": int}` (bytes)
- All tools → `{"error": str}` on failure

### Primary Use Cases

| Agent | Reads | Writes |
| --- | --- | --- |
| ETLAgent | `sql/` stored procedures | Updated SP logic |
| ReportingAgent | `powerbi/tmdl/` TMDL files | Updated measures, columns |

---

## Tasks

- [x] Set up MCP server: `mcp-sqlserver` ✅
- [x] Set up MCP server: `mcp-shell` ✅
- [x] Set up MCP server: `mcp-file` ✅
- [ ] Set up MCP server: `mcp-powerbi` ⏸ (deferred — Power BI Service requires work/school account)
- [x] Export Power BI data model to TMDL format → save to `powerbi/tmdl/` ✅
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
- [x] Test Claude querying DW via natural language → SQL → result ✅
- [x] Test Reporting Agent: DAX measure change via TMDL ✅ (deploy to Desktop pending mcp-powerbi / manual ALM step)
