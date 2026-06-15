import json
import re
import sys

data = json.loads(sys.stdin.read())
sql = data.get("tool_input", {}).get("sql", "")

# Strip comments, normalize to uppercase for pattern matching
sql_up = re.sub(r"--[^\n]*", "", sql)
sql_up = re.sub(r"/\*.*?\*/", "", sql_up, flags=re.DOTALL)
sql_up = sql_up.upper().strip()

reasons = []

# Block direct DML/DDL against dw.* — ETL must go through stg.*
if re.search(
    r"\b(INSERT\s+INTO|UPDATE|DELETE\s+FROM|DROP\s+TABLE|ALTER\s+TABLE|TRUNCATE\s+TABLE)\s+DW\.",
    sql_up,
):
    reasons.append(
        "Direct write to dw.* blocked — ETL must go through the staging layer (stg.*)"
    )

# Block DELETE without WHERE on any table
if re.search(r"\bDELETE\b", sql_up) and not re.search(r"\bWHERE\b", sql_up):
    reasons.append("DELETE without WHERE blocked — would affect all rows")

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
