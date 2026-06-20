"""
SQL tool implementations for HealthcareADK domain agents.

Connection is read at call time from environment variables:
  HEALTHCAREADK_SQL_SERVER          — e.g. ".\\SQLEXPRESS"
  HEALTHCAREADK_SQL_DB              — e.g. "HealthcareADK"
  HEALTHCAREADK_PWD_<DB_LOGIN>      — e.g. HEALTHCAREADK_PWD_AGENT_CLAIMS

Each agent connects as its own SQL Server login (db_login in agents/config/*.yaml),
so the schema-level GRANT/DENY rules in sql/10_agent_permissions.sql are the real
enforcement boundary — the allowed_tools list is the first line of defense, not the only one.

Each tool is registered with its MCP tool name so agent configs can reference the
same allowed_tools list regardless of whether they run via MCP or the Python agent layer.
"""
import functools
import json
import os
import re
from pathlib import Path

import pyodbc
from dotenv import load_dotenv

load_dotenv()

_KB_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "schema_kb.json"
_kb_cache: dict | None = None


# ------------------------------------------------------------------
# Connection
# ------------------------------------------------------------------

def _get_conn(db_login: str) -> pyodbc.Connection:
    server = os.environ["HEALTHCAREADK_SQL_SERVER"]
    db = os.environ["HEALTHCAREADK_SQL_DB"]
    pwd = os.environ[f"HEALTHCAREADK_PWD_{db_login.upper()}"]
    conn_str = (
        "DRIVER={ODBC Driver 17 for SQL Server};"
        f"SERVER={server};DATABASE={db};UID={db_login};PWD={pwd};"
    )
    return pyodbc.connect(conn_str)


def _cursor_to_dict(cursor) -> dict:
    cols = [col[0] for col in cursor.description]
    rows = [list(r) for r in cursor.fetchmany(500)]
    return {"columns": cols, "rows": rows, "row_count": len(rows)}


# ------------------------------------------------------------------
# RAG helpers (search_schema)
# ------------------------------------------------------------------

def _load_kb() -> dict:
    global _kb_cache
    if _kb_cache is None and _KB_PATH.exists():
        _kb_cache = json.loads(_KB_PATH.read_text(encoding="utf-8"))
    return _kb_cache or {}


def _score(words: list[str], text: str) -> int:
    text_lower = text.lower()
    score = 0
    for word in words:
        if word == text_lower:
            score += 10
        elif re.search(rf"\b{re.escape(word)}\b", text_lower):
            score += 5
        elif word in text_lower:
            score += 2
    return score


# ------------------------------------------------------------------
# Tool functions
# ------------------------------------------------------------------

def _execute_query(db_login: str, sql: str) -> str:
    if not sql.strip().upper().startswith("SELECT"):
        return json.dumps({"error": "Only SELECT statements are allowed."})
    try:
        conn = _get_conn(db_login)
        cursor = conn.cursor()
        cursor.execute(sql)
        result = _cursor_to_dict(cursor)
        conn.close()
        return json.dumps(result, default=str, indent=2)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def _search_schema(db_login: str, query: str, top_n: int = 10) -> str:
    kb = _load_kb()
    if not kb:
        return json.dumps({"error": "Schema knowledge base not found. Run scripts/build_schema_kb.py first."})

    words = [w.lower() for w in re.split(r"\W+", query) if w]
    hits: list[dict] = []

    for _, schema_obj in kb.get("schemas", {}).items():
        for fqn, table in schema_obj.items():
            t_score = _score(words, table["name"]) + _score(words, table.get("description", ""))
            if t_score > 0:
                hits.append({"type": "table", "object": fqn, "description": table.get("description", ""), "score": t_score})
            for col in table.get("columns", []):
                c_score = _score(words, col["name"]) + _score(words, col.get("description", ""))
                if c_score > 0:
                    hits.append({"type": "column", "object": f"{fqn}.{col['name']}", "data_type": col["type"], "description": col.get("description", ""), "score": c_score})

    for sp_name, sp in kb.get("stored_procedures", {}).items():
        sp_score = _score(words, sp_name) + _score(words, sp.get("definition_preview", ""))
        if sp_score > 0:
            hits.append({"type": "procedure", "object": sp_name, "preview": sp.get("definition_preview", "")[:200], "score": sp_score})

    hits.sort(key=lambda h: h["score"], reverse=True)
    return json.dumps({"query": query, "results": hits[:top_n]}, indent=2)


