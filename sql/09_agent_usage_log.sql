-- 09_agent_usage_log.sql
-- DDL for dw.AgentUsageLog — Phase 6 budget tracking table.
-- Run after: 08_etl_stg_to_dw.sql

USE HealthcareADK;
GO

IF NOT EXISTS (
    SELECT 1
    FROM   sys.tables  t
    JOIN   sys.schemas s ON s.schema_id = t.schema_id
    WHERE  s.name = 'dw' AND t.name = 'AgentUsageLog'
)
BEGIN
    CREATE TABLE dw.AgentUsageLog (
        LogID             INT IDENTITY(1,1)  NOT NULL,
        AgentName         VARCHAR(50)        NOT NULL,
        SessionID         VARCHAR(100)       NOT NULL,
        InputTokens       INT                NOT NULL  DEFAULT 0,
        OutputTokens      INT                NOT NULL  DEFAULT 0,
        ToolCalls         INT                NOT NULL  DEFAULT 0,
        ModelID           VARCHAR(100)           NULL,
        RequestTimestamp  DATETIME2          NOT NULL  DEFAULT SYSDATETIME(),
        Notes             VARCHAR(500)           NULL,

        CONSTRAINT PK_AgentUsageLog PRIMARY KEY CLUSTERED (LogID)
    );

    -- Supports remaining() and session_summary() lookups
    CREATE NONCLUSTERED INDEX IX_AgentUsageLog_Session
        ON dw.AgentUsageLog (SessionID, AgentName)
        INCLUDE (InputTokens, OutputTokens, ToolCalls);

    -- Supports date-range filters in the usage SP (task 6)
    CREATE NONCLUSTERED INDEX IX_AgentUsageLog_Timestamp
        ON dw.AgentUsageLog (RequestTimestamp)
        INCLUDE (AgentName, InputTokens, OutputTokens);

    PRINT 'dw.AgentUsageLog created.';
END
ELSE
BEGIN
    PRINT 'dw.AgentUsageLog already exists — skipped.';
END
GO
