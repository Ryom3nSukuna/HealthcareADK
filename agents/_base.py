"""
Shared agentic loop for all HealthcareADK domain agents.
Each domain agent calls run_agent() with its config and tools.
"""
import json
from pathlib import Path

import yaml
from anthropic import Anthropic

CONFIG_DIR = Path(__file__).parent / "config"
MAX_ITERATIONS = 20


def load_config(name: str) -> dict:
    with open(CONFIG_DIR / f"{name}.yaml") as f:
        return yaml.safe_load(f)


def _record_usage(
    agent_name: str,
    session_id: str,
    input_tokens: int,
    output_tokens: int,
    tool_calls: int,
) -> None:
    try:
        from agents.budget_tracker import record
        record(agent_name, session_id, input_tokens, output_tokens, tool_calls)
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

    messages = [{"role": "user", "content": user_request}]
    total_input = 0
    total_output = 0
    tool_call_count = 0

    for _ in range(MAX_ITERATIONS):
        response = client.messages.create(
            model=config["model"],
            max_tokens=8192,
            system=config["system_prompt"],
            tools=tool_defs,
            messages=messages,
        )
        total_input += response.usage.input_tokens
        total_output += response.usage.output_tokens

        if response.stop_reason == "end_turn":
            text = next((b.text for b in response.content if b.type == "text"), "")
            _record_usage(config["name"], session_id, total_input, total_output, tool_call_count)
            return text

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                tool_call_count += 1
                fn = tool_map.get(block.name)
                if fn:
                    try:
                        result = fn(**block.input)
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
            _record_usage(config["name"], session_id, total_input, total_output, tool_call_count)
            return f"[{config['name']}] Unexpected stop reason: {response.stop_reason}"

    _record_usage(config["name"], session_id, total_input, total_output, tool_call_count)
    return f"[{config['name']}] Max iterations ({MAX_ITERATIONS}) reached without a final answer."
