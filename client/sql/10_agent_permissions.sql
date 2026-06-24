-- 10_agent_permissions.sql
-- Database users and schema-level GRANTs for Phase 6 agents.
-- Run after: 09_agent_usage_log.sql AND scripts/deploy_agent_logins.py
--
-- NOTE ON AUTH MODE:
--   These are SQL Server logins (SQL auth). To use them, update _get_conn() in
--   agents/tools/sql_tools.py and agents/budget_tracker.py to read UID/PWD from
--   env vars (HEALTHCAREADK_SQL_USER / HEALTHCAREADK_SQL_PWD) instead of
--   Trusted_Connection=yes. For a Windows-auth setup, create a Windows login per
--   service account and run deploy_agent_logins.py with Windows-auth logins instead.
--
-- PASSWORDS: Managed entirely by scripts/deploy_agent_logins.py via env vars.
--   No passwords appear in this file.

-- Logins are created by scripts/deploy_agent_logins.py (reads passwords from env vars).
-- Run that script first, then run this file in SSMS.

-- ============================================================
-- 1. CREATE DATABASE USERS (HealthcareADK database)
-- ============================================================

USE HealthcareADK;
GO

IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'agent_orchestrator')
    CREATE USER agent_orchestrator FOR LOGIN agent_orchestrator;
GO
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'agent_claims')
    CREATE USER agent_claims FOR LOGIN agent_claims;
GO
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'agent_clinical')
    CREATE USER agent_clinical FOR LOGIN agent_clinical;
GO
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'agent_financial')
    CREATE USER agent_financial FOR LOGIN agent_financial;
GO
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'agent_reporting')
    CREATE USER agent_reporting FOR LOGIN agent_reporting;
GO
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'agent_etl')
    CREATE USER agent_etl FOR LOGIN agent_etl;
GO
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'agent_provider')
    CREATE USER agent_provider FOR LOGIN agent_provider;
GO

PRINT 'Database users created (or already exist).';
GO

-- ============================================================
-- 2. OrchestratorAgent — rpt schema (SELECT only)
-- ============================================================

GRANT SELECT ON SCHEMA::rpt TO agent_orchestrator;

-- Budget tracker access (all agents need this)
GRANT SELECT, INSERT ON dw.AgentUsageLog TO agent_orchestrator;

GO
PRINT 'agent_orchestrator permissions granted.';
GO

-- ============================================================
-- 3. ClaimsAgent — rpt schema + scoped dw tables
-- ============================================================

GRANT SELECT ON SCHEMA::rpt TO agent_claims;

-- Approved dw tables (per claims_agent.yaml db_tables)
GRANT SELECT ON dw.FactClaims     TO agent_claims;
GRANT SELECT ON dw.DimPatient     TO agent_claims;
GRANT SELECT ON dw.DimProvider    TO agent_claims;
GRANT SELECT ON dw.DimPayer       TO agent_claims;
GRANT SELECT ON dw.DimFacility    TO agent_claims;
GRANT SELECT ON dw.DimDiagnosis   TO agent_claims;
GRANT SELECT ON dw.DimProcedure   TO agent_claims;
GRANT SELECT ON dw.DimDate        TO agent_claims;

-- Stored procedure (get_claims_summary tool)
GRANT EXECUTE ON dw.usp_GetClaimsSummary TO agent_claims;

-- Budget tracker
GRANT SELECT, INSERT ON dw.AgentUsageLog TO agent_claims;

GO
PRINT 'agent_claims permissions granted.';
GO

-- ============================================================
-- 4. ClinicalAgent — rpt schema + scoped dw tables
-- ============================================================

GRANT SELECT ON SCHEMA::rpt TO agent_clinical;

-- Approved dw tables (per clinical_agent.yaml db_tables)
GRANT SELECT ON dw.FactLabResults    TO agent_clinical;
GRANT SELECT ON dw.FactPrescriptions TO agent_clinical;
GRANT SELECT ON dw.DimPatient        TO agent_clinical;
GRANT SELECT ON dw.DimDrug           TO agent_clinical;
GRANT SELECT ON dw.DimDiagnosis      TO agent_clinical;
GRANT SELECT ON dw.DimProvider       TO agent_clinical;
GRANT SELECT ON dw.DimDate           TO agent_clinical;

-- Stored procedures (get_abnormal_labs, get_patient_timeline tools)
GRANT EXECUTE ON dw.usp_GetAbnormalLabResults TO agent_clinical;
GRANT EXECUTE ON dw.usp_GetPatientTimeline    TO agent_clinical;

-- Budget tracker
GRANT SELECT, INSERT ON dw.AgentUsageLog TO agent_clinical;

GO
PRINT 'agent_clinical permissions granted.';
GO

-- ============================================================
-- 5. FinancialAgent — rpt schema + scoped dw tables
-- ============================================================

GRANT SELECT ON SCHEMA::rpt TO agent_financial;

-- Approved dw tables (per financial_agent.yaml db_tables)
GRANT SELECT ON dw.FactFinancials TO agent_financial;
GRANT SELECT ON dw.DimFacility    TO agent_financial;
GRANT SELECT ON dw.DimDate        TO agent_financial;

-- Stored procedure (get_financial_yoy tool)
GRANT EXECUTE ON dw.usp_GetFinancialYoY TO agent_financial;

-- Budget tracker
GRANT SELECT, INSERT ON dw.AgentUsageLog TO agent_financial;

