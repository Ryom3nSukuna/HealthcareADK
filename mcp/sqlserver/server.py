"""
HealthcareADK — MCP SQL Server
Provides read-only access to the HealthcareADK SQL Server data warehouse.

Tools:
  execute_query          — raw SELECT against any rpt/dw/stg table
  get_claims_summary     — filtered claims via usp_GetClaimsSummary
  get_financial_yoy      — YoY revenue/expense via usp_GetFinancialYoY
  get_provider_performance — provider KPIs via usp_GetProviderPerformance
  get_abnormal_labs      — abnormal/critical labs via usp_GetAbnormalLabResults
  get_patient_timeline   — full care timeline via usp_GetPatientTimeline
  get_schema             — describe columns of a table or view
  list_tables            — list objects in a schema
  search_schema          — keyword search across tables, columns, procedures (RAG)
"""

import json
import os
import re
from pathlib import Path

import pyodbc
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

_KB_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "schema_kb.json"
_kb_cache: dict | None = None


def _load_kb() -> dict:
    global _kb_cache
    if _kb_cache is None and _KB_PATH.exists():
        _kb_cache = json.loads(_KB_PATH.read_text(encoding="utf-8"))
    return _kb_cache or {}

mcp = FastMCP("mcp-sqlserver")

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def get_conn() -> pyodbc.Connection:
    server = os.environ["HEALTHCAREADK_SQL_SERVER"]
    db = os.environ["HEALTHCAREADK_SQL_DB"]
    return pyodbc.connect(
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={server};DATABASE={db};Trusted_Connection=yes;"
    )


def cursor_to_dict(cursor) -> dict:
    """Convert a cursor result set to a serialisable dict. Max 500 rows."""
    columns = [col[0] for col in cursor.description]
    rows = [list(row) for row in cursor.fetchmany(500)]
    return {"columns": columns, "rows": rows, "row_count": len(rows)}


def _validate_select(sql: str) -> str | None:
    """Return an error message if sql is not a safe single SELECT statement, else None.

    A bare str.startswith("SELECT") check lets a stacked batch like
    "SELECT 1; EXEC xp_cmdshell '...'" through, since SQL Server executes the whole
    batch. This strips comments, then rejects anything but one SELECT with no second
    statement and no EXEC/xp_/sp_/OPENROWSET/OPENQUERY anywhere in it.
    """
    no_comments = re.sub(r"--[^\n]*", "", sql)
    no_comments = re.sub(r"/\*.*?\*/", "", no_comments, flags=re.DOTALL)
    body = no_comments.strip().rstrip(";").strip()

    if not body.upper().startswith("SELECT"):
        return "Only SELECT statements are allowed."
    if ";" in body:
        return "Stacked/multiple statements are not allowed."
    if re.search(r"\b(EXEC|EXECUTE|XP_\w+|SP_\w+|OPENROWSET|OPENQUERY)\b", body.upper()):
        return "Query contains a blocked keyword (EXEC/xp_*/sp_*/OPENROWSET/OPENQUERY)."
    return None


# ------------------------------------------------------------------
# Tool: execute_query
# ------------------------------------------------------------------

@mcp.tool()
def execute_query(sql: str) -> str:
    """
    Run a read-only SELECT query against HealthcareADK. Returns up to 500 rows.
    Only SELECT statements are permitted — INSERT / UPDATE / DELETE / EXEC are blocked.

    Preferred views (rpt schema):
      rpt.vw_ClaimsSummary, rpt.vw_LabResults, rpt.vw_Prescriptions,
      rpt.vw_ProviderPerformance, rpt.vw_FinancialKPIs

    Warehouse tables (dw schema):
      dw.FactClaims, dw.FactLabResults, dw.FactPrescriptions, dw.FactFinancials,
      dw.DimPatient, dw.DimProvider, dw.DimFacility, dw.DimPayer, dw.DimDate
    """
    error = _validate_select(sql)
    if error:
        return f"Error: {error}"
    try:
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute(sql)
        result = cursor_to_dict(cursor)
        conn.close()
        return json.dumps(result, default=str, indent=2)
    except Exception as exc:
        return f"Error: {exc}"


# ------------------------------------------------------------------
# Tool: get_claims_summary
# ------------------------------------------------------------------

