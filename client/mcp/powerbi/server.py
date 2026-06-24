"""
HealthcareADK — MCP Power BI Server
Interacts with Power BI REST API for My Workspace via delegated auth.

Auth: reads AZURE_CLIENT_ID and AZURE_TENANT_ID from environment.
      Token is cached to ~/.pbi_token_cache.json after one-time login.
      Run mcp/powerbi/auth.py once to populate the cache.

Tools:
  list_datasets       — list datasets in My Workspace (use to discover dataset IDs)
  refresh_dataset     — trigger a dataset refresh
  get_refresh_status  — get recent refresh history for a dataset
  update_parameters   — update dataset parameters
"""

import json
import os
from pathlib import Path

import msal
import requests
from mcp.server.fastmcp import FastMCP

# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------

CLIENT_ID = os.environ.get("AZURE_CLIENT_ID")
TENANT_ID = os.environ.get("AZURE_TENANT_ID")
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPES = ["https://analysis.windows.net/powerbi/api/.default"]
TOKEN_CACHE_PATH = Path.home() / ".pbi_token_cache.json"
PBI_BASE = "https://api.powerbi.com/v1.0/myorg"

mcp = FastMCP("mcp-powerbi")

# ------------------------------------------------------------------
# Auth helpers
# ------------------------------------------------------------------

def _load_cache() -> msal.SerializableTokenCache:
    cache = msal.SerializableTokenCache()
    if TOKEN_CACHE_PATH.exists():
        cache.deserialize(TOKEN_CACHE_PATH.read_text(encoding="utf-8"))
    return cache


def _save_cache(cache: msal.SerializableTokenCache) -> None:
    if cache.has_state_changed:
        TOKEN_CACHE_PATH.write_text(cache.serialize(), encoding="utf-8")


def _get_token() -> str:
    if not CLIENT_ID or not TENANT_ID:
        raise EnvironmentError(
            "AZURE_CLIENT_ID and AZURE_TENANT_ID must be set as environment variables."
        )
    cache = _load_cache()
    app = msal.PublicClientApplication(CLIENT_ID, authority=AUTHORITY, token_cache=cache)

    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])
        if result and "access_token" in result:
            _save_cache(cache)
            return result["access_token"]

    raise RuntimeError(
        "No cached token found. Run 'python mcp/powerbi/auth.py' to authenticate, then retry."
    )


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {_get_token()}",
        "Content-Type": "application/json",
    }


def _api(method: str, path: str, **kwargs):
    url = f"{PBI_BASE}{path}"
    resp = requests.request(method, url, headers=_headers(), **kwargs)
    if resp.status_code in (200, 201):
        return resp.json()
    if resp.status_code == 202:
        return {"status": "accepted", "message": "Refresh triggered successfully."}
    return {"error": f"HTTP {resp.status_code}", "detail": resp.text}


# ------------------------------------------------------------------
# Tool: list_datasets
# ------------------------------------------------------------------

@mcp.tool()
def list_datasets() -> str:
    """
    List all datasets in My Workspace.
    Use the returned dataset ID with the other tools.

    Returns: {"datasets": [{"id": str, "name": str, "isRefreshable": bool}]}
    """
    try:
        result = _api("GET", "/datasets")
        datasets = [
            {
                "id": d["id"],
                "name": d["name"],
                "isRefreshable": d.get("isRefreshable"),
            }
            for d in result.get("value", [])
        ]
        return json.dumps({"datasets": datasets}, indent=2)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


# ------------------------------------------------------------------
# Tool: refresh_dataset
# ------------------------------------------------------------------

@mcp.tool()
def refresh_dataset(dataset_id: str) -> str:
    """
    Trigger a refresh for a Power BI dataset in My Workspace.
    dataset_id: GUID — get it from list_datasets().

    Returns: {"status": "accepted"} on success or {"error": str}
    """
    try:
        result = _api("POST", f"/datasets/{dataset_id}/refreshes", json={})
        return json.dumps(result, indent=2)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


# ------------------------------------------------------------------
# Tool: get_refresh_status
# ------------------------------------------------------------------

@mcp.tool()
def get_refresh_status(dataset_id: str, top: int = 5) -> str:
    """
    Get recent refresh history for a dataset.
    dataset_id: GUID — get it from list_datasets().
    top: number of recent refreshes to return (default 5).

    Returns: {"value": [...]} with status, startTime, endTime, refreshType per entry
    """
    try:
        result = _api("GET", f"/datasets/{dataset_id}/refreshes?$top={top}")
        return json.dumps(result, indent=2)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


# ------------------------------------------------------------------
# Tool: update_parameters
# ------------------------------------------------------------------

@mcp.tool()
def update_parameters(dataset_id: str, parameters: dict) -> str:
    """
    Update dataset parameters in My Workspace.
    dataset_id : GUID — get it from list_datasets().
    parameters : dict of {name: newValue},
                 e.g. {"ServerName": ".\\\\SQLEXPRESS", "DatabaseName": "HealthcareADK"}

    Returns: {"status": "accepted"} on success or {"error": str}
    """
    try:
        body = {
            "updateDetails": [
                {"name": k, "newValue": v}
                for k, v in parameters.items()
            ]
        }
        result = _api("POST", f"/datasets/{dataset_id}/Default.UpdateParameters", json=body)
        return json.dumps(result, indent=2)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