GO
PRINT 'agent_financial permissions granted.';
GO

-- ============================================================
-- 6. ReportingAgent — rpt schema only (read-only)
-- ============================================================

GRANT SELECT ON SCHEMA::rpt TO agent_reporting;

-- Budget tracker
GRANT SELECT, INSERT ON dw.AgentUsageLog TO agent_reporting;

GO
PRINT 'agent_reporting permissions granted.';
GO

-- ============================================================
-- 7. ETLAgent — stg schema (full) + dw.ETLLog (INSERT) + dw SELECT
-- ============================================================

-- Full access to staging (load, truncate, verify)
GRANT SELECT, INSERT, UPDATE, DELETE ON SCHEMA::stg TO agent_etl;

-- ETL log (INSERT only — no UPDATE/DELETE on audit log)
GRANT INSERT ON dw.ETLLog TO agent_etl;

-- Post-ETL verification: SELECT on dw schema
GRANT SELECT ON SCHEMA::dw TO agent_etl;

-- ETL stored procedures
GRANT EXECUTE ON dw.usp_ETL_RunAll                  TO agent_etl;
GRANT EXECUTE ON dw.usp_ETL_LoadDimPayer            TO agent_etl;
GRANT EXECUTE ON dw.usp_ETL_LoadDimFacility         TO agent_etl;
GRANT EXECUTE ON dw.usp_ETL_LoadDimProvider         TO agent_etl;
GRANT EXECUTE ON dw.usp_ETL_LoadDimPatient          TO agent_etl;
GRANT EXECUTE ON dw.usp_ETL_LoadFactClaims          TO agent_etl;
GRANT EXECUTE ON dw.usp_ETL_LoadFactLabResults      TO agent_etl;
GRANT EXECUTE ON dw.usp_ETL_LoadFactPrescriptions   TO agent_etl;
GRANT EXECUTE ON dw.usp_ETL_LoadFactFinancials      TO agent_etl;

-- Budget tracker
GRANT SELECT, INSERT ON dw.AgentUsageLog TO agent_etl;

GO
PRINT 'agent_etl permissions granted.';
GO

-- ============================================================
-- 8. ProviderAgent — rpt schema + scoped dw tables
-- ============================================================

GRANT SELECT ON SCHEMA::rpt TO agent_provider;

-- Approved dw tables (per provider_agent.yaml db_tables)
GRANT SELECT ON dw.DimProvider  TO agent_provider;
GRANT SELECT ON dw.DimFacility  TO agent_provider;
GRANT SELECT ON dw.FactClaims   TO agent_provider;
GRANT SELECT ON dw.DimDate      TO agent_provider;
GRANT SELECT ON dw.DimPatient   TO agent_provider;
GRANT SELECT ON dw.DimDiagnosis TO agent_provider;
GRANT SELECT ON dw.DimProcedure TO agent_provider;

-- Stored procedure (get_provider_performance tool)
GRANT EXECUTE ON dw.usp_GetProviderPerformance TO agent_provider;

-- Budget tracker
GRANT SELECT, INSERT ON dw.AgentUsageLog TO agent_provider;

GO
PRINT 'agent_provider permissions granted.';
GO

-- ============================================================
-- 9. DENY cross-schema access (defense-in-depth)
--     Explicit DENY overrides any role-level GRANTs.
-- ============================================================

-- OrchestratorAgent must not touch stg
-- NOTE: DENY SELECT ON SCHEMA::dw is intentionally omitted. SQL Server's DENY
-- overrides GRANT at any level, so a schema-level DENY would negate the
-- object-level GRANT on dw.AgentUsageLog above. Without any GRANT on the
-- dw schema, access is already denied by default for all other dw objects.
DENY SELECT ON SCHEMA::stg TO agent_orchestrator;

-- ClaimsAgent must not touch stg
DENY SELECT ON SCHEMA::stg TO agent_claims;

-- ClinicalAgent must not touch stg or financials
DENY SELECT ON SCHEMA::stg            TO agent_clinical;
DENY SELECT ON dw.FactFinancials      TO agent_clinical;

-- FinancialAgent must not touch stg or patient/lab/claims tables
DENY SELECT ON SCHEMA::stg            TO agent_financial;
DENY SELECT ON dw.FactClaims          TO agent_financial;
DENY SELECT ON dw.FactLabResults      TO agent_financial;
DENY SELECT ON dw.FactPrescriptions   TO agent_financial;
DENY SELECT ON dw.DimPatient          TO agent_financial;

-- ReportingAgent must not touch stg
-- NOTE: DENY SELECT ON SCHEMA::dw is intentionally omitted — same reason as
-- agent_orchestrator above. GRANT on dw.AgentUsageLog + no schema DENY is
-- the correct combination to allow only that one dw object.
DENY SELECT ON SCHEMA::stg TO agent_reporting;

-- ProviderAgent must not touch stg or financial/clinical facts
DENY SELECT ON SCHEMA::stg            TO agent_provider;
DENY SELECT ON dw.FactFinancials      TO agent_provider;
DENY SELECT ON dw.FactLabResults      TO agent_provider;
DENY SELECT ON dw.FactPrescriptions   TO agent_provider;

GO
PRINT 'Cross-schema DENY rules applied.';
GO

PRINT '=== 10_agent_permissions.sql complete ===';
GO
