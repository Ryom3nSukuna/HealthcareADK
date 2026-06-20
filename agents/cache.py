"""
Layer 2 response cache — dw.QueryCache.

Skips the Claude API entirely for an (agent, query) pair already answered within
its TTL window. Connects as agent_orchestrator, which owns all cache reads/writes/
invalidation centrally (see sql/12_query_cache.sql) rather than granting every
domain agent its own DELETE rights on this table.

Exports used by callers:
  cache_get(agent_name, query)                        -> cached response, or None on miss/expired
  cache_set(agent_name, query, response, ttl_minutes)  -> write/refresh a cache entry
  cache_invalidate(agent_names)                        -> delete all entries for the given agents
"""
import hashlib
import os

import pyodbc
from dotenv import load_dotenv

load_dotenv()


def _get_conn() -> pyodbc.Connection:
    server = os.environ["HEALTHCAREADK_SQL_SERVER"]
    db = os.environ["HEALTHCAREADK_SQL_DB"]
    pwd = os.environ["HEALTHCAREADK_PWD_AGENT_ORCHESTRATOR"]
    return pyodbc.connect(
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={server};DATABASE={db};UID=agent_orchestrator;PWD={pwd};"
    )


def _cache_key(agent_name: str, query: str) -> str:
    normalized = query.strip().lower()
    return hashlib.sha256(f"{agent_name}::{normalized}".encode()).hexdigest()


def cache_get(agent_name: str, query: str) -> str | None:
    """Return the cached response for (agent_name, query) if present and unexpired, else None."""
    key = _cache_key(agent_name, query)
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT Response FROM dw.QueryCache WHERE CacheKey = ? AND ExpiresAt > SYSDATETIME()",
            key,
        ).fetchone()
    return row[0] if row else None


def cache_set(agent_name: str, query: str, response: str, ttl_minutes: int) -> None:
    """Write or refresh a cache entry for (agent_name, query)."""
    key = _cache_key(agent_name, query)
    with _get_conn() as conn:
        conn.execute("DELETE FROM dw.QueryCache WHERE CacheKey = ?", key)
        conn.execute(
            """
            INSERT INTO dw.QueryCache (CacheKey, AgentName, Query, Response, ExpiresAt)
            VALUES (?, ?, ?, ?, DATEADD(MINUTE, ?, SYSDATETIME()))
            """,
            key,
            agent_name,
            query[:2000],
            response,
            ttl_minutes,
        )
        conn.commit()


def cache_invalidate(agent_names: list[str]) -> None:
    """Delete all cache entries for the given agents (e.g. after a fresh ETL run)."""
    if not agent_names:
        return
    placeholders = ",".join("?" for _ in agent_names)
    with _get_conn() as conn:
        conn.execute(f"DELETE FROM dw.QueryCache WHERE AgentName IN ({placeholders})", agent_names)
        conn.commit()
