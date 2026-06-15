# mcp-powerbi

MCP server that interacts with the Power BI REST API on behalf of HealthcareADK agents.
Targets **My Workspace** via delegated auth (MSAL device code flow).

## Setup

### 1. Install dependencies

```bash
pip install -r mcp/powerbi/requirements.txt
```

### 2. Set environment variables

Set these as Windows user environment variables (not in any file):

```
AZURE_CLIENT_ID=<your app registration client id>
AZURE_TENANT_ID=<your azure ad tenant id>
```

### 3. Authenticate once

Run the auth script once to cache your token:

```bash
python mcp/powerbi/auth.py
```

Follow the device code prompt — open the URL in a browser and sign in with your Microsoft account.
You consent to the Power BI permissions on first login. No admin approval required.
Token is cached to `~/.pbi_token_cache.json` and refreshed automatically.

### 4. Publish your .pbix

The REST API operates on cloud datasets. Publish your `.pbix` from Power BI Desktop:
**File → Publish → Publish to Power BI**

Then use `list_datasets` to find your dataset ID.

## Tools

| Tool | Signature | Purpose |
| --- | --- | --- |
| `list_datasets` | `()` | List all datasets in My Workspace — use to discover dataset IDs |
| `refresh_dataset` | `(dataset_id)` | Trigger a dataset refresh |
| `get_refresh_status` | `(dataset_id, top=5)` | Get recent refresh history |
| `update_parameters` | `(dataset_id, parameters)` | Update dataset parameters |

## Examples

```
list_datasets()
refresh_dataset("a1b2c3d4-...")
get_refresh_status("a1b2c3d4-...", top=3)
update_parameters("a1b2c3d4-...", {"ServerName": ".\\SQLEXPRESS", "DatabaseName": "HealthcareADK"})
```
