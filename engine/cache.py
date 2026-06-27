"""
Layer 2 response cache — dw.QueryCache. Layer 3 semantic cache extensions (Phase 8)
are in the second half of this file.

Skips the Claude API entirely for an (agent, query) pair already answered within
its TTL window. Connects as agent_orchestrator, which owns all cache reads/writes/
invalidation centrally (see sql/12_query_cache.sql) rather than granting every
domain agent its own DELETE rights on this table.

Exports used by callers:
  cache_get(agent_name, query)                        -> cached response, or None on miss/expired
  cache_set(agent_name, query, response, ttl_minutes)  -> write/refresh a cache entry
  cache_invalidate(agent_names)                        -> delete all entries for the given agents
  cache_get_semantic(agent_name, query)                -> (response, matched_query), or None
  verify_equivalence(client, new_query, candidate_query) -> bool, fail-closed
"""
import hashlib
import os

import numpy as np
import pyodbc
from dotenv import load_dotenv

load_dotenv()

SIMILARITY_FLOOR = 0.75
# Empirically measured against all-MiniLM-L6-v2:
#   "...in ohio" vs "...in OH" (true paraphrase)                      -> 0.825
#   "Show me total patients from New York" vs "How many from state of NY" -> 0.798  (missed at 0.80, caught at 0.75)
#   "...in ohio" vs "NOT ...in ohio" (negation)                        -> 0.9495 (HIGHER than true paraphrase!)
#   "...in ohio" vs "...in Texas" (different state)                    -> 0.7254
#   "...in ohio" vs "...claims denied in ohio" (diff metric)           -> 0.6049
# The negation result is exactly why the floor only ever gates a *candidate* — it is
# not a safety boundary by itself. verify_equivalence() is the only thing that can
# authorize reuse; a floor this loose is fine precisely because nothing downstream
# trusts it alone.


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
    """Write or refresh a cache entry for (agent_name, query). Also stores an embedding
    for Layer 3 semantic lookup — fails soft: if embedding generation errors, the row
    is still written without one, so exact-match caching for it keeps working and it's
    just invisible to semantic search."""
    key = _cache_key(agent_name, query)

    embedding_bytes = None
    try:
        from engine.embeddings import embed
        embedding_bytes = np.asarray(embed(query), dtype=np.float32).tobytes()
    except Exception:
        pass

    with _get_conn() as conn:
        conn.execute("DELETE FROM dw.QueryCache WHERE CacheKey = ?", key)
        conn.execute(
            """
            INSERT INTO dw.QueryCache (CacheKey, AgentName, Query, Response, ExpiresAt, Embedding)
            VALUES (?, ?, ?, ?, DATEADD(MINUTE, ?, SYSDATETIME()), ?)
            """,
            key,
            agent_name,
            query[:2000],
            response,
            ttl_minutes,
            embedding_bytes,
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


# ----------------------------------------------------------------------
# Layer 3 — semantic cache (Phase 8)
# ----------------------------------------------------------------------

def cache_get_semantic(agent_name: str, query: str) -> tuple[str, str] | None:
    """Find the best semantically-similar cached response for (agent_name, query).

    Returns (response, matched_query) if the best candidate clears SIMILARITY_FLOOR,
    else None. This only ever returns a *candidate* — callers MUST still run
    verify_equivalence() before serving it; see agents/orchestrator.py:_dispatch().
    Table is TTL-bounded (15-60 min per agent), so a brute-force Python scan is
    always small and fast — no vector index needed at this scale.
    """
    if os.environ.get("HEALTHCAREADK_SEMANTIC_CACHE_ENABLED", "1") != "1":
        return None

    try:
        from engine.embeddings import embed
        query_vec = np.asarray(embed(query), dtype=np.float32)
    except Exception:
        return None

    with _get_conn() as conn:
        rows = conn.execute(
            """
            SELECT Query, Response, Embedding FROM dw.QueryCache
            WHERE AgentName = ? AND ExpiresAt > SYSDATETIME() AND Embedding IS NOT NULL
            """,
            agent_name,
        ).fetchall()

    best_score = -1.0
    best: tuple[str, str] | None = None
    for matched_query, response, embedding_bytes in rows:
        candidate_vec = np.frombuffer(embedding_bytes, dtype=np.float32)
        score = float(np.dot(query_vec, candidate_vec))  # both unit-normalized -> cosine sim
        if score > best_score:
            best_score = score
            best = (response, matched_query)

    if best is not None and best_score >= SIMILARITY_FLOOR:
        return best
    return None


_VERIFY_SYSTEM = (
    "Answer YES only if a correct, complete answer to Question B would also be a "
    "fully correct, complete answer to Question A -- same filters, scope, metric, "
    "time period, and location. If there is ANY difference in meaning or you are "
    "not completely certain, answer NO. Respond with exactly one word: YES or NO."
)


def verify_equivalence(client, new_query: str, candidate_query: str) -> bool:
    """Mandatory fail-closed gate before ever serving a semantic cache candidate.

    Anything other than an exact "YES" -- including a malformed response, an API
    error, or a timeout -- is treated as False. This is the single most important
    fail-closed point in the whole feature: no similarity score alone, however
    high, ever authorizes reuse on its own.
    """
    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=5,
            system=_VERIFY_SYSTEM,
            messages=[{
                "role": "user",
                "content": f"Question A: {new_query}\n\nQuestion B: {candidate_query}",
            }],
        )
        text = next((b.text for b in response.content if b.type == "text"), "")
        return text.strip().upper() == "YES"
    except Exception:
        return False