@mcp.tool()
def get_claims_summary(
    start_date: str = None,
    end_date: str = None,
    payer_type: str = None,
    claim_status: str = None,
    state: str = None,
    top_n: int = 100,
) -> str:
    """
    Get claims with optional filters. Calls dw.usp_GetClaimsSummary.

    Parameters (all optional):
      start_date   : YYYY-MM-DD  e.g. "2023-01-01"
      end_date     : YYYY-MM-DD  e.g. "2023-12-31"
      payer_type   : Commercial | Medicare | Medicaid | Self-Pay
      claim_status : Approved | Denied | Pending | Appealed
      state        : 2-letter code e.g. "CA", "TX"
      top_n        : max rows to return (default 100)
    """
    try:
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "EXEC dw.usp_GetClaimsSummary "
            "@StartDate=?, @EndDate=?, @PayerType=?, @ClaimStatus=?, @State=?, @TopN=?",
            start_date, end_date, payer_type, claim_status, state, top_n,
        )
        result = cursor_to_dict(cursor)
        conn.close()
        return json.dumps(result, default=str, indent=2)
    except Exception as exc:
        return f"Error: {exc}"


# ------------------------------------------------------------------
# Tool: get_financial_yoy
# ------------------------------------------------------------------

@mcp.tool()
def get_financial_yoy(
    start_year: int = None,
    end_year: int = None,
    facility_id: str = None,
) -> str:
    """
    Get year-over-year revenue vs expense comparison. Calls dw.usp_GetFinancialYoY.
    Returns totals grouped by fiscal year, quarter, transaction type, and facility.

    Parameters (all optional):
      start_year  : e.g. 2022
      end_year    : e.g. 2025
      facility_id : UUID string to filter to a single facility
    """
    try:
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "EXEC dw.usp_GetFinancialYoY @StartYear=?, @EndYear=?, @FacilityID=?",
            start_year, end_year, facility_id,
        )
        result = cursor_to_dict(cursor)
        conn.close()
        return json.dumps(result, default=str, indent=2)
    except Exception as exc:
        return f"Error: {exc}"


# ------------------------------------------------------------------
# Tool: get_provider_performance
# ------------------------------------------------------------------

@mcp.tool()
def get_provider_performance(
    year: int = None,
    specialty: str = None,
    state: str = None,
    top_n: int = 50,
) -> str:
    """
    Get provider KPIs: claims volume, billed, paid, denial rate.
    Calls dw.usp_GetProviderPerformance. Results ranked by TotalBilled descending.

    Parameters (all optional):
      year      : e.g. 2024
      specialty : e.g. "Cardiology", "Orthopedics", "Internal Medicine"
      state     : 2-letter code e.g. "CA"
      top_n     : max rows (default 50)
    """
    try:
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "EXEC dw.usp_GetProviderPerformance @Year=?, @Specialty=?, @State=?, @TopN=?",
            year, specialty, state, top_n,
        )
        result = cursor_to_dict(cursor)
        conn.close()
        return json.dumps(result, default=str, indent=2)
    except Exception as exc:
        return f"Error: {exc}"


# ------------------------------------------------------------------
# Tool: get_abnormal_labs
# ------------------------------------------------------------------

@mcp.tool()
def get_abnormal_labs(
    patient_id: str = None,
    start_date: str = None,
    end_date: str = None,
    flag_filter: str = None,
    top_n: int = 200,
) -> str:
    """
    Get abnormal or critical lab results. Calls dw.usp_GetAbnormalLabResults.
    All results returned have AbnormalFlag != 'Normal'.

    Parameters (all optional except patient_id if targeting one patient):
      patient_id  : UUID to filter to a single patient
      start_date  : YYYY-MM-DD
      end_date    : YYYY-MM-DD
      flag_filter : High | Low | Critical  (omit for all abnormal)
      top_n       : max rows (default 200)
    """
    try:
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "EXEC dw.usp_GetAbnormalLabResults "
            "@PatientID=?, @StartDate=?, @EndDate=?, @FlagFilter=?, @TopN=?",
            patient_id, start_date, end_date, flag_filter, top_n,
        )
        result = cursor_to_dict(cursor)
        conn.close()
        return json.dumps(result, default=str, indent=2)
    except Exception as exc:
        return f"Error: {exc}"


# ------------------------------------------------------------------
# Tool: get_patient_timeline
# ------------------------------------------------------------------

@mcp.tool()
def get_patient_timeline(
    patient_id: str,
    start_date: str = None,
    end_date: str = None,
) -> str:
    """
    Get the full care timeline for one patient: claims, lab results, and prescriptions
    merged into a single chronological event list. Calls dw.usp_GetPatientTimeline.

    Parameters:
      patient_id : REQUIRED — UUID of the patient
      start_date : YYYY-MM-DD (optional)
      end_date   : YYYY-MM-DD (optional)
    """
    try:
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "EXEC dw.usp_GetPatientTimeline @PatientID=?, @StartDate=?, @EndDate=?",
            patient_id, start_date, end_date,
        )
        result = cursor_to_dict(cursor)
        conn.close()
        return json.dumps(result, default=str, indent=2)
    except Exception as exc:
        return f"Error: {exc}"


