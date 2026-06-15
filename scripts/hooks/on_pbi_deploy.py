import json
import sys

data = json.loads(sys.stdin.read())
response = data.get("tool_response", {})
returncode = response.get("returncode", 0)
stdout = response.get("stdout", "").strip()
stderr = response.get("stderr", "").strip()

status = "succeeded" if returncode == 0 else f"failed (exit {returncode})"

lines = stdout.splitlines()
summary = "\n".join(lines[-20:]) if len(lines) > 20 else stdout
if stderr:
    summary += f"\nstderr: {stderr[:500]}"

print(f"[on_pbi_deploy] pbi-tools {status}\n{summary}")
