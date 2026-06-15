"""
SQL Server schema permission integration tests.

Verifies that each agent SQL login can only access its approved schemas and tables.
All tests are skipped unless HEALTHCAREADK_TEST_PERMISSIONS=1 is set.

Prerequisites (must be done before running):
  1. sql/09_agent_usage_log.sql deployed in SSMS
  2. sql/10_agent_permissions.sql deployed in SSMS (passwords replaced)
  3. sql/11_agent_usage_views.sql deployed in SSMS

Required env vars:
  HEALTHCAREADK_SQL_SERVER               e.g. .\\SQLEXPRESS
  HEALTHCAREADK_SQL_DB                   e.g. HealthcareADK
  HEALTHCAREADK_TEST_PERMISSIONS         must be "1" to run
  HEALTHCAREADK_PWD_AGENT_ORCHESTRATOR
  HEALTHCAREADK_PWD_AGENT_CLAIMS
  HEALTHCAREADK_PWD_AGENT_CLINICAL
  HEALTHCAREADK_PWD_AGENT_FINANCIAL
  HEALTHCAREADK_PWD_AGENT_REPORTING
  HEALTHCAREADK_PWD_AGENT_ETL
  HEALTHCAREADK_PWD_AGENT_PROVIDER

Run:
  $env:HEALTHCAREADK_TEST_PERMISSIONS=1; pytest tests/test_permissions.py -v
"""

import os
import sys
from pathlib import Path

import pyodbc
import pytest
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

