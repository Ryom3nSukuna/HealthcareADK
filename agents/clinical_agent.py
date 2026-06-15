from agents._base import load_config, run_agent
from agents.tools.sql_tools import build_tools
from anthropic import Anthropic


def run(user_request: str, session_id: str, client: Anthropic) -> str:
    config = load_config("clinical_agent")
    tools = build_tools(config["allowed_tools"])
    return run_agent(config, tools, user_request, session_id, client)
