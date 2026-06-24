import json
import os
import subprocess
import sys

from dotenv import load_dotenv

load_dotenv()

data = json.loads(sys.stdin.read())
script_name = data.get("tool_input", {}).get("script_name", "")

if script_name != "generate_all.py":
    sys.exit(0)

result = subprocess.run(
    ["sqlcmd", "-S", os.environ["HEALTHCAREADK_SQL_SERVER"], "-d", os.environ["HEALTHCAREADK_SQL_DB"], "-Q", "EXEC dw.usp_ETL_RunAll"],
    capture_output=True,
    text=True,
    timeout=300,
)

output = (result.stdout + result.stderr).strip()
print(f"[on_data_drop] ETL triggered after generate_all.py\n{output}")

if result.returncode != 0:
    sys.exit(1)
