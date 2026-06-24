-- 13_semantic_cache.sql
-- DDL for Phase 8 Layer 3 semantic cache — adds an embedding column to dw.QueryCache.
-- Run after: 12_query_cache.sql

USE HealthcareADK;
GO

IF NOT EXISTS (
    SELECT 1
    FROM   sys.columns c
    JOIN   sys.tables  t ON t.object_id = c.object_id
    JOIN   sys.schemas s ON s.schema_id = t.schema_id
    WHERE  s.name = 'dw' AND t.name = 'QueryCache' AND c.name = 'Embedding'
)
BEGIN
    ALTER TABLE dw.QueryCache ADD Embedding VARBINARY(MAX) NULL;
    PRINT 'dw.QueryCache.Embedding added.';
END
ELSE
BEGIN
    PRINT 'dw.QueryCache.Embedding already exists — skipped.';
END
GO

-- No new GRANTs needed — agent_orchestrator already has SELECT/INSERT/DELETE
-- on the whole table from 12_query_cache.sql.

PRINT '=== 13_semantic_cache.sql complete ===';
GO
