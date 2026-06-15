-- 11_agent_usage_views.sql
-- Reporting view and stored procedure over dw.AgentUsageLog.
-- Run after: 10_agent_permissions.sql
--
-- Objects created:
--   rpt.vw_AgentUsage        — flat view for Power BI / ad-hoc queries
--   dw.usp_GetAgentUsage     — filtered SP used by ReportingAgent and usage dashboard

USE HealthcareADK;
GO

-- ============================================================
-- rpt.vw_AgentUsage
-- One row per log entry; adds TotalTokens and a cost-estimate
-- column so Power BI can visualise token spend without a join.
-- ============================================================
CREATE OR ALTER VIEW rpt.vw_AgentUsage AS
SELECT
    LogID,
    AgentName,
    SessionID,
    InputTokens,
    OutputTokens,
    InputTokens + OutputTokens          AS TotalTokens,
    ToolCalls,
    ModelID,
    RequestTimestamp,
    CAST(RequestTimestamp AS DATE)      AS RequestDate,
    DATEPART(HOUR, RequestTimestamp)    AS RequestHour,
    Notes
FROM dw.AgentUsageLog;
GO

PRINT 'rpt.vw_AgentUsage created.';
GO

-- ============================================================
-- dw.usp_GetAgentUsage
-- Filters by agent name and/or date range.
-- Returns per-call detail plus a session-level rollup.
-- Used by: ReportingAgent, end-to-end tests, usage dashboard.
-- ============================================================
CREATE OR ALTER PROCEDURE dw.usp_GetAgentUsage
    @AgentName  VARCHAR(50)  = NULL,    -- NULL = all agents
    @StartDate  DATE         = NULL,    -- NULL = no lower bound
    @EndDate    DATE         = NULL,    -- NULL = no upper bound
    @SessionID  VARCHAR(100) = NULL,    -- NULL = all sessions
    @Rollup     BIT          = 0        -- 1 = session-level summary; 0 = per-call detail
AS
BEGIN
    SET NOCOUNT ON;

    IF @Rollup = 0
    BEGIN
        -- Per-call detail
        SELECT
            LogID,
            AgentName,
            SessionID,
            InputTokens,
            OutputTokens,
            InputTokens + OutputTokens  AS TotalTokens,
            ToolCalls,
            ModelID,
            RequestTimestamp,
            Notes
        FROM dw.AgentUsageLog
        WHERE
            (@AgentName IS NULL OR AgentName   = @AgentName)
            AND (@SessionID IS NULL OR SessionID = @SessionID)
            AND (@StartDate IS NULL OR CAST(RequestTimestamp AS DATE) >= @StartDate)
            AND (@EndDate   IS NULL OR CAST(RequestTimestamp AS DATE) <= @EndDate)
        ORDER BY RequestTimestamp DESC;
    END
    ELSE
    BEGIN
        -- Session-level rollup: one row per (SessionID, AgentName)
        SELECT
            SessionID,
            AgentName,
            SUM(InputTokens)            AS TotalInputTokens,
            SUM(OutputTokens)           AS TotalOutputTokens,
            SUM(InputTokens + OutputTokens) AS TotalTokens,
            SUM(ToolCalls)              AS TotalToolCalls,
            COUNT(*)                    AS CallCount,
            MIN(RequestTimestamp)       AS SessionStart,
            MAX(RequestTimestamp)       AS SessionEnd,
            DATEDIFF(
                SECOND,
                MIN(RequestTimestamp),
                MAX(RequestTimestamp)
            )                           AS DurationSeconds
        FROM dw.AgentUsageLog
        WHERE
            (@AgentName IS NULL OR AgentName   = @AgentName)
            AND (@SessionID IS NULL OR SessionID = @SessionID)
            AND (@StartDate IS NULL OR CAST(RequestTimestamp AS DATE) >= @StartDate)
            AND (@EndDate   IS NULL OR CAST(RequestTimestamp AS DATE) <= @EndDate)
        GROUP BY SessionID, AgentName
        ORDER BY SessionStart DESC;
    END
END;
GO

PRINT 'dw.usp_GetAgentUsage created.';
GO

-- ============================================================
-- Grant access to agents that need the usage view/SP
-- ReportingAgent reads rpt.vw_AgentUsage for dashboard queries
-- All agents can call the SP for self-monitoring
-- ============================================================

GRANT SELECT  ON rpt.vw_AgentUsage      TO agent_reporting;
GRANT SELECT  ON rpt.vw_AgentUsage      TO agent_orchestrator;
GRANT EXECUTE ON dw.usp_GetAgentUsage   TO agent_reporting;
GRANT EXECUTE ON dw.usp_GetAgentUsage   TO agent_orchestrator;
GO

PRINT '=== 11_agent_usage_views.sql complete ===';
GO
