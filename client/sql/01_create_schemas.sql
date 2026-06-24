-- ============================================================
-- HealthcareADK : Create Schemas
-- stg  = staging (raw load from landing zone)
-- dw   = data warehouse (star schema)
-- rpt  = reporting views (Power BI layer)
-- ============================================================
USE HealthcareADK;
GO

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'stg')
    EXEC('CREATE SCHEMA stg');
GO

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'dw')
    EXEC('CREATE SCHEMA dw');
GO

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'rpt')
    EXEC('CREATE SCHEMA rpt');
GO

PRINT 'Schemas stg / dw / rpt ready.';
GO
