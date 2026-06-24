import json
import sys

data = json.loads(sys.stdin.read())
# Built-in Read tool uses "file_path"; mcp__file__read_file uses "path"
inp = data.get("tool_input", {})
path = inp.get("file_path") or inp.get("path", "")
path_norm = path.replace("\\", "/").lower()

BLOCKED_NAMES = [".env", "credentials.json", "secrets.json", "id_rsa", "id_ed25519"]
if any(path_norm == b or path_norm.endswith("/" + b) for b in BLOCKED_NAMES):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": f"Read of credential file '{path}' blocked",
        }
    }))
    sys.exit(2)

sys.exit(0)
