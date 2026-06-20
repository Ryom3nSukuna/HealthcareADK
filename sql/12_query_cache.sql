-- 12_query_cache.sql
-- DDL for dw.QueryCache — Phase 7 Layer 2 response cache.
-- Run after: 11_agent_usage_views.sql

USE HealthcareADK;
GO

IF NOT EXISTS (
    SELECT 1
    FROM   sys.tables  t
    JOIN   sys.schemas s ON s.schema_id = t.schema_id
    WHERE  s.name = 'dw' AND t.name = 'QueryCache'
)
BEGIN
    CREATE TABLE dw.QueryCache (
        CacheID    INT IDENTITY(1,1)  NOT NULL,
        CacheKey   CHAR(64)           NOT NULL,   -- SHA-256 hex of "AgentName::normalized_query"
        AgentName  VARCHAR(50)        NOT NULL,
        Query      VARCHAR(2000)      NOT NULL,
        Response   NVARCHAR(MAX)      NOT NULL,
        CreatedAt  DATETIME2          NOT NULL  DEFAULT SYSDATETIME(),
        ExpiresAt  DATETIME2          NOT NULL,

        CONSTRAINT PK_QueryCache PRIMARY KEY CLUSTERED (CacheID)
    );

    -- Supports cache_get()'s point lookup
    CREATE NONCLUSTERED INDEX IX_QueryCache_Key
        ON dw.QueryCache (CacheKey, ExpiresAt)
        INCLUDE (Response);

    -- Supports cache_invalidate()'s bulk delete by agent (e.g. after a fresh ETL run)
    CREATE NONCLUSTERED INDEX IX_QueryCache_Agent
        ON dw.QueryCache (AgentName);

    PRINT 'dw.QueryCache created.';
END
ELSE
BEGIN
    PRINT 'dw.QueryCache already exists — skipped.';
END
GO

-- OrchestratorAgent owns all cache reads/writes/invalidation centrally
-- (see agents/cache.py) rather than granting every domain agent its own
-- DELETE rights on this table.
GRANT SELECT, INSERT, DELETE ON dw.QueryCache TO agent_orchestrator;
GO

PRINT '=== 12_query_cache.sql complete ===';
GO