def _get_claims_summary(
    db_login: str, start_date: str = None, end_date: str = None, payer_type: str = None,
    claim_status: str = None, state: str = None, top_n: int = 100,
) -> str:
    try:
        conn = _get_conn(db_login)
        cursor = conn.cursor()
        cursor.execute(
            "EXEC dw.usp_GetClaimsSummary @StartDate=?, @EndDate=?, @PayerType=?, @ClaimStatus=?, @State=?, @TopN=?",
            start_date, end_date, payer_type, claim_status, state, top_n,
        )
        result = _cursor_to_dict(cursor)
        conn.close()
        return json.dumps(result, default=str, indent=2)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def _get_financial_yoy(db_login: str, start_year: int = None, end_year: int = None, facility_id: str = None) -> str:
    try:
        conn = _get_conn(db_login)
        cursor = conn.cursor()
        cursor.execute(
            "EXEC dw.usp_GetFinancialYoY @StartYear=?, @EndYear=?, @FacilityID=?",
            start_year, end_year, facility_id,
        )
        result = _cursor_to_dict(cursor)
        conn.close()
        return json.dumps(result, default=str, indent=2)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def _get_provider_performance(db_login: str, year: int = None, specialty: str = None, state: str = None, top_n: int = 50) -> str:
    try:
        conn = _get_conn(db_login)
        cursor = conn.cursor()
        cursor.execute(
            "EXEC dw.usp_GetProviderPerformance @Year=?, @Specialty=?, @State=?, @TopN=?",
            year, specialty, state, top_n,
        )
        result = _cursor_to_dict(cursor)
        conn.close()
        return json.dumps(result, default=str, indent=2)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def _get_abnormal_labs(
    db_login: str, patient_id: str = None, start_date: str = None, end_date: str = None,
    flag_filter: str = None, top_n: int = 200,
) -> str:
    try:
        conn = _get_conn(db_login)
        cursor = conn.cursor()
        cursor.execute(
            "EXEC dw.usp_GetAbnormalLabResults @PatientID=?, @StartDate=?, @EndDate=?, @FlagFilter=?, @TopN=?",
            patient_id, start_date, end_date, flag_filter, top_n,
        )
        result = _cursor_to_dict(cursor)
        conn.close()
        return json.dumps(result, default=str, indent=2)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def _get_patient_timeline(db_login: str, patient_id: str, start_date: str = None, end_date: str = None) -> str:
    try:
        conn = _get_conn(db_login)
        cursor = conn.cursor()
        cursor.execute(
            "EXEC dw.usp_GetPatientTimeline @PatientID=?, @StartDate=?, @EndDate=?",
            patient_id, start_date, end_date,
        )
        result = _cursor_to_dict(cursor)
        conn.close()
        return json.dumps(result, default=str, indent=2)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def _get_schema(db_login: str, table: str, schema: str = "rpt") -> str:
    try:
        conn = _get_conn(db_login)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, IS_NULLABLE "
            "FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA=? AND TABLE_NAME=? ORDER BY ORDINAL_POSITION",
            schema, table,
        )
        cols = cursor.fetchall()
        conn.close()
        if not cols:
            return json.dumps({"error": f"No object found: {schema}.{table}"})
        return json.dumps({
            "table": f"{schema}.{table}",
            "columns": [{"name": c[0], "type": c[1], "max_length": c[2], "nullable": c[3]} for c in cols],
        }, indent=2)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def _list_tables(db_login: str, schema: str = "rpt") -> str:
    try:
        conn = _get_conn(db_login)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT TABLE_NAME, TABLE_TYPE FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA=? ORDER BY TABLE_TYPE, TABLE_NAME",
            schema,
        )
        tables = cursor.fetchall()
        conn.close()
        return json.dumps({"schema": schema, "objects": [{"name": t[0], "type": t[1]} for t in tables]}, indent=2)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


# ------------------------------------------------------------------
# Tool registry  (MCP tool name → Anthropic definition + fn)
# ------------------------------------------------------------------

