"""
Phase 6 end-to-end tests.

Run from project root:
    pytest tests/test_phase6.py -v

Test coverage:
  1. SingleAgentRouting  — OrchestratorAgent routes to the correct domain agent
  2. MultiHopDispatch    — Two-agent queries produce merged, section-headed output
  3. BudgetEscalation   — Exhausted budget blocks dispatch and returns escalation message
  4. ToolIsolation       — Agents cannot invoke tools outside their allowed_tools list
  5. ResponseCache       — Layer 2 cache hit skips dispatch; miss dispatches and writes
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# Ensure project root is on sys.path when pytest is run from any directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(autouse=True)
def _no_real_cache():
    """orchestrator.py binds cache_get/cache_set/cache_invalidate/cache_get_semantic/
    verify_equivalence via `from engine.cache import ...`, so they must be patched on
    agents.orchestrator (the importing module's namespace), not engine.cache. Applies
    to every test so none of them hit a real DB or load the real embedding model
    through any cache layer."""
    with patch("client.agents.orchestrator.cache_get", return_value=None), \
         patch("client.agents.orchestrator.cache_set"), \
         patch("client.agents.orchestrator.cache_invalidate"), \
         patch("client.agents.orchestrator.cache_get_semantic", return_value=None), \
         patch("client.agents.orchestrator.verify_equivalence", return_value=False):
        yield


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _text_response(text: str, input_tokens: int = 200, output_tokens: int = 100, cached_tokens: int = 0):
    """Minimal mock of an Anthropic end_turn message with one text block."""
    msg = MagicMock()
    msg.stop_reason = "end_turn"
    msg.usage.input_tokens = input_tokens
    msg.usage.output_tokens = output_tokens
    msg.usage.cache_read_input_tokens = cached_tokens
    block = MagicMock()
    block.type = "text"
    block.text = text
    msg.content = [block]
    return msg


def _routing_response(agents: list, rationale: str = "test routing"):
    """Orchestrator routing response: JSON payload in a text block."""
    payload = json.dumps({"agents": agents, "rationale": rationale})
    return _text_response(payload)


def _tool_use_response(tool_name: str, tool_input: dict, tool_id: str = "tu_001"):
    """Mock tool_use stop — Claude requests a tool call."""
    msg = MagicMock()
    msg.stop_reason = "tool_use"
    msg.usage.input_tokens = 150
    msg.usage.output_tokens = 60
    msg.usage.cache_read_input_tokens = 0

    block = MagicMock()
    block.type = "tool_use"
    block.name = tool_name
    block.input = tool_input
    block.id = tool_id
    msg.content = [block]
    return msg


def _mock_client(*side_effects):
    """Anthropic client mock whose messages.create() yields responses in order."""
    client = MagicMock()
    client.messages.create.side_effect = list(side_effects)
    return client


# ---------------------------------------------------------------------------
# 1. Single-agent routing
# ---------------------------------------------------------------------------

class TestSingleAgentRouting:
    """OrchestratorAgent routes domain-specific queries to the correct agent."""

    def test_claims_query_dispatched_to_claims_agent(self):
        routing = _routing_response(
            ["ClaimsAgent"], rationale="'denial rate' → ClaimsAgent"
        )
        agent_answer = _text_response(
            "| PayerType | DenialRate |\n|---|---|\n| Medicare | 12.3% |"
        )

        with patch("client.agents.orchestrator.Anthropic",
                   return_value=_mock_client(routing, agent_answer)):
            with patch("engine.budget_tracker.remaining", return_value=19_000):
                with patch("engine.budget_tracker.record"):
                    from client.agents.orchestrator import run
                    result = run(
                        "What is the denial rate for Medicare claims?",
                        session_id="t1-claims",
                    )

        assert "DenialRate" in result or "denial" in result.lower()
        assert "escalat" not in result.lower()

    def test_financial_query_dispatched_to_financial_agent(self):
        routing = _routing_response(
            ["FinancialAgent"], rationale="'revenue' → FinancialAgent"
        )
        agent_answer = _text_response(
            "| FiscalYear | Revenue | Expense |\n|---|---|---|\n| 2024 | $5M | $4M |"
        )

        with patch("client.agents.orchestrator.Anthropic",
                   return_value=_mock_client(routing, agent_answer)):
            with patch("engine.budget_tracker.remaining", return_value=19_000):
                with patch("engine.budget_tracker.record"):
                    from client.agents.orchestrator import run
                    result = run(
                        "Show total revenue vs expenses for 2024.",
                        session_id="t1-financial",
                    )

        assert "Revenue" in result or "revenue" in result.lower()
        assert "escalat" not in result.lower()


# ---------------------------------------------------------------------------
# 2. Multi-hop dispatch
# ---------------------------------------------------------------------------

class TestMultiHopDispatch:
    """Multi-intent queries dispatch to two agents and merge results with
    '### AgentName' section headers separated by '---'."""

    def test_two_agents_merged_with_headers(self):
        routing = _routing_response(
            ["FinancialAgent", "ReportingAgent"],
            rationale="'margin' → FinancialAgent; 'dashboard' → ReportingAgent",
        )
        fin_answer = _text_response("Net margin for 2024 was 18.4%.")
        rpt_answer = _text_response("Power BI dataset refresh triggered successfully.")

        with patch("client.agents.orchestrator.Anthropic",
                   return_value=_mock_client(routing, fin_answer, rpt_answer)):
            with patch("engine.budget_tracker.remaining", return_value=19_000):
                with patch("engine.budget_tracker.record"):
                    from client.agents.orchestrator import run
                    result = run(
                        "Show the net margin trend and refresh the Power BI dashboard.",
                        session_id="t2-multihop",
                    )

        assert "### FinancialAgent" in result
        assert "### ReportingAgent" in result
        assert "margin" in result.lower()
        assert "Power BI" in result or "refresh" in result.lower()

    def test_multi_hop_includes_section_separator(self):
        routing = _routing_response(["ClaimsAgent", "ClinicalAgent"])
        resp_a = _text_response("Claims result.")
        resp_b = _text_response("Clinical result.")

        with patch("client.agents.orchestrator.Anthropic",
                   return_value=_mock_client(routing, resp_a, resp_b)):
            with patch("engine.budget_tracker.remaining", return_value=19_000):
                with patch("engine.budget_tracker.record"):
                    from client.agents.orchestrator import run
                    result = run(
                        "Show claims denial rates and abnormal lab trends.",
                        session_id="t2-separator",
                    )

        assert "---" in result
        assert "### ClaimsAgent" in result
        assert "### ClinicalAgent" in result


# ---------------------------------------------------------------------------
# 3. Budget escalation
# ---------------------------------------------------------------------------

class TestBudgetEscalation:
    """When remaining tokens fall below MIN_BUDGET_THRESHOLD, the orchestrator
    returns an escalation message and does not call the domain agent."""

    def test_exhausted_budget_blocks_dispatch(self):
        from engine.budget_tracker import MIN_BUDGET_THRESHOLD

        routing = _routing_response(["ClaimsAgent"])

        client = _mock_client(routing)
        with patch("client.agents.orchestrator.Anthropic", return_value=client):
            with patch("engine.budget_tracker.remaining",
                       return_value=MIN_BUDGET_THRESHOLD - 1):
                from client.agents.orchestrator import run
                result = run(
                    "What is the denial rate for Medicare claims?",
                    session_id="t3-budget-exhausted",
                )

        # Escalation message returned
        assert "budget" in result.lower()
        # Domain agent was never called — only the routing call happened
        assert client.messages.create.call_count == 1
        # No agent result content leaked through
        assert "DenialRate" not in result

    def test_sufficient_budget_dispatches_normally(self):
        from engine.budget_tracker import MIN_BUDGET_THRESHOLD

        routing = _routing_response(["ClaimsAgent"])
        agent_answer = _text_response("Denial rate: 14.2%")

        with patch("client.agents.orchestrator.Anthropic",
                   return_value=_mock_client(routing, agent_answer)):
            with patch("engine.budget_tracker.remaining",
                       return_value=MIN_BUDGET_THRESHOLD + 5_000):
                with patch("engine.budget_tracker.record"):
                    from client.agents.orchestrator import run
                    result = run(
                        "What is the denial rate?",
                        session_id="t3-budget-ok",
                    )

        assert "denial" in result.lower()
        assert "budget" not in result.lower()


# ---------------------------------------------------------------------------
# 3b. Mid-dispatch budget enforcement (_base.py)
# ---------------------------------------------------------------------------

class TestMidDispatchBudget:
    """A single dispatch that accumulates tokens exceeding the per-agent budget
    mid-loop should halt before the next tool iteration and return an escalation
    message, not silently run to completion."""

    @staticmethod
    def _minimal_config(budget: int = 1000) -> dict:
        return {
            "name": "ClaimsAgent",
            "model": "claude-sonnet-4-6",
            "system_prompt": "test prompt",
            "token_budget": budget,
        }

    def test_halts_when_budget_exceeded_mid_tool_loop(self):
        """First response is tool_use and burns > budget tokens — loop must stop
        before a second API call."""
        from anthropic import Anthropic
        from engine.base import run_agent

        tool_resp = _tool_use_response(
            "execute_query", {"sql": "SELECT 1"}, tool_id="tu_mid_budget"
        )
        # Make the first call exceed the 1 000-token budget
        tool_resp.usage.input_tokens = 800
        tool_resp.usage.output_tokens = 400  # total = 1200 > 1000

        client = _mock_client(tool_resp)

        tools = [{
            "definition": {"name": "execute_query", "description": "run sql",
                           "input_schema": {"type": "object", "properties": {}, "required": []}},
            "fn": lambda **_: "[]",
        }]

        with patch("engine.base._record_usage") as mock_record:
            result = run_agent(
                self._minimal_config(budget=1000),
                tools,
                "test query",
                "test-mid-budget-session",
                client,
            )

        # Only one API call — loop stopped before making a second
        assert client.messages.create.call_count == 1
        # Escalation message surfaced
        assert "budget" in result.lower()
        assert "exceeded" in result.lower()
        # Usage was still recorded despite the early exit
        mock_record.assert_called_once()

    def test_does_not_halt_when_within_budget(self):
        """Normal dispatch completing within budget reaches end_turn normally."""
        from engine.base import run_agent

        tool_resp = _tool_use_response("execute_query", {"sql": "SELECT 1"})
        # 150 + 60 = 210 tokens, well under a 1000-token budget
        end_resp = _text_response("Result: 42")

        client = _mock_client(tool_resp, end_resp)

        tools = [{
            "definition": {"name": "execute_query", "description": "run sql",
                           "input_schema": {"type": "object", "properties": {}, "required": []}},
            "fn": lambda **_: "[]",
        }]

        with patch("engine.base._record_usage"):
            result = run_agent(
                self._minimal_config(budget=1000),
                tools,
                "test query",
                "test-mid-budget-ok",
                client,
            )

        assert client.messages.create.call_count == 2
        assert "42" in result
        assert "budget" not in result.lower()


# ---------------------------------------------------------------------------
# 4. Tool isolation
# ---------------------------------------------------------------------------

class TestToolIsolation:
    """When Claude requests a tool that is not in the agent's allowed_tools list,
    the agentic loop returns a 'Tool not available' error as the tool_result
    (sent back to Claude) rather than executing the tool."""

    @staticmethod
    def _extract_tool_result_content(call_args_list) -> list[str]:
        """Pull tool_result content strings from the second messages.create() call."""
        messages = call_args_list[1].kwargs["messages"]
        tool_result_msg = messages[-1]  # appended last by the loop
        assert tool_result_msg["role"] == "user"
        return [
            item.get("content", "")
            for item in tool_result_msg["content"]
            if isinstance(item, dict) and item.get("type") == "tool_result"
        ]

    def test_claims_agent_cannot_use_file_tool(self):
        """ClaimsAgent's allowed_tools are SQL-only.
        A Claude request for 'read_file' must return 'not available'."""
        from engine.base import run_agent
        from client.agents.loader import load_config
        from client.agents.tools.sql_tools import build_tools

        config = load_config("claims_agent")
        tools = build_tools(config["allowed_tools"], config["db_login"])

        # Claude first requests a file tool (not in ClaimsAgent's allowlist)
        tool_req = _tool_use_response(
            "read_file",
            {"path": "powerbi/tmdl/tables/_Measures.tmdl"},
        )
        # Then produces a final text answer after seeing the error
        final = _text_response("I cannot access file tools. I'll use SQL instead.")

        client = _mock_client(tool_req, final)
        with patch("engine.budget_tracker.record"):
            run_agent(config, tools, "Read the TMDL measures file.",
                      "t4-file-claim", client)

        contents = self._extract_tool_result_content(client.messages.create.call_args_list)
        assert any("not available" in c.lower() for c in contents), (
            f"Expected 'not available' in tool_result; got: {contents}"
        )

    def test_etl_agent_cannot_use_file_tool(self):
        """ETLAgent's allowed_tools are shell + SQL only — write_file must be blocked."""
        from engine.base import run_agent
        from client.agents.loader import load_config
        from client.agents.tools.shell_tools import build_tools as build_shell_tools
        from client.agents.tools.sql_tools import build_tools as build_sql_tools

        config = load_config("etl_agent")
        allowed = config["allowed_tools"]
        tools = build_shell_tools(allowed, config["db_login"]) + build_sql_tools(allowed, config["db_login"])

        tool_req = _tool_use_response(
            "write_file",
            {"path": "sql/injected.sql", "content": "DROP TABLE dw.FactClaims"},
        )
        final = _text_response("I cannot write files. That tool is not available to me.")

        client = _mock_client(tool_req, final)
        with patch("engine.budget_tracker.record"):
            run_agent(config, tools, "Write a SQL script to drop the claims table.",
                      "t4-file-etl", client)

        contents = self._extract_tool_result_content(client.messages.create.call_args_list)
        assert any("not available" in c.lower() for c in contents), (
            f"Expected 'not available' in tool_result; got: {contents}"
        )

    def test_reporting_agent_cannot_use_shell_etl_tool(self):
        """ReportingAgent cannot invoke run_ssis_package (shell ETL tool)."""
        from engine.base import run_agent
        from client.agents.loader import load_config
        from client.agents.tools.file_tools import build_tools as build_file_tools
        from client.agents.tools.shell_tools import build_tools as build_shell_tools
        from client.agents.tools.sql_tools import build_tools as build_sql_tools

        config = load_config("reporting_agent")
        allowed = config["allowed_tools"]
        tools = (
            build_sql_tools(allowed, config["db_login"])
            + build_file_tools(allowed)
            + build_shell_tools(allowed, config["db_login"])
        )

        tool_req = _tool_use_response(
            "run_ssis_package",
            {"package_path": "ssis/Package_Master.dtsx"},
        )
        final = _text_response("That tool is not available to me.")

        client = _mock_client(tool_req, final)
        with patch("engine.budget_tracker.record"):
            run_agent(config, tools, "Run the master SSIS package.",
                      "t4-ssis-reporting", client)

        contents = self._extract_tool_result_content(client.messages.create.call_args_list)
        assert any("not available" in c.lower() for c in contents), (
            f"Expected 'not available' in tool_result; got: {contents}"
        )


# ---------------------------------------------------------------------------
# 5. Response cache (Layer 2)
# ---------------------------------------------------------------------------

class TestResponseCache:
    """Layer 2 response cache short-circuits dispatch on a hit and writes a
    fresh entry (with the agent's configured TTL) on a miss."""

    def test_cache_hit_skips_dispatch_and_domain_agent_api_call(self):
        routing = _routing_response(["ClaimsAgent"], rationale="'denial rate' -> ClaimsAgent")
        client = _mock_client(routing)  # only the routing call should ever fire

        with patch("client.agents.orchestrator.Anthropic", return_value=client):
            with patch("client.agents.orchestrator.cache_get",
                       return_value="CACHED: 14.2% denial rate") as mock_get, \
                 patch("client.agents.orchestrator.cache_set") as mock_set:
                from client.agents.orchestrator import run
                result = run("What is the denial rate for Medicare claims?", session_id="t5-cache-hit")

        assert result == "CACHED: 14.2% denial rate"
        # Only the routing call happened — _dispatch() returned on the cache hit
        # before ever importing/calling the domain agent module.
        assert client.messages.create.call_count == 1
        mock_get.assert_called_once_with("ClaimsAgent", "What is the denial rate for Medicare claims?")
        mock_set.assert_not_called()

    def test_cache_miss_dispatches_and_writes_with_configured_ttl(self):
        routing = _routing_response(["ClaimsAgent"])
        agent_answer = _text_response("Denial rate: 14.2%")

        with patch("client.agents.orchestrator.Anthropic",
                   return_value=_mock_client(routing, agent_answer)):
            with patch("client.agents.orchestrator.cache_get", return_value=None), \
                 patch("client.agents.orchestrator.cache_set") as mock_set:
                with patch("engine.budget_tracker.remaining", return_value=19_000):
                    with patch("engine.budget_tracker.record"):
                        from client.agents.orchestrator import run
                        result = run("What is the denial rate?", session_id="t5-cache-miss")

        assert "denial" in result.lower()
        mock_set.assert_called_once()
        args, _ = mock_set.call_args
        assert args[0] == "ClaimsAgent"
        assert args[1] == "What is the denial rate?"
        assert args[3] == 30  # claims_agent.yaml cache_ttl_minutes


# ---------------------------------------------------------------------------
# 6. Semantic cache (Layer 3, Phase 8)
# ---------------------------------------------------------------------------

class TestSemanticCache:
    """A semantic candidate is only ever served after a mandatory verify_equivalence()
    check returns True — embedding similarity alone never authorizes reuse."""

    def test_exact_match_hit_skips_semantic_check_entirely(self):
        routing = _routing_response(["ClaimsAgent"])
        client = _mock_client(routing)

        with patch("client.agents.orchestrator.Anthropic", return_value=client):
            with patch("client.agents.orchestrator.cache_get", return_value="EXACT HIT"), \
                 patch("client.agents.orchestrator.cache_get_semantic") as mock_semantic:
                from client.agents.orchestrator import run
                result = run("What is the denial rate?", session_id="t6-exact-skips-semantic")

        assert result == "EXACT HIT"
        mock_semantic.assert_not_called()

    def test_semantic_candidate_verified_true_returns_candidate_without_dispatch(self):
        routing = _routing_response(["FinancialAgent"])
        client = _mock_client(routing)  # only the routing call should ever fire

        with patch("client.agents.orchestrator.Anthropic", return_value=client):
            with patch("client.agents.orchestrator.cache_get", return_value=None), \
                 patch("client.agents.orchestrator.cache_get_semantic",
                       return_value=("Total payments: $4.2M", "total payments made in ohio")), \
                 patch("client.agents.orchestrator.verify_equivalence", return_value=True) as mock_verify, \
                 patch("client.agents.orchestrator.cache_set") as mock_set:
                from client.agents.orchestrator import run
                result = run("total payments made in OH", session_id="t6-semantic-hit")

        assert "Total payments: $4.2M" in result
        assert "similar question" in result.lower()
        mock_verify.assert_called_once()
        assert client.messages.create.call_count == 1  # routing only — domain agent never dispatched
        mock_set.assert_not_called()  # served from cache, nothing new to write

    def test_semantic_candidate_verified_false_falls_through_to_fresh_dispatch(self):
        routing = _routing_response(["FinancialAgent"])
        agent_answer = _text_response("Total payments NOT in Ohio: $9.1M")

        with patch("client.agents.orchestrator.Anthropic",
                   return_value=_mock_client(routing, agent_answer)):
            with patch("client.agents.orchestrator.cache_get", return_value=None), \
                 patch("client.agents.orchestrator.cache_get_semantic",
                       return_value=("Total payments: $4.2M", "total payments made in ohio")), \
                 patch("client.agents.orchestrator.verify_equivalence", return_value=False), \
                 patch("client.agents.orchestrator.cache_set") as mock_set:
                with patch("engine.budget_tracker.remaining", return_value=19_000):
                    with patch("engine.budget_tracker.record"):
                        from client.agents.orchestrator import run
                        result = run("total payments NOT in ohio", session_id="t6-semantic-rejected")

        assert "NOT in Ohio" in result
        mock_set.assert_called_once()  # fresh dispatch result gets cached normally

    def test_no_semantic_candidate_falls_through_to_fresh_dispatch(self):
        routing = _routing_response(["FinancialAgent"])
        agent_answer = _text_response("Total payments: $4.2M")

        with patch("client.agents.orchestrator.Anthropic",
                   return_value=_mock_client(routing, agent_answer)):
            with patch("client.agents.orchestrator.cache_get", return_value=None), \
                 patch("client.agents.orchestrator.cache_get_semantic", return_value=None), \
                 patch("client.agents.orchestrator.cache_set") as mock_set:
                with patch("engine.budget_tracker.remaining", return_value=19_000):
                    with patch("engine.budget_tracker.record"):
                        from client.agents.orchestrator import run
                        result = run("total payments made in ohio", session_id="t6-no-candidate")

        assert "4.2M" in result
        mock_set.assert_called_once()


class TestSemanticCacheScoring:
    """Pure cosine-similarity math in engine.cache.cache_get_semantic() — hand-crafted
    vectors, no real model or DB. Tests the function directly (not via orchestrator),
    so the autouse _no_real_cache patch doesn't apply here."""

    @staticmethod
    def _mock_conn(rows):
        conn = MagicMock()
        conn.__enter__.return_value = conn
        conn.__exit__.return_value = False
        conn.execute.return_value.fetchall.return_value = rows
        return conn

    def test_best_candidate_above_floor_is_returned(self):
        from engine.cache import cache_get_semantic

        query_vec = np.array([1.0, 0.0], dtype=np.float32)
        close_vec = np.array([0.99, 0.14107], dtype=np.float32)  # cos ~0.99, above floor
        far_vec = np.array([0.0, 1.0], dtype=np.float32)         # cos 0.0, below floor

        rows = [
            ("a different question", "far response", far_vec.tobytes()),
            ("a very similar question", "close response", close_vec.tobytes()),
        ]

        with patch("engine.cache._get_conn", return_value=self._mock_conn(rows)), \
             patch("engine.embeddings.embed", return_value=query_vec):
            result = cache_get_semantic("FinancialAgent", "a similar question")

        assert result == ("close response", "a very similar question")

    def test_no_candidate_clears_floor_returns_none(self):
        from engine.cache import cache_get_semantic

        query_vec = np.array([1.0, 0.0], dtype=np.float32)
        far_vec = np.array([0.0, 1.0], dtype=np.float32)
        rows = [("unrelated question", "unrelated response", far_vec.tobytes())]

        with patch("engine.cache._get_conn", return_value=self._mock_conn(rows)), \
             patch("engine.embeddings.embed", return_value=query_vec):
            result = cache_get_semantic("FinancialAgent", "totally different topic")

        assert result is None

    def test_kill_switch_disables_semantic_lookup(self):
        from engine.cache import cache_get_semantic

        with patch.dict("os.environ", {"HEALTHCAREADK_SEMANTIC_CACHE_ENABLED": "0"}):
            result = cache_get_semantic("FinancialAgent", "anything")

        assert result is None
