"""
One-time Power BI authentication script.
Run this once to cache your credentials — the MCP server uses the cache silently.

Usage:
    python mcp/powerbi/auth.py
"""

import os
from pathlib import Path

import msal

CLIENT_ID = os.environ.get("AZURE_CLIENT_ID")
TENANT_ID = os.environ.get("AZURE_TENANT_ID")

if not CLIENT_ID or not TENANT_ID:
    raise SystemExit("AZURE_CLIENT_ID and AZURE_TENANT_ID must be set as environment variables.")

AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPES = ["https://analysis.windows.net/powerbi/api/.default"]
TOKEN_CACHE_PATH = Path.home() / ".pbi_token_cache.json"

cache = msal.SerializableTokenCache()
if TOKEN_CACHE_PATH.exists():
    cache.deserialize(TOKEN_CACHE_PATH.read_text(encoding="utf-8"))

app = msal.PublicClientApplication(CLIENT_ID, authority=AUTHORITY, token_cache=cache)

# Try silent first in case a valid token already exists
accounts = app.get_accounts()
if accounts:
    result = app.acquire_token_silent(SCOPES, account=accounts[0])
    if result and "access_token" in result:
        print(f"Already authenticated as {accounts[0]['username']}. Token is valid.")
        raise SystemExit(0)

# Device code flow
flow = app.initiate_device_flow(scopes=SCOPES)
if "user_code" not in flow:
    raise SystemExit(f"Failed to initiate device flow: {flow}")

print(flow["message"])
print()

result = app.acquire_token_by_device_flow(flow)

if "access_token" in result:
    if cache.has_state_changed:
        TOKEN_CACHE_PATH.write_text(cache.serialize(), encoding="utf-8")
    account = app.get_accounts()[0]
    print(f"Authenticated as {account['username']}.")
    print(f"Token cached to {TOKEN_CACHE_PATH}")
else:
    raise SystemExit(f"Authentication failed: {result.get('error_description', result)}")
