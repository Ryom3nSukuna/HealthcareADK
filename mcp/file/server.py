"""
HealthcareADK — MCP File Server
Read/write text files within the project. Extension allowlist enforced.
All paths resolve under PROJECT_ROOT; path traversal is blocked.

Tools:
  read_file   — read a text file
  write_file  — write/overwrite a text file
  list_files  — list files in a directory, optionally filtered by extension
  append_file — append content to a text file
"""

import json
from datetime import datetime
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

ALLOWED_EXTENSIONS = {".sql", ".tmdl", ".csv", ".json", ".md", ".py"}

# This server is built for the TMDL/SQL editing workflow (Phase 5 design) — writes are
# restricted to those directories. Mirrors agents/tools/file_tools.py's _check_write;
# keep both in sync. Previously this allowlist only existed in the PreToolUse hook
# (scripts/hooks/guard_file_write.py), so any caller that skipped the Claude Code
# harness could write a .py file anywhere and then mcp-shell's run_python_script
# would execute it. The server must enforce this itself, not rely on the harness.
ALLOWED_WRITE_DIRS = ("powerbi/tmdl/", "sql/")

mcp = FastMCP("mcp-file")

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _safe_resolve(relative_path: str) -> Path:
    """Resolve relative_path under PROJECT_ROOT. Raises if traversal escapes root."""
    root = PROJECT_ROOT.resolve()
    resolved = (PROJECT_ROOT / relative_path).resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"Path traversal blocked: {relative_path!r}")
    return resolved


def _check_extension(path: Path) -> None:
    if path.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Extension {path.suffix!r} not allowed. Permitted: {sorted(ALLOWED_EXTENSIONS)}"
        )


def _check_write_dir(path: Path) -> None:
    rel = path.relative_to(PROJECT_ROOT.resolve()).as_posix()
    if not any(rel.startswith(d) for d in ALLOWED_WRITE_DIRS):
        raise ValueError(
            f"Write blocked: {rel!r} is outside the allowed directories {ALLOWED_WRITE_DIRS}"
        )


# ------------------------------------------------------------------
# Tool: read_file
# ------------------------------------------------------------------

@mcp.tool()
def read_file(path: str) -> str:
    """
    Read a text file. path is relative to the project root.
    Allowed extensions: .sql .tmdl .csv .json .md .py

    Returns: {"content": str} or {"error": str}
    """
    try:
        resolved = _safe_resolve(path)
        _check_extension(resolved)
        content = resolved.read_text(encoding="utf-8")
        return json.dumps({"content": content})
    except Exception as exc:
        return json.dumps({"error": str(exc)})


# ------------------------------------------------------------------
# Tool: write_file
# ------------------------------------------------------------------

@mcp.tool()
def write_file(path: str, content: str) -> str:
    """
    Write content to a file, creating parent directories as needed.
    path is relative to the project root.
    Allowed extensions: .sql .tmdl .csv .json .md .py

    Returns: {"written": int} (bytes written) or {"error": str}
    """
    try:
        resolved = _safe_resolve(path)
        _check_extension(resolved)
        _check_write_dir(resolved)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")
        return json.dumps({"written": len(content.encode("utf-8"))})
    except Exception as exc:
        return json.dumps({"error": str(exc)})


# ------------------------------------------------------------------
# Tool: list_files
# ------------------------------------------------------------------

@mcp.tool()
def list_files(directory: str = ".", extension: str = None) -> str:
    """
    List files recursively in a directory under the project root.
    directory : relative to project root (default: project root)
    extension : optional filter, e.g. ".sql" or ".tmdl"

    Returns: {"files": [{"path": str, "size": int, "modified": str}]} or {"error": str}
    """
    try:
        base = _safe_resolve(directory)
        if not base.is_dir():
            return json.dumps({"error": f"Not a directory: {directory!r}"})
        files = []
        for p in sorted(base.rglob("*")):
            if not p.is_file():
                continue
            if extension and p.suffix.lower() != extension.lower():
                continue
            stat = p.stat()
            files.append({
                "path": str(p.relative_to(PROJECT_ROOT)).replace("\\", "/"),
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })
        return json.dumps({"files": files})
    except Exception as exc:
        return json.dumps({"error": str(exc)})


# ------------------------------------------------------------------
# Tool: append_file
# ------------------------------------------------------------------

@mcp.tool()
def append_file(path: str, content: str) -> str:
    """
    Append content to a file. Creates the file if it does not exist.
    path is relative to the project root.
    Allowed extensions: .sql .tmdl .csv .json .md .py

    Returns: {"appended": int} (bytes appended) or {"error": str}
    """
    try:
        resolved = _safe_resolve(path)
        _check_extension(resolved)
        _check_write_dir(resolved)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        with resolved.open("a", encoding="utf-8") as f:
            f.write(content)
        return json.dumps({"appended": len(content.encode("utf-8"))})
    except Exception as exc:
        return json.dumps({"error": str(exc)})


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
