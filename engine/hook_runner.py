"""
Replays Claude Code's hook contract at agent runtime.

The domain agents don't run inside Claude Code, so the PreToolUse / PostToolUse
hooks in .claude/settings.json never fire for them. This module reads that same
settings file and runs the same hook commands the same way the CLI does, so the
guard scripts are honored on every tool call regardless of who drives the loop.

Contract mirrored from Claude Code:
  - stdin: JSON with hook_event_name, tool_name, tool_input (+ tool_response on Post)
  - PreToolUse: exit 0 -> allow. exit 2 OR stdout permissionDecision="deny" -> block.
  - The command string is run through a shell with cwd at the repo root, so the
    relative paths in settings.json ("python client/scripts/hooks/...") resolve.
"""
import json
import re
import subprocess
from functools import lru_cache
from pathlib import Path

# repo root = parent of engine/, which is where .claude/settings.json lives
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SETTINGS_PATH = _REPO_ROOT / ".claude" / "settings.json"

# Pre is fail-closed (a guard that didn't run must not wave the call through).
# Post is fail-open (the tool already ran; blocking its result undoes nothing).
_FAIL_CLOSED = {"PreToolUse": True, "PostToolUse": False}


class HookDenied(Exception):
    """Raised when a PreToolUse hook blocks a tool call."""
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@lru_cache(maxsize=1)
def _load_settings() -> dict:
    if not _SETTINGS_PATH.exists():
        return {}
    return json.loads(_SETTINGS_PATH.read_text(encoding="utf-8"))


def _matching_hooks(event: str, tool_name: str) -> list[dict]:
    """All hook commands whose matcher matches tool_name, in settings order."""
    out: list[dict] = []
    for entry in _load_settings().get("hooks", {}).get(event, []):
        matcher = entry.get("matcher", "")
        # Matchers are regexes against the MCP-qualified tool name.
        # Native-tool matchers like "Read" never match mcp__* names at runtime.
        if matcher and re.search(matcher, tool_name):
            out.extend(entry.get("hooks", []))
    return out


def _run_one(hook: dict, payload: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        hook["command"],
        shell=True,
        cwd=_REPO_ROOT,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=hook.get("timeout", 30),
    )


def _deny_reason(proc: subprocess.CompletedProcess) -> str | None:
    """Return a deny reason if this result blocks the call, else None."""
    if proc.returncode == 2:
        try:
            out = json.loads(proc.stdout or "{}")
            reason = out.get("hookSpecificOutput", {}).get("permissionDecisionReason")
            if reason:
                return reason
        except json.JSONDecodeError:
            pass
        return (proc.stderr or proc.stdout or "blocked by hook").strip()
    # exit 0 with an explicit deny decision also blocks (Claude Code honors this too)
    try:
        out = json.loads(proc.stdout or "{}")
        hso = out.get("hookSpecificOutput", {})
        if hso.get("permissionDecision") == "deny":
            return hso.get("permissionDecisionReason", "blocked by hook")
    except json.JSONDecodeError:
        pass
    return None


def run_pre_tool_use(tool_name: str, tool_input: dict) -> None:
    """Raise HookDenied if any matching PreToolUse hook blocks the call."""
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": tool_name,
        "tool_input": tool_input,
    }
    for hook in _matching_hooks("PreToolUse", tool_name):
        try:
            proc = _run_one(hook, payload)
        except Exception as exc:
            if _FAIL_CLOSED["PreToolUse"]:
                raise HookDenied(f"hook '{hook.get('command')}' failed to run: {exc}")
            continue
        reason = _deny_reason(proc)
        if reason:
            raise HookDenied(reason)


def run_post_tool_use(tool_name: str, tool_input: dict, tool_response: str) -> None:
    """Fire matching PostToolUse hooks. Side-effect / observability only;
    failures are swallowed (the tool already executed)."""
    payload = {
        "hook_event_name": "PostToolUse",
        "tool_name": tool_name,
        "tool_input": tool_input,
        "tool_response": tool_response,
    }
    for hook in _matching_hooks("PostToolUse", tool_name):
        try:
            _run_one(hook, payload)
        except Exception:
            if _FAIL_CLOSED["PostToolUse"]:
                raise
            continue