TOOL_REGISTRY: dict[str, dict] = {
    "mcp__sqlserver__execute_query": {
        "definition": {
            "name": "execute_query",
            "description": "Run a read-only SELECT query against HealthcareADK. Returns up to 500 rows.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "sql": {"type": "string", "description": "SELECT query to execute"},
                },
                "required": ["sql"],
            },
        },
        "fn": _execute_query,
    },
    "mcp__sqlserver__search_schema": {
        "definition": {
            "name": "search_schema",
            "description": "Keyword search across tables, columns, and stored procedures. Call this before writing SQL.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search terms e.g. 'denial rate payer'"},
                    "top_n": {"type": "integer", "description": "Max results (default 10)"},
                },
                "required": ["query"],
            },
        },
        "fn": _search_schema,
    },
    "mcp__sqlserver__get_claims_summary": {
        "definition": {
            "name": "get_claims_summary",
            "description": "Get filtered claims via dw.usp_GetClaimsSummary. All parameters optional.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "start_date":   {"type": "string", "description": "YYYY-MM-DD"},
                    "end_date":     {"type": "string", "description": "YYYY-MM-DD"},
                    "payer_type":   {"type": "string", "description": "Commercial | Medicare | Medicaid | Self-Pay"},
                    "claim_status": {"type": "string", "description": "Approved | Denied | Pending | Appealed"},
                    "state":        {"type": "string", "description": "2-letter state code"},
                    "top_n":        {"type": "integer", "description": "Max rows (default 100)"},
                },
            },
        },
        "fn": _get_claims_summary,
    },
    "mcp__sqlserver__get_financial_yoy": {
        "definition": {
            "name": "get_financial_yoy",
            "description": "Year-over-year revenue vs expense via dw.usp_GetFinancialYoY. All parameters optional.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "start_year":   {"type": "integer", "description": "e.g. 2022"},
                    "end_year":     {"type": "integer", "description": "e.g. 2025"},
                    "facility_id":  {"type": "string", "description": "UUID to filter to one facility"},
                },
            },
        },
        "fn": _get_financial_yoy,
    },
    "mcp__sqlserver__get_provider_performance": {
        "definition": {
            "name": "get_provider_performance",
            "description": "Provider KPIs (claims, billed, paid, denial rate) via dw.usp_GetProviderPerformance.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "year":      {"type": "integer", "description": "e.g. 2024"},
                    "specialty": {"type": "string", "description": "e.g. Cardiology"},
                    "state":     {"type": "string", "description": "2-letter state code"},
                    "top_n":     {"type": "integer", "description": "Max rows (default 50)"},
                },
            },
        },
        "fn": _get_provider_performance,
    },
    "mcp__sqlserver__get_abnormal_labs": {
        "definition": {
            "name": "get_abnormal_labs",
            "description": "Abnormal and critical lab results via dw.usp_GetAbnormalLabResults.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "patient_id":   {"type": "string", "description": "UUID to filter to one patient"},
                    "start_date":   {"type": "string", "description": "YYYY-MM-DD"},
                    "end_date":     {"type": "string", "description": "YYYY-MM-DD"},
                    "flag_filter":  {"type": "string", "description": "High | Low | Critical"},
                    "top_n":        {"type": "integer", "description": "Max rows (default 200)"},
                },
            },
        },
        "fn": _get_abnormal_labs,
    },
    "mcp__sqlserver__get_patient_timeline": {
        "definition": {
            "name": "get_patient_timeline",
            "description": "Full care timeline (claims + labs + prescriptions) for one patient via dw.usp_GetPatientTimeline.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "string", "description": "REQUIRED — patient UUID"},
                    "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "end_date":   {"type": "string", "description": "YYYY-MM-DD"},
                },
                "required": ["patient_id"],
            },
        },
        "fn": _get_patient_timeline,
    },
    "mcp__sqlserver__get_schema": {
        "definition": {
            "name": "get_schema",
            "description": "Describe columns of a table or view in HealthcareADK.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "table":  {"type": "string", "description": "Table or view name e.g. vw_ClaimsSummary"},
                    "schema": {"type": "string", "description": "rpt | dw | stg (default rpt)"},
                },
                "required": ["table"],
            },
        },
        "fn": _get_schema,
    },
    "mcp__sqlserver__list_tables": {
        "definition": {
            "name": "list_tables",
            "description": "List all tables and views in a HealthcareADK schema.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "schema": {"type": "string", "description": "rpt | dw | stg (default rpt)"},
                },
            },
        },
        "fn": _list_tables,
    },
}


def build_tools(allowed_mcp_names: list[str], db_login: str) -> list[dict]:
    """Return tool dicts for the given MCP tool names, bound to db_login's SQL Server credentials
    (preserving order, silently skipping unknowns)."""
    return [
        {"definition": TOOL_REGISTRY[name]["definition"], "fn": functools.partial(TOOL_REGISTRY[name]["fn"], db_login)}
        for name in allowed_mcp_names
        if name in TOOL_REGISTRY
    ]
