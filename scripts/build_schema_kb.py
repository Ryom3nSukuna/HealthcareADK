"""
Build the HealthcareADK schema knowledge base.

Queries SQL Server information_schema for live column metadata, parses sql/ DDL
files for SP/view definitions, and writes docs/schema_kb.json.

Run whenever the schema changes:
    python scripts/build_schema_kb.py
"""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import pyodbc
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def _conn_str() -> str:
    server = os.environ["HEALTHCAREADK_SQL_SERVER"]
    db = os.environ["HEALTHCAREADK_SQL_DB"]
    return (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={server};DATABASE={db};Trusted_Connection=yes;"
    )

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SQL_DIR = PROJECT_ROOT / "sql"
OUT_PATH = PROJECT_ROOT / "docs" / "schema_kb.json"

SCHEMAS = ("stg", "dw", "rpt")

# Business-friendly descriptions for well-known tables
TABLE_DESCRIPTIONS = {
    "stg.Patients":           "Raw patient demographic data loaded from landing zone CSVs",
    "stg.Providers":          "Raw provider data (doctors, nurses) from landing zone",
    "stg.Claims":             "Raw insurance claims data from landing zone",
    "stg.Labs":               "Raw lab result records from landing zone",
    "stg.Prescriptions":      "Raw prescription records from landing zone",
    "stg.Facilities":         "Raw facility/hospital data from landing zone",
    "stg.Payers":             "Raw insurance payer data from landing zone",
    "stg.Financials":         "Raw financial transaction data from landing zone",
    "dw.DimPatient":          "SCD2 patient dimension — tracks demographic history",
    "dw.DimProvider":         "Provider dimension — specialty, license, NPI",
    "dw.DimFacility":         "Facility dimension — hospitals, clinics, state, bed count",
    "dw.DimPayer":            "Payer dimension — commercial, Medicare, Medicaid, Self-Pay",
    "dw.DimDate":             "Date dimension pre-populated 2019–2030, fiscal calendar",
    "dw.DimDiagnosis":        "ICD-10 diagnosis codes and descriptions",
    "dw.DimDrug":             "Drug/medication dimension — name, class, controlled status",
    "dw.DimProcedure":        "CPT procedure codes and descriptions",
    "dw.FactClaims":          "Claim fact table — billed, allowed, paid, denied amounts",
    "dw.FactLabResults":      "Lab result fact — test values, reference ranges, abnormal flags",
    "dw.FactPrescriptions":   "Prescription fact — drug, cost to patient vs payer, refills",
    "dw.FactFinancials":      "Financial fact — revenue, expenses, department, fiscal period",
    "rpt.vw_ClaimsSummary":   "Reporting view joining FactClaims with all dims — primary claims view",
    "rpt.vw_LabResults":      "Reporting view for lab results with patient/provider context",
    "rpt.vw_Prescriptions":   "Reporting view for prescriptions with drug/patient/payer context",
    "rpt.vw_ProviderPerformance": "Reporting view aggregating provider claim metrics",
    "rpt.vw_FinancialKPIs":   "Reporting view for financial KPIs by department and fiscal year",
    "dw.AgentUsageLog":       "Phase 6 budget tracking — one row per Claude API call; stores token counts, tool calls, and session IDs per agent",
    "rpt.vw_AgentUsage":      "Reporting view over dw.AgentUsageLog — adds TotalTokens and date/hour columns for Power BI",
}