pytestmark = pytest.mark.skipif(
    os.getenv("HEALTHCAREADK_TEST_PERMISSIONS") != "1",
    reason="Set HEALTHCAREADK_TEST_PERMISSIONS=1 to run schema permission tests",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _conn(login: str) -> pyodbc.Connection:
    server = os.environ["HEALTHCAREADK_SQL_SERVER"]
    db = os.environ["HEALTHCAREADK_SQL_DB"]
    pwd = os.environ[f"HEALTHCAREADK_PWD_{login.upper()}"]
    return pyodbc.connect(
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={server};DATABASE={db};"
        f"UID={login};PWD={pwd};"
    )


def _can_select(login: str, table: str) -> bool:
    """Return True if the login can SELECT from the table, False if permission denied."""
    try:
        with _conn(login) as conn:
            conn.execute(f"SELECT TOP 1 * FROM {table}").fetchone()
        return True
    except pyodbc.Error:
        return False


def _has_perm(login: str, obj: str, perm: str) -> bool:
    """Return True if the login has the given permission on the object."""
    with _conn(login) as conn:
        row = conn.execute(
            "SELECT HAS_PERMS_BY_NAME(?, 'OBJECT', ?)", obj, perm
        ).fetchone()
    return bool(row and row[0] == 1)


def _can_insert_etl_log(login: str) -> bool:
    """Try an INSERT into dw.ETLLog (rolled back) — True if permitted."""
    try:
        with _conn(login) as conn:
            conn.autocommit = False
            conn.execute(
                "INSERT INTO dw.ETLLog (Entity) VALUES (?)", "PermTest"
            )
            conn.rollback()
        return True
    except pyodbc.Error:
        return False


# ---------------------------------------------------------------------------
# OrchestratorAgent — rpt only
# ---------------------------------------------------------------------------

class TestOrchestratorPermissions:

    def test_can_select_rpt_view(self):
        assert _can_select("agent_orchestrator", "rpt.vw_ClaimsSummary")

    def test_can_select_agent_usage_log(self):
        assert _can_select("agent_orchestrator", "dw.AgentUsageLog")

    def test_cannot_select_dw_fact(self):
        assert not _can_select("agent_orchestrator", "dw.FactClaims")

    def test_cannot_select_stg(self):
        assert not _can_select("agent_orchestrator", "stg.Claims")


# ---------------------------------------------------------------------------
# ClaimsAgent — rpt + approved dw claims tables
# ---------------------------------------------------------------------------

class TestClaimsPermissions:

    def test_can_select_fact_claims(self):
        assert _can_select("agent_claims", "dw.FactClaims")

    def test_can_select_dim_payer(self):
        assert _can_select("agent_claims", "dw.DimPayer")

    def test_can_select_rpt_view(self):
        assert _can_select("agent_claims", "rpt.vw_ClaimsSummary")

    def test_can_execute_claims_sp(self):
        assert _has_perm("agent_claims", "dw.usp_GetClaimsSummary", "EXECUTE")

    def test_cannot_select_stg(self):
        assert not _can_select("agent_claims", "stg.Claims")

    def test_cannot_select_fact_financials(self):
        assert not _can_select("agent_claims", "dw.FactFinancials")

    def test_cannot_select_fact_lab_results(self):
        assert not _can_select("agent_claims", "dw.FactLabResults")


# ---------------------------------------------------------------------------
# ClinicalAgent — rpt + approved dw patient/lab/rx tables
# ---------------------------------------------------------------------------

class TestClinicalPermissions:

    def test_can_select_fact_lab_results(self):
        assert _can_select("agent_clinical", "dw.FactLabResults")

    def test_can_select_fact_prescriptions(self):
        assert _can_select("agent_clinical", "dw.FactPrescriptions")

    def test_can_select_dim_patient(self):
        assert _can_select("agent_clinical", "dw.DimPatient")

    def test_can_select_rpt_view(self):
        assert _can_select("agent_clinical", "rpt.vw_LabResults")

    def test_can_execute_abnormal_labs_sp(self):
        assert _has_perm("agent_clinical", "dw.usp_GetAbnormalLabResults", "EXECUTE")

    def test_can_execute_patient_timeline_sp(self):
        assert _has_perm("agent_clinical", "dw.usp_GetPatientTimeline", "EXECUTE")

    def test_cannot_select_stg(self):
        assert not _can_select("agent_clinical", "stg.Labs")

    def test_cannot_select_fact_financials(self):
        assert not _can_select("agent_clinical", "dw.FactFinancials")

    def test_cannot_select_fact_claims(self):
        assert not _can_select("agent_clinical", "dw.FactClaims")


# ---------------------------------------------------------------------------
# FinancialAgent — rpt + FactFinancials, DimFacility, DimDate only
# ---------------------------------------------------------------------------

class TestFinancialPermissions:

    def test_can_select_fact_financials(self):
        assert _can_select("agent_financial", "dw.FactFinancials")

    def test_can_select_dim_facility(self):
        assert _can_select("agent_financial", "dw.DimFacility")

    def test_can_select_rpt_view(self):
        assert _can_select("agent_financial", "rpt.vw_FinancialKPIs")

    def test_can_execute_financial_yoy_sp(self):
        assert _has_perm("agent_financial", "dw.usp_GetFinancialYoY", "EXECUTE")

    def test_cannot_select_stg(self):
        assert not _can_select("agent_financial", "stg.Financials")

    def test_cannot_select_fact_claims(self):
        assert not _can_select("agent_financial", "dw.FactClaims")

    def test_cannot_select_dim_patient(self):
        assert not _can_select("agent_financial", "dw.DimPatient")

    def test_cannot_select_fact_lab_results(self):
        assert not _can_select("agent_financial", "dw.FactLabResults")

    def test_cannot_select_fact_prescriptions(self):
        assert not _can_select("agent_financial", "dw.FactPrescriptions")


# ---------------------------------------------------------------------------
# ReportingAgent — rpt only (read-only)
# ---------------------------------------------------------------------------

class TestReportingPermissions:

    def test_can_select_rpt_claims_view(self):
        assert _can_select("agent_reporting", "rpt.vw_ClaimsSummary")

    def test_can_select_rpt_financial_view(self):
        assert _can_select("agent_reporting", "rpt.vw_FinancialKPIs")

    def test_can_select_agent_usage_log(self):
        assert _can_select("agent_reporting", "dw.AgentUsageLog")

    def test_can_execute_agent_usage_sp(self):
        assert _has_perm("agent_reporting", "dw.usp_GetAgentUsage", "EXECUTE")

    def test_cannot_select_dw_fact(self):
        assert not _can_select("agent_reporting", "dw.FactClaims")

    def test_cannot_select_stg(self):
        assert not _can_select("agent_reporting", "stg.Claims")


# ---------------------------------------------------------------------------
# ETLAgent — stg full + dw SELECT + dw.ETLLog INSERT
# ---------------------------------------------------------------------------

class TestETLPermissions:

    def test_can_select_stg(self):
        assert _can_select("agent_etl", "stg.Claims")

    def test_can_select_dw_for_verification(self):
        assert _can_select("agent_etl", "dw.FactClaims")

    def test_can_insert_etl_log(self):
        assert _can_insert_etl_log("agent_etl")

    def test_can_execute_etl_run_all_sp(self):
        assert _has_perm("agent_etl", "dw.usp_ETL_RunAll", "EXECUTE")

    def test_cannot_insert_into_dw_fact(self):
        # agent_etl has SELECT on dw.* but not INSERT
        assert not _has_perm("agent_etl", "dw.FactClaims", "INSERT")

    def test_cannot_delete_from_dw_fact(self):
        assert not _has_perm("agent_etl", "dw.FactClaims", "DELETE")


# ---------------------------------------------------------------------------
# ProviderAgent — rpt + approved dw provider/facility tables
# ---------------------------------------------------------------------------

class TestProviderPermissions:

    def test_can_select_dim_provider(self):
        assert _can_select("agent_provider", "dw.DimProvider")

    def test_can_select_dim_facility(self):
        assert _can_select("agent_provider", "dw.DimFacility")

    def test_can_select_rpt_view(self):
        assert _can_select("agent_provider", "rpt.vw_ProviderPerformance")

    def test_can_execute_provider_sp(self):
        assert _has_perm("agent_provider", "dw.usp_GetProviderPerformance", "EXECUTE")

    def test_cannot_select_stg(self):
        assert not _can_select("agent_provider", "stg.Providers")

    def test_cannot_select_fact_financials(self):
        assert not _can_select("agent_provider", "dw.FactFinancials")

    def test_cannot_select_fact_lab_results(self):
        assert not _can_select("agent_provider", "dw.FactLabResults")

    def test_cannot_select_fact_prescriptions(self):
        assert not _can_select("agent_provider", "dw.FactPrescriptions")
