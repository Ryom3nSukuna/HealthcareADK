"""
Shell tool implementations for HealthcareADK domain agents (ETLAgent, ReportingAgent).

Paths are resolved relative to project subdirectories; traversal is blocked.
Server/DB for sqlcmd read from environment variables at call time.

run_sql_script authenticates as the calling agent's own SQL Server login
(db_login in agents/config/*.yaml) rather than the trusted (Windows) connection,
so it is bound by the same GRANT/DENY rules as sql_tools.py — see sql/10_agent_permissions.sql.
"""
import functools
import json
import os
import shutil
import subprocess
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_SSIS_DIR    = _PROJECT_ROOT / "ssis"
_SCRIPTS_DIR = _PROJECT_ROOT / "scripts"
_SQL_DIR     = _PROJECT_ROOT / "sql"
_TIMEOUT     = 300

_ENV = {**os.environ, "DOTNET_ROLL_FORWARD": "Major"}


def _safe_resolve(base_dir: Path, relative_path: str) -> Path:
    root = base_dir.resolve()
    resolved = (base_dir / relative_path).resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"Path traversal blocked: {relative_path!r}")
    return resolved


def _run(args: list, extra_env: dict | None = None) -> str:
    env = {**_ENV, **extra_env} if extra_env else _ENV
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_TIMEOUT,
            stdin=subprocess.DEVNULL,
            env=env,
        )
        return json.dumps({"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}, indent=2)
    except subprocess.TimeoutExpired:
        return json.dumps({"returncode": -1, "stdout": "", "stderr": f"Timed out after {_TIMEOUT}s"})
    except FileNotFoundError as exc:
        return json.dumps({"returncode": -1, "stdout": "", "stderr": f"Executable not found: {exc}"})


# ------------------------------------------------------------------
# Tool functions
# ------------------------------------------------------------------

def _run_ssis_package(db_login: str, package_path: str, config_path: str = None) -> str:
    try:
        pkg = _safe_resolve(_SSIS_DIR, package_path)
        args = ["dtexec", "/F", str(pkg)]
        if config_path:
            cfg = _safe_resolve(_SSIS_DIR, config_path)
            args += ["/ConfigFile", str(cfg)]
        return _run(args)
    except Exception as exc:
        return json.dumps({"returncode": -1, "stdout": "", "stderr": str(exc)})


def _run_python_script(db_login: str, script_name: str, args: list = None) -> str:
    try:
        script = _safe_resolve(_SCRIPTS_DIR, script_name)
        cmd = ["python", str(script)] + [str(a) for a in (args or [])]
        return _run(cmd)
    except Exception as exc:
        return json.dumps({"returncode": -1, "stdout": "", "stderr": str(exc)})


def _run_pbi_tools(db_login: str, subcommand: str, args: list = None) -> str:
    exe = shutil.which("pbi-tools.core")
    if not exe:
        return json.dumps({"returncode": -1, "stdout": "", "stderr": "pbi-tools.core not found on PATH."})
    try:
        cmd = [exe, subcommand] + [str(a) for a in (args or [])]
        return _run(cmd)
    except Exception as exc:
        return json.dumps({"returncode": -1, "stdout": "", "stderr": str(exc)})


def _run_sql_script(db_login: str, script_path: str) -> str:
    try:
        server = os.environ["HEALTHCAREADK_SQL_SERVER"]
        db = os.environ["HEALTHCAREADK_SQL_DB"]
        pwd = os.environ[f"HEALTHCAREADK_PWD_{db_login.upper()}"]
        script = _safe_resolve(_SQL_DIR, script_path)
        args = ["sqlcmd", "-S", server, "-d", db, "-U", db_login, "-i", str(script)]
        # Password passed via SQLCMDPASSWORD env var, not -P, so it never appears
        # in the process command line (visible to other users via tasklist/ps).
        return _run(args, extra_env={"SQLCMDPASSWORD": pwd})
    except Exception as exc:
        return json.dumps({"returncode": -1, "stdout": "", "stderr": str(exc)})


# ------------------------------------------------------------------
# Tool registry
# ------------------------------------------------------------------

TOOL_REGISTRY: dict[str, dict] = {
    "mcp__shell__run_ssis_package": {
        "definition": {
            "name": "run_ssis_package",
            "description": "Run an SSIS package via dtexec. package_path is relative to ssis/.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "package_path": {"type": "string", "description": "Relative path to .dtsx e.g. HealthcareADK_ETL/Package_Master.dtsx"},
                    "config_path":  {"type": "string", "description": "Optional .dtsConfig path relative to ssis/"},
                },
                "required": ["package_path"],
            },
        },
        "fn": _run_ssis_package,
    },
    "mcp__shell__run_python_script": {
        "definition": {
            "name": "run_python_script",
            "description": "Run a Python script from the scripts/ directory.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "script_name": {"type": "string", "description": "Filename relative to scripts/ e.g. generate_all.py"},
                    "args":        {"type": "array", "items": {"type": "string"}, "description": "Optional CLI arguments"},
                },
                "required": ["script_name"],
            },
        },
        "fn": _run_python_script,
    },
    "mcp__shell__run_pbi_tools": {
        "definition": {
            "name": "run_pbi_tools",
            "description": "Run a pbi-tools subcommand (deploy, extract, convert, info).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "subcommand": {"type": "string", "description": "e.g. deploy, extract, convert"},
                    "args":       {"type": "array", "items": {"type": "string"}, "description": "Optional flags and paths"},
                },
                "required": ["subcommand"],
            },
        },
        "fn": _run_pbi_tools,
    },
    "mcp__shell__run_sql_script": {
        "definition": {
            "name": "run_sql_script",
            "description": "Run a .sql file via sqlcmd. script_path is relative to sql/.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "script_path": {"type": "string", "description": "Relative path e.g. 08_etl_stg_to_dw.sql"},
                },
                "required": ["script_path"],
            },
        },
        "fn": _run_sql_script,
    },
}


def build_tools(allowed_mcp_names: list[str], db_login: str) -> list[dict]:
    """Return tool dicts for the given MCP tool names, bound to db_login (used by run_sql_script
    to authenticate as the calling agent's own SQL Server login)."""
    return [
        {"definition": TOOL_REGISTRY[name]["definition"], "fn": functools.partial(TOOL_REGISTRY[name]["fn"], db_login)}
        for name in allowed_mcp_names
        if name in TOOL_REGISTRY
    ]
