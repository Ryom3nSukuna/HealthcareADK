import pandas as pd
import numpy as np
import uuid
from datetime import datetime, timedelta
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import LANDING, VOLUMES, SEED, RUN_DATE, ICD10_CODES, CPT_CODES

np.random.seed(SEED + 4)

DENIAL_REASONS = [
    "Service not covered", "Prior authorization required",
    "Duplicate claim", "Patient not eligible on service date",
    "Exceeds benefit limit", "Invalid diagnosis code",
]


def generate_claims(patient_ids, provider_ids, facility_ids, payer_ids):
    n = VOLUMES["claims"]
    rng = np.random.default_rng(SEED + 4)
    base_date = datetime(2026, 5, 15)

    icd_codes  = [c[0] for c in ICD10_CODES]
    cpt_codes  = [c[0] for c in CPT_CODES]
    cpt_prices = {c[0]: c[2] for c in CPT_CODES}

    proc_codes   = rng.choice(cpt_codes, n)
    billed       = np.array([cpt_prices[c] * rng.uniform(0.9, 1.5) for c in proc_codes])
    allowed_pct  = rng.uniform(0.55, 0.85, n)
    paid_pct     = rng.uniform(0.80, 1.00, n)
    allowed      = billed * allowed_pct
    statuses     = rng.choice(["Approved", "Denied", "Pending", "Appealed"], n, p=[0.70, 0.15, 0.10, 0.05])
    paid         = np.where(statuses == "Approved", allowed * paid_pct, 0.0)

    service_days = rng.integers(0, 365 * 3, n)
    service_dates = [(base_date - timedelta(days=int(d))).strftime("%Y-%m-%d") for d in service_days]
    claim_dates   = [(datetime.strptime(sd, "%Y-%m-%d") + timedelta(days=int(rng.integers(1, 10)))).strftime("%Y-%m-%d") for sd in service_dates]

    df = pd.DataFrame({
        "claim_id":          [str(uuid.uuid4()) for _ in range(n)],
        "patient_id":        rng.choice(patient_ids, n),
        "provider_id":       rng.choice(provider_ids, n),
        "facility_id":       rng.choice(facility_ids, n),
        "payer_id":          rng.choice(payer_ids, n),
        "claim_date":        claim_dates,
        "service_date":      service_dates,
        "icd10_primary":     rng.choice(icd_codes, n),
        "icd10_secondary":   rng.choice(icd_codes + [""], n),
        "procedure_code":    proc_codes,
        "billed_amount":     billed.round(2),
        "allowed_amount":    allowed.round(2),
        "paid_amount":       paid.round(2),
        "claim_status":      statuses,
        "denial_reason":     [rng.choice(DENIAL_REASONS) if s == "Denied" else "" for s in statuses],
        "created_at":        [(datetime.strptime(cd, "%Y-%m-%d")).strftime("%Y-%m-%d %H:%M:%S") for cd in claim_dates],
    })

    out = LANDING / "claims" / f"claims_{RUN_DATE}.csv"
    df.to_csv(out, index=False)
    print(f"[claims]  {n:>6,} rows  ->  {out.name}")
    return df["claim_id"].tolist()


if __name__ == "__main__":
    pat_df = pd.read_csv(LANDING / "patients"   / f"patients_{RUN_DATE}.csv")
    prv_df = pd.read_csv(LANDING / "providers"  / f"providers_{RUN_DATE}.csv")
    fac_df = pd.read_csv(LANDING / "facilities" / f"facilities_{RUN_DATE}.csv")
    pay_df = pd.read_csv(LANDING / "payers"     / f"payers_{RUN_DATE}.csv")
    generate_claims(
        pat_df["patient_id"].tolist(), prv_df["provider_id"].tolist(),
        fac_df["facility_id"].tolist(), pay_df["payer_id"].tolist()
    )

