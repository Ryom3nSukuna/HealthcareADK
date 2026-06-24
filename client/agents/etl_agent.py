from engine.base import run_agent
from client.agents.loader import load_config
from client.agents.tools.shell_tools import build_tools as build_shell_tools
from client.agents.tools.sql_tools import build_tools as build_sql_tools
from anthropic import Anthropic


def run(user_request: str, session_id: str, client: Anthropic) -> str:
    config = load_config("etl_agent")
    allowed = config["allowed_tools"]
    tools = build_shell_tools(allowed, config["db_login"]) + build_sql_tools(allowed, config["db_login"])
    return run_agent(config, tools, user_request, session_id, client)
