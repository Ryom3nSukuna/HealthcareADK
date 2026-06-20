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

import pytest

# Ensure project root is on sys.path when pytest is run from any directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(autouse=True)
def _no_real_cache():
    """orchestrator.py binds cache_get/cache_set/cache_invalidate via `from agents.cache
    import ...`, so they must be patched on agents.orchestrator (the importing module's
    namespace), not agents.cache. Applies to every test so none of them hit a real DB
    through the Layer 2 cache check."""
    with patch("agents.orchestrator.cache_get", return_value=None), \
         patch("agents.orchestrator.cache_set"), \
         patch("agents.orchestrator.cache_invalidate"):
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

        with patch("agents.orchestrator.Anthropic",
                   return_value=_mock_client(routing, agent_answer)):
            with patch("agents.budget_tracker.remaining", return_value=19_000):
                with patch("agents.budget_tracker.record"):
                    from agents.orchestrator import run
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

        with patch("agents.orchestrator.Anthropic",
                   return_value=_mock_client(routing, agent_answer)):
            with patch("agents.budget_tracker.remaining", return_value=19_000):
                with patch("agents.budget_tracker.record"):
                    from agents.orchestrator import run
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

        with patch("agents.orchestrator.Anthropic",
                   return_value=_mock_client(routing, fin_answer, rpt_answer)):
            with patch("agents.budget_tracker.remaining", return_value=19_000):
                with patch("agents.budget_tracker.record"):
                    from agents.orchestrator import run
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

        with patch("agents.orchestrator.Anthropic",
                   return_value=_mock_client(routing, resp_a, resp_b)):
            with patch("agents.budget_tracker.remaining", return_value=19_000):
                with patch("agents.budget_tracker.record"):
                    from agents.orchestrator import run
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
        from agents.budget_tracker import MIN_BUDGET_THRESHOLD

        routing = _routing_response(["ClaimsAgent"])

        client = _mock_client(routing)
        with patch("agents.orchestrator.Anthropic", return_value=client):
            with patch("agents.budget_tracker.remaining",
                       return_value=MIN_BUDGET_THRESHOLD - 1):
                from agents.orchestrator import run
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
        from agents.budget_tracker import MIN_BUDGET_THRESHOLD

        routing = _routing_response(["ClaimsAgent"])
        agent_answer = _text_response("Denial rate: 14.2%")

        with patch("agents.orchestrator.Anthropic",
                   return_value=_mock_client(routing, agent_answer)):
            with patch("agents.budget_tracker.remaining",
                       return_value=MIN_BUDGET_THRESHOLD + 5_000):
                with patch("agents.budget_tracker.record"):
                    from agents.orchestrator import run
                    result = run(
                        "What is the denial rate?",
                        session_id="t3-budget-ok",
                    )

        assert "denial" in result.lower()
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
        from agents._base import run_agent, load_config
        from agents.tools.sql_tools import build_tools

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
        with patch("agents.budget_tracker.record"):
            run_agent(config, tools, "Read the TMDL measures file.",
                      "t4-file-claim", client)

        contents = self._extract_tool_result_content(client.messages.create.call_args_list)
        assert any("not available" in c.lower() for c in contents), (
            f"Expected 'not available' in tool_result; got: {contents}"
        )

    def test_etl_agent_cannot_use_file_tool(self):
        """ETLAgent's allowed_tools are shell + SQL only — write_file must be blocked."""
        from agents._base import run_agent, load_config
        from agents.tools.shell_tools import build_tools as build_shell_tools
        from agents.tools.sql_tools import build_tools as build_sql_tools

        config = load_config("etl_agent")
        allowed = config["allowed_tools"]
        tools = build_shell_tools(allowed, config["db_login"]) + build_sql_tools(allowed, config["db_login"])

        tool_req = _tool_use_response(
            "write_file",
            {"path": "sql/injected.sql", "content": "DROP TABLE dw.FactClaims"},
        )
        final = _text_response("I cannot write files. That tool is not available to me.")

        client = _mock_client(tool_req, final)
        with patch("agents.budget_tracker.record"):
            run_agent(config, tools, "Write a SQL script to drop the claims table.",
                      "t4-file-etl", client)

        contents = self._extract_tool_result_content(client.messages.create.call_args_list)
        assert any("not available" in c.lower() for c in contents), (
            f"Expected 'not available' in tool_result; got: {contents}"
        )

    def test_reporting_agent_cannot_use_shell_etl_tool(self):
        """ReportingAgent cannot invoke run_ssis_package (shell ETL tool)."""
        from agents._base import run_agent, load_config
        from agents.tools.file_tools import build_tools as build_file_tools
        from agents.tools.shell_tools import build_tools as build_shell_tools
        from agents.tools.sql_tools import build_tools as build_sql_tools

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
        with patch("agents.budget_tracker.record"):
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

        with patch("agents.orchestrator.Anthropic", return_value=client):
            with patch("agents.orchestrator.cache_get",
                       return_value="CACHED: 14.2% denial rate") as mock_get, \
                 patch("agents.orchestrator.cache_set") as mock_set:
                from agents.orchestrator import run
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

        with patch("agents.orchestrator.Anthropic",
                   return_value=_mock_client(routing, agent_answer)):
            with patch("agents.orchestrator.cache_get", return_value=None), \
                 patch("agents.orchestrator.cache_set") as mock_set:
                with patch("agents.budget_tracker.remaining", return_value=19_000):
                    with patch("agents.budget_tracker.record"):
                        from agents.orchestrator import run
                        result = run("What is the denial rate?", session_id="t5-cache-miss")

        assert "denial" in result.lower()
        mock_set.assert_called_once()
        args, _ = mock_set.call_args
        assert args[0] == "ClaimsAgent"
        assert args[1] == "What is the denial rate?"
        assert args[3] == 30  # claims_agent.yaml cache_ttl_minutes
