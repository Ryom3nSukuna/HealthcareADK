"""
Budget tracker — logs token usage to dw.AgentUsageLog and enforces per-agent session budgets.

Exports used by callers:
  record()              → called by engine/base.py after every Claude call
  remaining()           → called by agents/orchestrator.py before dispatch
  session_summary()     → called by end-to-end tests / usage dashboard
  MIN_BUDGET_THRESHOLD  → imported by agents/orchestrator.py
"""
import os
import re
from pathlib import Path

import pyodbc
import yaml
from dotenv import load_dotenv

load_dotenv()

MIN_BUDGET_THRESHOLD = 2000  # escalate when tokens remaining fall below this

# HEALTHCAREADK_AGENT_CONFIG_DIR overrides the default client-pack convention
# that agent YAML configs live at <project_root>/agents/config/.
_CONFIG_DIR = Path(os.environ.get(
    "HEALTHCAREADK_AGENT_CONFIG_DIR",
    str(Path(__file__).parent.parent / "agents" / "config"),
))


def _get_conn() -> pyodbc.Connection:
    server = os.environ["HEALTHCAREADK_SQL_SERVER"]
    db = os.environ["HEALTHCAREADK_SQL_DB"]
    user = "agent_orchestrator"
    pwd = os.environ["HEALTHCAREADK_PWD_AGENT_ORCHESTRATOR"]
    return pyodbc.connect(
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={server};DATABASE={db};UID={user};PWD={pwd};"
    )


def _agent_yaml_name(agent_name: str) -> str:
    """Convert 'ClaimsAgent' → 'claims_agent', 'ETLAgent' → 'etl_agent'."""
    # Two-pass: handle acronym→CamelCase boundary (ETLAgent → ETL_Agent),
    # then lowercase→uppercase boundary (ClaimsAgent → Claims_Agent).
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", agent_name)
    s = re.sub(r"([a-z])([A-Z])", r"\1_\2", s)
    return s.lower()


def _load_budget(agent_name: str) -> int:
    yaml_path = _CONFIG_DIR / f"{_agent_yaml_name(agent_name)}.yaml"
    with open(yaml_path) as f:
        config = yaml.safe_load(f)
    return int(config.get("token_budget", 20000))


def record(
    agent_name: str,
    session_id: str,
    input_tokens: int,
    output_tokens: int,
    tool_calls: int,
    model: str | None = None,
    notes: str | None = None,
    cached_tokens: int = 0,
) -> None:
    """Insert one usage row for a completed agent call."""
    with _get_conn() as conn:
        conn.execute(
            """
            INSERT INTO dw.AgentUsageLog
                (AgentName, SessionID, InputTokens, OutputTokens, ToolCalls, ModelID, Notes, CachedTokens)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            agent_name,
            session_id,
            input_tokens,
            output_tokens,
            tool_calls,
            model,
            notes,
            cached_tokens,
        )
        conn.commit()


def remaining(agent_name: str, session_id: str) -> int:
    """Return tokens remaining for this agent within the current session."""
    budget = _load_budget(agent_name)
    with _get_conn() as conn:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(InputTokens + OutputTokens), 0)
            FROM   dw.AgentUsageLog
            WHERE  AgentName = ? AND SessionID = ?
            """,
            agent_name,
            session_id,
        ).fetchone()
    used = row[0] if row else 0
    return budget - used


def session_summary(session_id: str) -> dict:
    """Return per-agent totals for a session (used by tests and usage dashboard)."""
    with _get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
                AgentName,
                SUM(InputTokens)   AS TotalInput,
                SUM(OutputTokens)  AS TotalOutput,
                SUM(ToolCalls)     AS TotalToolCalls,
                COUNT(*)           AS Calls
            FROM   dw.AgentUsageLog
            WHERE  SessionID = ?
            GROUP  BY AgentName
            ORDER  BY AgentName
            """,
            session_id,
        ).fetchall()
    return {
        row[0]: {
            "input_tokens":  row[1],
            "output_tokens": row[2],
            "tool_calls":    row[3],
            "calls":         row[4],
        }
        for row in rows
    }