# Business-friendly descriptions for well-known columns
COLUMN_DESCRIPTIONS = {
    "BilledAmount":      "Amount billed by provider to payer",
    "AllowedAmount":     "Amount allowed by payer contract",
    "PaidAmount":        "Amount actually paid by payer",
    "WriteOffAmount":    "Contractual write-off (BilledAmount minus AllowedAmount)",
    "CostToPatient":     "Patient out-of-pocket cost (copay/deductible)",
    "CostToPayer":       "Amount covered by the payer",
    "TotalCost":         "Total cost (CostToPatient + CostToPayer)",
    "ClaimStatus":       "Approved | Denied | Pending | Appealed",
    "AbnormalFlag":      "Normal | High | Low | Critical",
    "DenialRatePct":     "Percentage of claims denied for a provider",
    "PatientAgeAtService": "Age of patient at time of service (years)",
    "FiscalYear":        "Fiscal year (same as calendar year in this dataset)",
    "FiscalQuarter":     "Fiscal quarter (Q1–Q4)",
    "IsCurrent":         "SCD2 flag — 1 = current record, 0 = historical",
    "IsWeekend":         "1 = Saturday or Sunday",
    "DaysSupply":        "Number of days a prescription covers",
    "RefillsAuthorized": "Total refills authorized by the prescriber",
    "RefillsRemaining":  "Refills remaining on the prescription",
    "TransactionType":   "Revenue | Expense (FactFinancials)",
    "Department":        "Clinical or administrative department name",
    "Amount":            "Financial transaction amount",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def col_type_str(row) -> str:
    dt = row.DATA_TYPE
    if dt in ("varchar", "nvarchar", "char", "nchar"):
        length = row.CHARACTER_MAXIMUM_LENGTH
        length_str = "MAX" if length == -1 else str(length)
        return f"{dt}({length_str})"
    if dt in ("decimal", "numeric") and row.NUMERIC_PRECISION:
        return f"{dt}({row.NUMERIC_PRECISION},{row.NUMERIC_SCALE})"
    return dt


def extract_sp_definitions(sql_text: str) -> dict[str, str]:
    """Extract CREATE PROCEDURE blocks from a SQL file."""
    pattern = re.compile(
        r"CREATE\s+(?:OR\s+ALTER\s+)?PROCEDURE\s+(\S+)\s.*?(?=\nGO\b|\Z)",
        re.IGNORECASE | re.DOTALL,
    )
    return {m.group(1).strip("[]"): m.group(0)[:500] for m in pattern.finditer(sql_text)}


def extract_view_definitions(sql_text: str) -> dict[str, str]:
    """Extract CREATE VIEW blocks from a SQL file."""
    pattern = re.compile(
        r"CREATE\s+(?:OR\s+ALTER\s+)?VIEW\s+(\S+)\s.*?(?=\nGO\b|\Z)",
        re.IGNORECASE | re.DOTALL,
    )
    return {m.group(1).strip("[]"): m.group(0)[:800] for m in pattern.finditer(sql_text)}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build_kb() -> dict:
    conn = pyodbc.connect(_conn_str())
    cursor = conn.cursor()

    kb: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "database": os.environ["HEALTHCAREADK_SQL_DB"],
        "schemas": {},
        "stored_procedures": {},
        "etl_procedures": {},
        "views_sql": {},
    }

    # -----------------------------------------------------------------------
    # 1. Tables and columns from information_schema
    # -----------------------------------------------------------------------
    cursor.execute("""
        SELECT
            t.TABLE_SCHEMA,
            t.TABLE_NAME,
            t.TABLE_TYPE,
            c.COLUMN_NAME,
            c.DATA_TYPE,
            c.CHARACTER_MAXIMUM_LENGTH,
            c.NUMERIC_PRECISION,
            c.NUMERIC_SCALE,
            c.IS_NULLABLE,
            c.ORDINAL_POSITION
        FROM INFORMATION_SCHEMA.TABLES t
        JOIN INFORMATION_SCHEMA.COLUMNS c
            ON t.TABLE_SCHEMA = c.TABLE_SCHEMA AND t.TABLE_NAME = c.TABLE_NAME
        WHERE t.TABLE_SCHEMA IN ('stg','dw','rpt')
        ORDER BY t.TABLE_SCHEMA, t.TABLE_NAME, c.ORDINAL_POSITION
    """)

    tables: dict = {}
    for row in cursor.fetchall():
        schema = row.TABLE_SCHEMA
        tname = row.TABLE_NAME
        key = f"{schema}.{tname}"
        if key not in tables:
            tables[key] = {
                "schema": schema,
                "name": tname,
                "type": "VIEW" if row.TABLE_TYPE == "VIEW" else "TABLE",
                "description": TABLE_DESCRIPTIONS.get(key, ""),
                "columns": [],
            }
        tables[key]["columns"].append({
            "name": row.COLUMN_NAME,
            "type": col_type_str(row),
            "nullable": row.IS_NULLABLE == "YES",
            "description": COLUMN_DESCRIPTIONS.get(row.COLUMN_NAME, ""),
        })

    # Organise by schema
    for schema in SCHEMAS:
        kb["schemas"][schema] = {
            k: v for k, v in tables.items() if k.startswith(f"{schema}.")
        }

    # -----------------------------------------------------------------------
    # 2. Stored procedures from information_schema
    # -----------------------------------------------------------------------
    cursor.execute("""
        SELECT ROUTINE_SCHEMA, ROUTINE_NAME, ROUTINE_DEFINITION
        FROM INFORMATION_SCHEMA.ROUTINES
        WHERE ROUTINE_TYPE = 'PROCEDURE'
          AND ROUTINE_SCHEMA IN ('dw','stg','rpt')
        ORDER BY ROUTINE_SCHEMA, ROUTINE_NAME
    """)
    for row in cursor.fetchall():
        fqn = f"{row.ROUTINE_SCHEMA}.{row.ROUTINE_NAME}"
        kb["stored_procedures"][fqn] = {
            "schema": row.ROUTINE_SCHEMA,
            "name": row.ROUTINE_NAME,
            "definition_preview": (row.ROUTINE_DEFINITION or "")[:600],
        }

    conn.close()

    # -----------------------------------------------------------------------
    # 3. Parse sql/ files for SP/view definitions (richer than IS truncation)
    # -----------------------------------------------------------------------
    for sql_file in sorted(SQL_DIR.glob("*.sql")):
        text = sql_file.read_text(encoding="utf-8", errors="ignore")
        for sp_name, sp_body in extract_sp_definitions(text).items():
            if sp_name not in kb["stored_procedures"]:
                kb["stored_procedures"][sp_name] = {}
            kb["stored_procedures"][sp_name]["source_file"] = sql_file.name
            kb["stored_procedures"][sp_name]["definition_preview"] = sp_body

        for view_name, view_body in extract_view_definitions(text).items():
            kb["views_sql"][view_name] = {
                "source_file": sql_file.name,
                "definition_preview": view_body,
            }

    return kb


if __name__ == "__main__":
    print("Building schema knowledge base...")
    kb = build_kb()

    table_count = sum(len(v) for v in kb["schemas"].values())
    sp_count = len(kb["stored_procedures"])
    col_count = sum(
        len(t["columns"])
        for schema in kb["schemas"].values()
        for t in schema.values()
    )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(kb, indent=2), encoding="utf-8")

    print(f"  Tables/views : {table_count}")
    print(f"  Columns      : {col_count}")
    print(f"  Procedures   : {sp_count}")
    print(f"  Written to   : {OUT_PATH}")
