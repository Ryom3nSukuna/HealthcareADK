"""
Create SQL Server logins for Phase 6 agent accounts.

Passwords are read from environment variables and passed in-memory to pyodbc.
They never appear in any source file or on disk.

Prerequisites:
  - SQL Server instance accessible via HEALTHCAREADK_SQL_SERVER
  - Current Windows account must have sysadmin or securityadmin role on the instance

Required env vars:
  HEALTHCAREADK_SQL_SERVER               e.g. .\\SQLEXPRESS
  HEALTHCAREADK_PWD_AGENT_ORCHESTRATOR
  HEALTHCAREADK_PWD_AGENT_CLAIMS
  HEALTHCAREADK_PWD_AGENT_CLINICAL
  HEALTHCAREADK_PWD_AGENT_FINANCIAL
  HEALTHCAREADK_PWD_AGENT_REPORTING
  HEALTHCAREADK_PWD_AGENT_ETL
  HEALTHCAREADK_PWD_AGENT_PROVIDER

Usage:
  python scripts/deploy_agent_logins.py

After this script succeeds, run sql/10_agent_permissions.sql in SSMS to create
database users and apply schema-level GRANTs.
"""

import os
import sys

import pyodbc
from dotenv import load_dotenv

load_dotenv()


LOGINS = [
    ("agent_orchestrator", "HEALTHCAREADK_PWD_AGENT_ORCHESTRATOR"),
    ("agent_claims",       "HEALTHCAREADK_PWD_AGENT_CLAIMS"),
    ("agent_clinical",     "HEALTHCAREADK_PWD_AGENT_CLINICAL"),
    ("agent_financial",    "HEALTHCAREADK_PWD_AGENT_FINANCIAL"),
    ("agent_reporting",    "HEALTHCAREADK_PWD_AGENT_REPORTING"),
    ("agent_etl",          "HEALTHCAREADK_PWD_AGENT_ETL"),
    ("agent_provider",     "HEALTHCAREADK_PWD_AGENT_PROVIDER"),
]


def _check_env():
    missing = [env for _, env in LOGINS if not os.environ.get(env)]
    if missing:
        print("ERROR: Missing required environment variables:")
        for m in missing:
            print(f"  {m}")
        sys.exit(1)


def _master_conn() -> pyodbc.Connection:
    server = os.environ["HEALTHCAREADK_SQL_SERVER"]
    return pyodbc.connect(
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={server};DATABASE=master;Trusted_Connection=yes;"
    )


def main():
    _check_env()

    conn = _master_conn()
    conn.autocommit = True
    cur = conn.cursor()

    for login, env_key in LOGINS:
        pwd = os.environ[env_key]
        exists = cur.execute(
            "SELECT 1 FROM sys.server_principals WHERE name = ?", login
        ).fetchone()

        safe_pwd = pwd.replace("'", "''")
        if exists:
            # Reset password so .env values are always in sync with SQL Server.
            cur.execute(f"ALTER LOGIN [{login}] WITH PASSWORD = N'{safe_pwd}'")
            print(f"  RESET {login}")
        else:
            # Password lives in Python memory only — never written to any file.
            # Single-quote escaping is the only required sanitization for the
            # CREATE LOGIN statement; login name is validated against the known
            # allowlist above so no injection risk on that side.
            cur.execute(f"CREATE LOGIN [{login}] WITH PASSWORD = N'{safe_pwd}'")
            print(f"  OK    {login}")

    cur.close()
    conn.close()
    print("\nAll logins processed.")
    print("Next: run sql/10_agent_permissions.sql in SSMS to create users and apply GRANTs.")


if __name__ == "__main__":
    main()
