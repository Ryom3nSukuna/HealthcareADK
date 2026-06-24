"""
OrchestratorAgent — routes user requests to domain agents and enforces token budgets.

Usage:
    python -m client.agents.orchestrator "Show me the denial rate for Medicare claims"
    python -m client.agents.orchestrator "Refresh the dashboard and show YoY margin" --session abc123
"""
import argparse
import importlib
import json
import sys
import uuid
from pathlib import Path

import yaml
from anthropic import Anthropic
from dotenv import load_dotenv

from engine.cache import cache_get, cache_get_semantic, cache_invalidate, cache_set, verify_equivalence

load_dotenv()

AGENTS_DIR = Path(__file__).parent
CONFIG_DIR = AGENTS_DIR / "config"

AGENT_MODULE_MAP = {
    "ClaimsAgent":    "claims_agent",
    "ClinicalAgent":  "clinical_agent",
    "FinancialAgent": "financial_agent",
    "ReportingAgent": "reporting_agent",
    "ETLAgent":       "etl_agent",
    "ProviderAgent":  "provider_agent",
}


def _load_config(name: str) -> dict:
    with open(CONFIG_DIR / f"{name}.yaml") as f:
        return yaml.safe_load(f)


def _route(user_request: str, client: Anthropic) -> dict:
    """Call Claude as OrchestratorAgent to get a routing decision."""
    config = _load_config("orchestrator")
    response = client.messages.create(
        model=config["model"],
        max_tokens=300,
        system=config["system_prompt"],
        messages=[{"role": "user", "content": user_request}],
    )
    try:
        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return json.loads(text)
    except (json.JSONDecodeError, IndexError, KeyError) as exc:
        return {"agents": [], "escalation": f"Routing parse error: {exc}"}


def _check_budget(agent_name: str, session_id: str) -> str | None:
    """Return an escalation message if the agent's budget is exhausted, else None."""
    try:
        from engine.budget_tracker import remaining, MIN_BUDGET_THRESHOLD
        tokens_left = remaining(agent_name, session_id)
        if tokens_left < MIN_BUDGET_THRESHOLD:
            config = _load_config(f"{AGENT_MODULE_MAP[agent_name]}")
            return (
                f"{agent_name} budget exhausted for session {session_id}. "
                f"Limit: {config['token_budget']:,} tokens. Remaining: {tokens_left:,}."
            )
    except ImportError:
        pass  # budget_tracker not yet built — skip enforcement
    return None


def _dispatch(agent_name: str, user_request: str, session_id: str, client: Anthropic) -> str:
    """Import and run a domain agent module. Checked against the Layer 2 response
    cache first — a hit returns instantly with zero API tokens spent."""
    module_key = AGENT_MODULE_MAP.get(agent_name)
    if not module_key:
        return f"[OrchestratorAgent] Unknown agent: {agent_name}"

    cached = cache_get(agent_name, user_request)
    if cached is not None:
        return cached

    # Layer 3 — only reached on an exact-match miss. cache_get_semantic() only ever
    # returns a *candidate*; verify_equivalence() is the mandatory fail-closed gate
    # that actually authorizes reuse. No similarity score alone serves a cached answer.
    semantic_hit = cache_get_semantic(agent_name, user_request)
    if semantic_hit is not None:
        candidate_response, matched_query = semantic_hit
        if verify_equivalence(client, user_request, matched_query):
            return (
                f"{candidate_response}\n\n"
                f'*(Answered using a cached response to a similar question: "{matched_query}")*'
            )

    budget_msg = _check_budget(agent_name, session_id)
    if budget_msg:
        return f"[OrchestratorAgent] {budget_msg}"

    try:
        module = importlib.import_module(f"client.agents.{module_key}")
    except ModuleNotFoundError:
        return f"[OrchestratorAgent] Agent module not yet built: agents/{module_key}.py"

    result = module.run(user_request, session_id, client)

    config = _load_config(module_key)
    cache_set(agent_name, user_request, result, config.get("cache_ttl_minutes", 30))

    # ETL runs invalidate clinical data freshness too — drop both caches so the
    # next query for either reflects the new load instead of a stale cached answer.
    if agent_name == "ETLAgent":
        cache_invalidate(["ETLAgent", "ClinicalAgent"])

    return result


def run_with_meta(user_request: str, session_id: str | None = None) -> tuple[str, list[str], str]:
    """Like run(), but also returns the agent names that handled the request and the
    session_id actually used (generated fresh if none was passed in). Used by the
    chat API, which needs to hand the session_id back to the client for the next turn."""
    session_id = session_id or str(uuid.uuid4())
    client = Anthropic()  # reads ANTHROPIC_API_KEY from environment

    routing = _route(user_request, client)

    if "escalation" in routing:
        return f"[OrchestratorAgent] {routing['escalation']}", [], session_id

    agents = routing.get("agents", [])
    rationale = routing.get("rationale", "")

    if not agents:
        return "[OrchestratorAgent] Could not determine which agent should handle this request.", [], session_id

    print(
        f"[OrchestratorAgent] session={session_id} → {', '.join(agents)} | {rationale}",
        file=sys.stderr,
    )

    results = []
    for agent_name in agents:
        result = _dispatch(agent_name, user_request, session_id, client)
        results.append((agent_name, result))

    if len(results) == 1:
        return results[0][1], agents, session_id

    # Multi-hop: combine with section headers
    sections = [f"### {name}\n\n{content}" for name, content in results]
    return "\n\n---\n\n".join(sections), agents, session_id


def run(user_request: str, session_id: str | None = None) -> str:
    text, _, _ = run_with_meta(user_request, session_id)
    return text


def main() -> None:
    parser = argparse.ArgumentParser(description="HealthcareADK OrchestratorAgent")
    parser.add_argument("request", help="User request in natural language")
    parser.add_argument("--session", default=None, help="Session ID for budget tracking")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    print(run(args.request, args.session))


if __name__ == "__main__":
    main()
