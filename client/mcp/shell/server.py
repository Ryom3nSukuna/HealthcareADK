"""
HealthcareADK — MCP Shell Server
Executes allowlisted shell commands on behalf of agents.
All path arguments are resolved under their designated project directories;
path traversal is blocked.

Tools:
  run_ssis_package   — run a .dtsx package via dtexec (resolves under ssis/)
  run_python_script  — run a script via python (resolves under scripts/)
  run_pbi_tools      — run a pbi-tools subcommand
  run_sql_script     — run a .sql file via sqlcmd against HealthcareADK (resolves under sql/)
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

SSIS_DIR    = PROJECT_ROOT / "ssis"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
SQL_DIR     = PROJECT_ROOT / "sql"

TIMEOUT = 300  # seconds — SSIS packages can be slow

mcp = FastMCP("mcp-shell")

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _safe_resolve(base_dir: Path, relative_path: str) -> Path:
    """Resolve relative_path under base_dir. Raises if traversal escapes base."""
    base = base_dir.resolve()
    resolved = (base_dir / relative_path).resolve()
    if resolved != base and base not in resolved.parents:
        raise ValueError(f"Path traversal blocked: {relative_path!r}")
    return resolved


_ENV = {**os.environ, "DOTNET_ROLL_FORWARD": "Major"}


def _run(args: list) -> str:
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            stdin=subprocess.DEVNULL,
            env=_ENV,
        )
        return json.dumps(
            {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            },
            indent=2,
        )
    except subprocess.TimeoutExpired:
        return json.dumps({"returncode": -1, "stdout": "", "stderr": f"Timed out after {TIMEOUT}s"})
    except FileNotFoundError as exc:
        return json.dumps({"returncode": -1, "stdout": "", "stderr": f"Executable not found: {exc}"})


# ------------------------------------------------------------------
# Tool: run_ssis_package
# ------------------------------------------------------------------

@mcp.tool()
def run_ssis_package(package_path: str, config_path: str = None) -> str:
    """
    Run an SSIS package via dtexec.
    package_path is relative to the ssis/ directory.

    Parameters:
      package_path : relative path to .dtsx file, e.g. "HealthcareADK_ETL/Package_Master.dtsx"
      config_path  : optional .dtsConfig file, also relative to ssis/

    Returns: {"returncode": int, "stdout": str, "stderr": str}
    """
    try:
        pkg = _safe_resolve(SSIS_DIR, package_path)
        args = ["dtexec", "/F", str(pkg)]
        if config_path:
            cfg = _safe_resolve(SSIS_DIR, config_path)
            args += ["/ConfigFile", str(cfg)]
        return _run(args)
    except Exception as exc:
        return json.dumps({"returncode": -1, "stdout": "", "stderr": str(exc)})


# ------------------------------------------------------------------
# Tool: run_python_script
# ------------------------------------------------------------------

@mcp.tool()
def run_python_script(script_name: str, args: list = None) -> str:
    """
    Run a Python script from the scripts/ directory.

    Parameters:
      script_name : filename relative to scripts/, e.g. "generate_all.py"
      args        : optional list of string arguments, e.g. ["--domain", "claims"]

    Returns: {"returncode": int, "stdout": str, "stderr": str}
    """
    try:
        script = _safe_resolve(SCRIPTS_DIR, script_name)
        cmd = ["python", str(script)] + [str(a) for a in (args or [])]
        return _run(cmd)
    except Exception as exc:
        return json.dumps({"returncode": -1, "stdout": "", "stderr": str(exc)})


# ------------------------------------------------------------------
# Tool: run_pbi_tools
# ------------------------------------------------------------------

@mcp.tool()
def run_pbi_tools(subcommand: str, args: list = None) -> str:
    """
    Run a pbi-tools subcommand.
    Common subcommands: deploy, extract, info, compile-pbix

    Parameters:
      subcommand : pbi-tools subcommand, e.g. "deploy"
      args       : optional list of flags/values, e.g. ["powerbi/tmdl", "-workspace", "MyWorkspace"]

    Returns: {"returncode": int, "stdout": str, "stderr": str}
    """
    try:
        exe = shutil.which("pbi-tools.core")
        if not exe:
            return json.dumps({"returncode": -1, "stdout": "", "stderr": "pbi-tools.core not found on PATH. Install from https://pbi.tools and add to PATH."})
        cmd = [exe, subcommand] + [str(a) for a in (args or [])]
        return _run(cmd)
    except Exception as exc:
        return json.dumps({"returncode": -1, "stdout": "", "stderr": str(exc)})


# ------------------------------------------------------------------
# Tool: run_sql_script
# ------------------------------------------------------------------

@mcp.tool()
def run_sql_script(script_path: str) -> str:
    """
    Run a .sql file via sqlcmd. script_path is relative to the sql/ directory.

    Parameters:
      script_path : relative path to .sql file, e.g. "08_etl_stg_to_dw.sql"

    Returns: {"returncode": int, "stdout": str, "stderr": str}
    """
    try:
        script = _safe_resolve(SQL_DIR, script_path)
        args = [
            "sqlcmd",
            "-S", os.environ["HEALTHCAREADK_SQL_SERVER"],
            "-d", os.environ["HEALTHCAREADK_SQL_DB"],
            "-E",
            "-i", str(script),
        ]
        return _run(args)
    except Exception as exc:
        return json.dumps({"returncode": -1, "stdout": "", "stderr": str(exc)})


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
