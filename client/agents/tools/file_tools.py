"""
File I/O tool implementations for HealthcareADK domain agents (ReportingAgent).

Scoped to project root. Only permitted extensions may be read or written.
Write guard replicates scripts/hooks/guard_file_write.py logic.
"""
import json
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_ALLOWED_EXTENSIONS = {".sql", ".tmdl", ".csv", ".json", ".md", ".py"}
_BLOCKED_NAMES = {"credentials.json", "secrets.json", ".env", "id_rsa", "id_ed25519", ".mcp.json"}
# ReportingAgent's system prompt claims write access is limited to these directories
# (powerbi/tmdl/ for the data model, sql/ for SP reference) — enforce it in code too,
# since the prompt alone doesn't stop a write_file call (e.g. via prompt injection).
_ALLOWED_WRITE_DIRS = ("powerbi/tmdl/", "sql/")


def _safe_path(relative_path: str) -> Path:
    resolved = (_PROJECT_ROOT / relative_path).resolve()
    if resolved != _PROJECT_ROOT and _PROJECT_ROOT not in resolved.parents:
        raise ValueError(f"Path traversal blocked: {relative_path!r}")
    return resolved


def _check_write(path: Path) -> str | None:
    if ".." in str(path):
        return "Path traversal blocked."
    if path.name.lower() in _BLOCKED_NAMES:
        return f"Writing credential file blocked: {path.name}"
    if path.suffix.lower() not in _ALLOWED_EXTENSIONS:
        return f"Extension not permitted: {path.suffix}. Allowed: {sorted(_ALLOWED_EXTENSIONS)}"
    rel = path.relative_to(_PROJECT_ROOT).as_posix()
    if not any(rel.startswith(d) for d in _ALLOWED_WRITE_DIRS):
        return f"Write blocked: '{rel}' is outside the allowed directories {_ALLOWED_WRITE_DIRS}"
    return None


# ------------------------------------------------------------------
# Tool functions
# ------------------------------------------------------------------

def _read_file(path: str) -> str:
    try:
        resolved = _safe_path(path)
        if not resolved.exists():
            return json.dumps({"error": f"File not found: {path}"})
        content = resolved.read_text(encoding="utf-8")
        return json.dumps({"content": content})
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def _write_file(path: str, content: str) -> str:
    try:
        resolved = _safe_path(path)
        guard = _check_write(resolved)
        if guard:
            return json.dumps({"error": guard})
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")
        return json.dumps({"written": len(content.encode("utf-8"))})
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def _list_files(directory: str = ".", extension: str = None) -> str:
    try:
        resolved = _safe_path(directory)
        if not resolved.is_dir():
            return json.dumps({"error": f"Not a directory: {directory}"})
        pattern = f"**/*{extension}" if extension else "**/*"
        files = [
            {
                "path": str(f.relative_to(_PROJECT_ROOT)),
                "size": f.stat().st_size,
                "modified": f.stat().st_mtime,
            }
            for f in resolved.glob(pattern)
            if f.is_file()
        ]
        return json.dumps({"files": files})
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def _append_file(path: str, content: str) -> str:
    try:
        resolved = _safe_path(path)
        guard = _check_write(resolved)
        if guard:
            return json.dumps({"error": guard})
        resolved.parent.mkdir(parents=True, exist_ok=True)
        with resolved.open("a", encoding="utf-8") as f:
            f.write(content)
        return json.dumps({"appended": len(content.encode("utf-8"))})
    except Exception as exc:
        return json.dumps({"error": str(exc)})


# ------------------------------------------------------------------
# Tool registry
# ------------------------------------------------------------------

TOOL_REGISTRY: dict[str, dict] = {
    "mcp__file__read_file": {
        "definition": {
            "name": "read_file",
            "description": "Read a text file from the project. Path is relative to the project root.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path e.g. powerbi/tmdl/tables/_Measures.tmdl"},
                },
                "required": ["path"],
            },
        },
        "fn": _read_file,
    },
    "mcp__file__write_file": {
        "definition": {
            "name": "write_file",
            "description": "Write or overwrite a file in the project. Creates parent dirs as needed. Blocked on credential files and path traversal.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path":    {"type": "string", "description": "Relative path e.g. powerbi/tmdl/tables/_Measures.tmdl"},
                    "content": {"type": "string", "description": "Full file content to write"},
                },
                "required": ["path", "content"],
            },
        },
        "fn": _write_file,
    },
    "mcp__file__list_files": {
        "definition": {
            "name": "list_files",
            "description": "List files in a project directory, recursively.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "Relative path to directory (default: project root)"},
                    "extension": {"type": "string", "description": "Filter by extension e.g. .tmdl"},
                },
            },
        },
        "fn": _list_files,
    },
    "mcp__file__append_file": {
        "definition": {
            "name": "append_file",
            "description": "Append content to a file. Creates the file if it does not exist.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path":    {"type": "string", "description": "Relative path"},
                    "content": {"type": "string", "description": "Content to append"},
                },
                "required": ["path", "content"],
            },
        },
        "fn": _append_file,
    },
}


def build_tools(allowed_mcp_names: list[str]) -> list[dict]:
    return [
        {"mcp_name": name, **TOOL_REGISTRY[name]}
        for name in allowed_mcp_names
        if name in TOOL_REGISTRY
    ]
