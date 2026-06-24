# mcp-sqlserver

MCP server providing read-only access to the HealthcareADK SQL Server data warehouse.

## Setup

```bash
pip install -r mcp/sqlserver/requirements.txt
```

### ODBC Driver
Requires **ODBC Driver 17 for SQL Server** (or 18).
- Download: https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server
- If you have Driver 18, update `CONNECTION_STRING` in `server.py` accordingly.

### SQL Server Instance
- **HealthcareADK database** → `.\SQLEXPRESS`  (configured in `server.py`)
- **Integration Services Catalog (SSISDB)** → `localhost` (separate instance — not used by this server)

### Windows Authentication
The server uses Windows Authentication (`Trusted_Connection=yes`).
Run Claude Code as the same Windows user that has access to the HealthcareADK database.

## Tools

| Tool | Description |
|---|---|
| `execute_query` | Run a SELECT query. Max 500 rows. |
| `get_claims_summary` | Filtered claims via `usp_GetClaimsSummary` |
| `get_financial_yoy` | YoY revenue/expense via `usp_GetFinancialYoY` |
| `get_provider_performance` | Provider KPIs via `usp_GetProviderPerformance` |
| `get_abnormal_labs` | Abnormal/critical labs via `usp_GetAbnormalLabResults` |
| `get_patient_timeline` | Full patient care timeline via `usp_GetPatientTimeline` |
| `get_schema` | Describe columns of a table or view |
| `list_tables` | List all objects in a schema |

## Test

```bash
python mcp/sqlserver/server.py
```

Server should start without errors. Claude Code will connect via stdio.
