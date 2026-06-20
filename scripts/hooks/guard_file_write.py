import json
import sys

data = json.loads(sys.stdin.read())
path = data.get("tool_input", {}).get("path", "")
path_norm = path.replace("\\", "/").lower()

reasons = []

if ".." in path:
    reasons.append(f"Path traversal blocked: '{path}' contains '..'")

BLOCKED_NAMES = [".env", "credentials.json", "secrets.json", "id_rsa", "id_ed25519"]
if any(path_norm == b or path_norm.endswith("/" + b) for b in BLOCKED_NAMES):
    reasons.append(f"Write to credential file '{path}' blocked")

# mcp-file's write_file is built for the TMDL/SQL editing workflow (Phase 5 design) —
# restrict it to those directories, matching agents/tools/file_tools.py's _check_write.
ALLOWED_DIRS = ("powerbi/tmdl/", "sql/")
if not any(path_norm.startswith(d) for d in ALLOWED_DIRS):
    reasons.append(f"Write blocked: '{path}' is outside the allowed directories {ALLOWED_DIRS}")

if not reasons:
    sys.exit(0)

print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": "; ".join(reasons),
    }
}))
sys.exit(2)
