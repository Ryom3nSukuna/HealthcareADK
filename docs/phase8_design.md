# HealthcareADK — Phase 8 Design: Semantic Query Cache (Layer 3)

## Goal

Catch paraphrased repeat queries (synonyms, abbreviations, rewording) that Layer 2's exact-text-match cache misses — e.g. "total payments in ohio" vs "...in OH" — without ever risking a wrong answer served from a merely-similar cached response.

**Status:** 🔄 Planned, implementation in progress. Plan approved via `EnterPlanMode` on 2026-06-21.

---

## Context

Phase 7's Layer 2 response cache (`dw.QueryCache`, `agents/cache.py`) is an **exact-text-match** cache: the key is `SHA256(agent_name + "::" + query.strip().lower())`. Live testing surfaced its limitation directly — "Show me total payments made in ohio" and "...in OH" are semantically the same question but hash differently, producing two separate cache entries instead of one. That's expected behavior for what was built, not a bug (see [phase7_design.md § Layer 2](phase7_design.md#layer-2--response-cache-sql-server)), but it means a large class of real paraphrases never benefits from caching today.

The goal of Phase 8 is to catch those paraphrases — **without ever risking a wrong answer**. A semantic-cache false positive (serving a cached answer to a question that only *resembles* the original) is worse than a cache miss: a miss just costs a normal API call, but a false positive looks like a confident, correct answer that's actually wrong. So the entire design is built around **failing closed**: any uncertainty anywhere in the pipeline falls through to a fresh agent dispatch, never to a guessed reuse.

**Decisions confirmed with the user before implementation:**

- Embeddings: **local model** (`sentence-transformers`, `all-MiniLM-L6-v2`) — no new vendor, no new API key, consistent with this project depending only on Anthropic for AI.
- Scope: **all 6 domain agents** (no carve-out for ClinicalAgent, despite patient-adjacent data — uniform scope chosen over extra restriction).

---

## Architecture

Three-stage fallback inside `agents/orchestrator.py:_dispatch()`, only reached on a Layer 2 exact-match miss (the existing fast/zero-risk path is untouched):

```
1. Exact match (existing, unchanged)        cache_get(agent_name, query)
       │ miss
       ▼
2. Semantic candidate retrieval (new)        cache_get_semantic(agent_name, query)
       │ candidate found (cosine similarity >= floor)
       ▼
3. LLM equivalence verification (new)        verify_equivalence(client, query, candidate_query)
       │ YES, exactly equivalent
       ▼
   Return candidate's cached response (0 domain-agent tokens spent)
```

If stage 2 finds no candidate above the similarity floor, or stage 3 returns anything other than an unambiguous "YES", execution falls straight through to the existing budget-check → dispatch → `cache_set()` path. **No similarity-only shortcut ever serves a cached answer — verification is mandatory on every semantic hit, with no exception for very-high-similarity scores.** That's the core mechanism for approaching zero false positives: embeddings only generate *candidates*; a dedicated, strict LLM check is what actually authorizes reuse, and it's instructed to default to "NO" on any doubt about scope, filters, time period, or interpretation.

---

## New file: `agents/embeddings.py`

```python
_model = None  # lazy singleton — avoid loading torch/sentence-transformers at import time

def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model

def embed(text: str) -> np.ndarray:
    return _get_model().encode(text, normalize_embeddings=True)  # unit-norm -> cosine sim = dot product
```

Lazy import keeps unit tests (which mock this module entirely) from ever loading the real model. `all-MiniLM-L6-v2` is small (~80MB, one-time download to the user's local HF cache), fast on CPU, and a standard choice for short-text similarity.

---

## `sql/13_semantic_cache.sql` (new, idempotent)

Mirrors the `CachedTokens` column pattern from `sql/09_agent_usage_log.sql`:

```sql
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('dw.QueryCache') AND name = 'Embedding')
BEGIN
    ALTER TABLE dw.QueryCache ADD Embedding VARBINARY(MAX) NULL;
END
```

No new GRANTs needed — `agent_orchestrator` already has SELECT/INSERT/DELETE on the whole table (see `sql/12_query_cache.sql`).

---

## `agents/cache.py` — extensions

- **`cache_set()`**: after the existing INSERT, also compute `embed(query)`, serialize via `np.asarray(vec, dtype=np.float32).tobytes()`, store in the new `Embedding` column. Wrapped in try/except — **fails soft on write** (if embedding generation errors, the row is still written without an embedding; exact-match caching for it keeps working, it's just invisible to semantic search).
- **New `cache_get_semantic(agent_name, query, similarity_floor=0.85) -> tuple[str, str] | None`:**
  1. `SELECT Query, Response, Embedding FROM dw.QueryCache WHERE AgentName = ? AND ExpiresAt > SYSDATETIME() AND Embedding IS NOT NULL`
  2. Embed the incoming query, compute cosine similarity (dot product, since vectors are pre-normalized) against each candidate in Python — table size is TTL-bounded (15–60 min) so this is always a small, fast scan; no vector index needed at this scale.
  3. Return the best-scoring `(response, matched_query)` pair if its score clears `similarity_floor`, else `None`.
- **New `verify_equivalence(client, new_query, candidate_query) -> bool`:**
  - Single Claude **Haiku** call (`claude-haiku-4-5-20251001` — cheap/fast, this is a pure classification task), strict fail-closed prompt:
    > Answer YES only if a correct, complete answer to Question B would also be a fully correct, complete answer to Question A — same filters, scope, metric, time period, and location. If there is ANY difference in meaning or you are not completely certain, answer NO. Respond with exactly one word: YES or NO.
  - Parsing: `response.strip().upper() == "YES"` — anything else (including a malformed response, an API error, a timeout) is caught and treated as `False`. **This is the single most important fail-closed point in the whole feature.**
- **New env-var kill switch:** `HEALTHCAREADK_SEMANTIC_CACHE_ENABLED` (default `"1"`). If `"0"`, `cache_get_semantic()` short-circuits to `None` immediately — an instant way to disable Layer 3 without a code change while leaving Layer 2 exact-match untouched, given how new and trust-sensitive this feature is.

---

## `agents/orchestrator.py` — extend `_dispatch()`

```python
cached = cache_get(agent_name, user_request)
if cached is not None:
    return cached

candidate = cache_get_semantic(agent_name, user_request)
if candidate is not None:
    candidate_response, matched_query = candidate
    if verify_equivalence(client, user_request, matched_query):
        return f"{candidate_response}\n\n*(Answered using a cached response to a similar question: \"{matched_query}\")*"

budget_msg = _check_budget(agent_name, session_id)
...  # existing dispatch + cache_set, unchanged
```

The appended note on a semantic hit is a deliberate transparency choice: it costs nothing, and it gives the user (visible in the chat UI) a clear signal that this specific answer was reused rather than freshly computed, so they can sanity-check it if the topic is sensitive enough to warrant it.

---

## Dependencies

`requirements.txt` gains `sentence-transformers` (pulls in `torch` transitively). The first call downloads the `all-MiniLM-L6-v2` model (~80MB) to the local Hugging Face cache and needs internet access once.

---

## Testing

**Unit tests** (`tests/test_phase6.py`) — extend the existing `_no_real_cache` autouse fixture to also patch `agents.orchestrator.cache_get_semantic` and `agents.orchestrator.verify_equivalence`, so no test ever loads the real model or hits a real DB/API (matches the existing pattern for `cache_get`/`cache_set`/`cache_invalidate`). New `TestSemanticCache` class:

- Exact-match hit still short-circuits before semantic check is even consulted (regression guard).
- Semantic candidate + `verify_equivalence` → `True` returns the candidate response, domain agent never dispatched.
- Semantic candidate + `verify_equivalence` → `False` falls through to a normal fresh dispatch.
- No candidate (`cache_get_semantic` → `None`) falls through to a normal fresh dispatch.
- Pure cosine-similarity math (`cache_get_semantic`'s scoring) is also tested directly with hand-crafted vectors — deterministic, no model needed.

**Live verification** (same pattern used for Layer 2 in Phase 7):

1. Deploy `sql/13_semantic_cache.sql`.
2. Ask "Show me total payments made in ohio", then "...in OH" — confirm the second call returns the same answer with **zero new FinancialAgent tokens** in `dw.AgentUsageLog` (only the small Haiku verification cost), proving the semantic hit worked.
3. Ask a deliberately *similar-but-different* follow-up (e.g., "total payments NOT in Ohio", or a different state) — confirm `verify_equivalence` correctly returns `False` and a fresh dispatch happens. This is the direct test of the false-positive-prevention mechanism.
4. Confirm `HEALTHCAREADK_SEMANTIC_CACHE_ENABLED=0` fully disables Layer 3 while Layer 2 exact-match keeps working.

---

## Explicitly deferred (not in this phase)

- Per-agent opt-out config (`semantic_cache_enabled` in YAML) — not needed since scope is all 6 agents by decision; can be added later if that changes.
- A real vector index (e.g., SQL Server native `VECTOR` type) — unnecessary at the current TTL-bounded cache scale; brute-force Python scan is simpler and sufficient.
- Logging verification-call token cost into `dw.AgentUsageLog` under its own line item — verification is cheap and orchestrator-owned, not charged against the domain agent's budget; can be added later if cost visibility becomes a concern.

---

## Tasks

See [docs/plan.md § Phase 8](plan.md) for the full task checklist.
