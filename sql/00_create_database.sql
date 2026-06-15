-- ============================================================
-- HealthcareADK : Create Database
-- Run once as sysadmin before any other scripts
-- ============================================================
USE master;
GO

IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = N'HealthcareADK')
BEGIN
    CREATE DATABASE HealthcareADK
        COLLATE SQL_Latin1_General_CP1_CI_AS;
    PRINT 'Database HealthcareADK created.';
END
ELSE
    PRINT 'Database HealthcareADK already exists — skipped.';
GO
