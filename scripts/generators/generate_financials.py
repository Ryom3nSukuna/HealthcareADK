import pandas as pd
import numpy as np
import uuid
from datetime import datetime, timedelta
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import LANDING, VOLUMES, SEED, RUN_DATE, DEPARTMENTS, GL_ACCOUNTS

np.random.seed(SEED + 7)


def generate_financials(facility_ids):
    n = VOLUMES["financials"]
    rng = np.random.default_rng(SEED + 7)
    base_date = datetime(2026, 5, 15)

    tx_types  = rng.choice(["Revenue", "Expense", "Reimbursement", "Write-off"], n, p=[0.40, 0.35, 0.15, 0.10])
    tx_days   = rng.integers(0, 365 * 5, n)
    tx_dates  = [(base_date - timedelta(days=int(d))).strftime("%Y-%m-%d") for d in tx_days]

    amounts = []
    gl_accs = []
    for tx in tx_types:
        if tx == "Revenue":
            amounts.append(round(float(rng.uniform(500, 250_000)), 2))
        elif tx == "Expense":
            amounts.append(round(float(rng.uniform(100, 100_000)), 2))
        elif tx == "Reimbursement":
            amounts.append(round(float(rng.uniform(200, 150_000)), 2))
        else:
            amounts.append(round(float(rng.uniform(50, 50_000)), 2))
        gl_accs.append(rng.choice(GL_ACCOUNTS[tx]))

    fiscal_years    = [int(datetime.strptime(d, "%Y-%m-%d").year) for d in tx_dates]
    fiscal_quarters = [((datetime.strptime(d, "%Y-%m-%d").month - 1) // 3) + 1 for d in tx_dates]

    df = pd.DataFrame({
        "transaction_id":      [str(uuid.uuid4()) for _ in range(n)],
        "transaction_date":    tx_dates,
        "transaction_type":    tx_types,
        "department":          rng.choice(DEPARTMENTS, n),
        "facility_id":         rng.choice(facility_ids, n),
        "amount":              amounts,
        "fiscal_year":         fiscal_years,
        "fiscal_quarter":      fiscal_quarters,
        "cost_center":         [f"CC-{rng.integers(100,999)}" for _ in range(n)],
        "gl_account":          gl_accs,
        "description":         [f"{tx} - {dept}" for tx, dept in zip(tx_types, rng.choice(DEPARTMENTS, n))],
        "created_at":          tx_dates,
    })

    out = LANDING / "financials" / f"financials_{RUN_DATE}.xlsx"
    df.to_excel(out, index=False, engine="openpyxl")
    print(f"[financials/xlsx]  {n:>6,} rows  ->  {out.name}")
    return df["transaction_id"].tolist()


if __name__ == "__main__":
    fac_df = pd.read_csv(LANDING / "facilities" / f"facilities_{RUN_DATE}.csv")
    generate_financials(fac_df["facility_id"].tolist())

