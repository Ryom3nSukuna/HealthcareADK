"""
Shared agentic loop for all domain agents.
Each domain agent calls run_agent() with its config and tools.
"""
import json

from anthropic import Anthropic

from engine.hook_runner import HookDenied, run_post_tool_use, run_pre_tool_use

MAX_ITERATIONS = 20


def _record_usage(
    agent_name: str,
    session_id: str,
    input_tokens: int,
    output_tokens: int,
    tool_calls: int,
    cached_tokens: int = 0,
) -> None:
    try:
        from engine.budget_tracker import record
        record(agent_name, session_id, input_tokens, output_tokens, tool_calls, cached_tokens=cached_tokens)
    except ImportError:
        pass  # budget_tracker not yet built


def run_agent(
    config: dict,
    tools: list[dict],
    user_request: str,
    session_id: str,
    client: Anthropic,
) -> str:
    """
    Agentic loop: call Claude, execute tool calls, repeat until end_turn.

    tools: list of {"definition": <Anthropic tool dict>, "fn": <callable>}
    """
    tool_defs = [t["definition"] for t in tools]
    tool_map = {t["definition"]["name"]: t["fn"] for t in tools}
    mcp_names = {t["definition"]["name"]: t.get("mcp_name", t["definition"]["name"]) for t in tools}

    messages = [{"role": "user", "content": user_request}]
    total_input = 0
    total_output = 0
    total_cached = 0
    tool_call_count = 0
    token_budget = int(config.get("token_budget", 20000))

    for _ in range(MAX_ITERATIONS):
        response = client.messages.create(
            model=config["model"],
            max_tokens=8192,
            # cache_control caches the compiled system prompt for 5 min; repeat calls
            # within that window pay ~10% on these input tokens instead of 100%.
            system=[{
                "type": "text",
                "text": config["system_prompt"],
                "cache_control": {"type": "ephemeral"},
            }],
            tools=tool_defs,
            messages=messages,
        )
        total_input += response.usage.input_tokens
        total_output += response.usage.output_tokens
        total_cached += response.usage.cache_read_input_tokens

        if response.stop_reason == "end_turn":
            text = next((b.text for b in response.content if b.type == "text"), "")
            _record_usage(config["name"], session_id, total_input, total_output, tool_call_count, total_cached)
            return text

        # Mid-dispatch budget check — fires only when more tool calls would follow.
        # A naturally completed dispatch (end_turn above) always returns its answer.
        if total_input + total_output > token_budget:
            _record_usage(config["name"], session_id, total_input, total_output, tool_call_count, total_cached)
            return (
                f"[{config['name']}] Token budget ({token_budget:,} tokens) exceeded mid-dispatch "
                f"({total_input + total_output:,} used). Stopping to prevent runaway spend. "
                f"Escalate to OrchestratorAgent or retry with a narrower query."
            )

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                tool_call_count += 1
                fn = tool_map.get(block.name)
                if fn:
                    mcp_name = mcp_names.get(block.name, block.name)
                    try:
                        run_pre_tool_use(mcp_name, block.input)
                        result = fn(**block.input)
                        run_post_tool_use(mcp_name, block.input, result)
                    except HookDenied as denied:
                        result = json.dumps({"error": f"Blocked by guard: {denied.reason}"})
                    except Exception as exc:
                        result = json.dumps({"error": str(exc)})
                else:
                    result = json.dumps({"error": f"Tool not available to this agent: {block.name}"})

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result if isinstance(result, str) else json.dumps(result, default=str),
                })

            messages.append({"role": "user", "content": tool_results})

        else:
            _record_usage(config["name"], session_id, total_input, total_output, tool_call_count, total_cached)
            return f"[{config['name']}] Unexpected stop reason: {response.stop_reason}"

    _record_usage(config["name"], session_id, total_input, total_output, tool_call_count, total_cached)
    return f"[{config['name']}] Max iterations ({MAX_ITERATIONS}) reached without a final answer."