# ------------------------------------------------------------------
# Tool: get_schema
# ------------------------------------------------------------------

@mcp.tool()
def get_schema(table: str, schema: str = "rpt") -> str:
    """
    Describe the columns of a table or view in HealthcareADK.

    Parameters:
      table  : e.g. "vw_ClaimsSummary", "FactClaims", "DimPatient"
      schema : rpt | dw | stg  (default: rpt)
    """
    try:
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, IS_NULLABLE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?
            ORDER BY ORDINAL_POSITION
            """,
            schema, table,
        )
        cols = cursor.fetchall()
        conn.close()
        if not cols:
            return f"No object found: {schema}.{table}"
        result = {
            "table": f"{schema}.{table}",
            "columns": [
                {"name": c[0], "type": c[1], "max_length": c[2], "nullable": c[3]}
                for c in cols
            ],
        }
        return json.dumps(result, indent=2)
    except Exception as exc:
        return f"Error: {exc}"


# ------------------------------------------------------------------
# Tool: list_tables
# ------------------------------------------------------------------

@mcp.tool()
def list_tables(schema: str = "rpt") -> str:
    """
    List all tables and views in a HealthcareADK schema.

    Parameters:
      schema : rpt | dw | stg  (default: rpt)
    """
    try:
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT TABLE_NAME, TABLE_TYPE
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = ?
            ORDER BY TABLE_TYPE, TABLE_NAME
            """,
            schema,
        )
        tables = cursor.fetchall()
        conn.close()
        result = {
            "schema": schema,
            "objects": [{"name": t[0], "type": t[1]} for t in tables],
        }
        return json.dumps(result, indent=2)
    except Exception as exc:
        return f"Error: {exc}"


# ------------------------------------------------------------------
# Tool: search_schema
# ------------------------------------------------------------------

def _score(query_words: list[str], text: str) -> int:
    """Return a relevance score for text against a list of query words."""
    text_lower = text.lower()
    score = 0
    for word in query_words:
        if word == text_lower:
            score += 10          # exact match
        elif re.search(rf"\b{re.escape(word)}\b", text_lower):
            score += 5           # word boundary match
        elif word in text_lower:
            score += 2           # substring match
    return score


@mcp.tool()
def search_schema(query: str, top_n: int = 10) -> str:
    """
    Keyword search across the HealthcareADK schema knowledge base.
    Searches table names, column names, descriptions, and stored procedure names.
    Use this before writing a query to discover relevant tables and columns.

    Parameters:
      query : plain-text search terms e.g. "patient cost payer" or "denial rate"
      top_n : max results to return (default 10)

    Returns: ranked list of matching tables, columns, and procedures.
    """
    kb = _load_kb()
    if not kb:
        return json.dumps({"error": "Schema knowledge base not found. Run scripts/build_schema_kb.py first."})

    words = [w.lower() for w in re.split(r"\W+", query) if w]
    hits: list[dict] = []

    # Search tables and columns
    for _, schema_obj in kb.get("schemas", {}).items():
        for fqn, table in schema_obj.items():
            t_score = _score(words, table["name"]) + _score(words, table.get("description", ""))
            if t_score > 0:
                hits.append({
                    "type": "table",
                    "object": fqn,
                    "description": table.get("description", ""),
                    "score": t_score,
                })
            for col in table.get("columns", []):
                c_score = _score(words, col["name"]) + _score(words, col.get("description", ""))
                if c_score > 0:
                    hits.append({
                        "type": "column",
                        "object": f"{fqn}.{col['name']}",
                        "data_type": col["type"],
                        "description": col.get("description", ""),
                        "score": c_score,
                    })

    # Search stored procedures
    for sp_name, sp in kb.get("stored_procedures", {}).items():
        sp_score = _score(words, sp_name) + _score(words, sp.get("definition_preview", ""))
        if sp_score > 0:
            hits.append({
                "type": "procedure",
                "object": sp_name,
                "preview": sp.get("definition_preview", "")[:200],
                "score": sp_score,
            })

    hits.sort(key=lambda h: h["score"], reverse=True)
    return json.dumps({"query": query, "results": hits[:top_n]}, indent=2)


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
