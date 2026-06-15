import json
import os
import subprocess
import sys

from dotenv import load_dotenv

load_dotenv()

data = json.loads(sys.stdin.read())
response = data.get("tool_response", {})
returncode = response.get("returncode", 0)

result = subprocess.run(
    [
        "sqlcmd", "-S", os.environ["HEALTHCAREADK_SQL_SERVER"], "-d", os.environ["HEALTHCAREADK_SQL_DB"], "-Q",
        "SELECT TOP 10 Entity, RowsInserted, RowsUpdated, RowsSkipped, Status, ErrorMessage "
        "FROM dw.ETLLog ORDER BY LogID DESC",
    ],
    capture_output=True,
    text=True,
    timeout=30,
)

status = "FAILED" if returncode != 0 else "completed"
output = (result.stdout + result.stderr).strip()
print(f"[on_ssis_complete] SSIS package {status}\n{output}")
