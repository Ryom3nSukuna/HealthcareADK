# mcp-shell

MCP server that executes allowlisted shell commands on behalf of HealthcareADK agents.

## Security model

Only four executables are permitted: `dtexec`, `python`, `pbi-tools`, `sqlcmd`.
All path arguments are resolved under their designated project directories — path traversal (`..`) is blocked.

## Setup

```bash
pip install -r mcp/shell/requirements.txt
```

The following tools must be on PATH:
- `dtexec` — SQL Server Integration Services (installed with SSDT or SSIS runtime)
- `python` — Python 3.x
- `pbi-tools.core` — [pbi-tools CLI](https://pbi.tools) v1.2.0, installed at `C:\Tools\pbi-tools\`. Requires .NET 8+; run with `DOTNET_ROLL_FORWARD=Major` to use the installed .NET 10 runtime (handled automatically by the server).
- `sqlcmd` — SQL Server command-line tool

## Tools

| Tool | Signature | Purpose |
| --- | --- | --- |
| `run_ssis_package` | `(package_path, config_path=None)` | Run a `.dtsx` via `dtexec`; path relative to `ssis/` |
| `run_python_script` | `(script_name, args=[])` | Run a script via `python`; path relative to `scripts/` |
| `run_pbi_tools` | `(subcommand, args=[])` | Run `pbi-tools <subcommand>` |
| `run_sql_script` | `(script_path)` | Run a `.sql` file via `sqlcmd`; path relative to `sql/` |

All tools return:
```json
{"returncode": 0, "stdout": "...", "stderr": "..."}
```

## Examples

```
run_ssis_package("HealthcareADK_ETL/Package_Master.dtsx")
run_python_script("generate_all.py", ["--domain", "claims"])
run_pbi_tools("deploy", ["powerbi/tmdl"])
run_sql_script("08_etl_stg_to_dw.sql")
```
