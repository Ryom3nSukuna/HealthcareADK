import pandas as pd
import numpy as np
import uuid
import json
from datetime import datetime, timedelta
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import LANDING, VOLUMES, SEED, RUN_DATE, DRUGS

np.random.seed(SEED + 6)


def generate_prescriptions(patient_ids, provider_ids, payer_ids):
    n = VOLUMES["prescriptions"]
    rng = np.random.default_rng(SEED + 6)
    base_date = datetime(2026, 5, 15)

    drug_indices    = rng.integers(0, len(DRUGS), n)
    prescribed_days = rng.integers(0, 365 * 3, n)
    prescribed_dates = [(base_date - timedelta(days=int(d))).strftime("%Y-%m-%d") for d in prescribed_days]
    fill_dates       = [(datetime.strptime(pd_, "%Y-%m-%d") + timedelta(days=int(rng.integers(0, 7)))).strftime("%Y-%m-%d") for pd_ in prescribed_dates]

    refills_auth = rng.integers(0, 12, n)
    refills_rem  = np.array([rng.integers(0, int(ra) + 1) for ra in refills_auth])
    cost_patient = rng.uniform(5, 150, n).round(2)
    cost_payer   = rng.uniform(20, 800, n).round(2)

    df = pd.DataFrame({
        "prescription_id":    [str(uuid.uuid4()) for _ in range(n)],
        "patient_id":         rng.choice(patient_ids, n),
        "provider_id":        rng.choice(provider_ids, n),
        "drug_name":          [DRUGS[i][0] for i in drug_indices],
        "ndc_code":           [DRUGS[i][1] for i in drug_indices],
        "dosage":             [DRUGS[i][2] for i in drug_indices],
        "frequency":          [DRUGS[i][3] for i in drug_indices],
        "days_supply":        rng.choice([30, 60, 90], n, p=[0.60, 0.20, 0.20]),
        "quantity":           rng.integers(10, 180, n),
        "refills_authorized": refills_auth,
        "refills_remaining":  refills_rem,
        "prescribed_date":    prescribed_dates,
        "fill_date":          fill_dates,
        "payer_id":           rng.choice(payer_ids, n),
        "cost_to_patient":    cost_patient,
        "cost_to_payer":      cost_payer,
        "created_at":         fill_dates,
    })

    # CSV
    csv_out = LANDING / "prescriptions" / f"prescriptions_{RUN_DATE}.csv"
    df.to_csv(csv_out, index=False)
    print(f"[prescriptions/csv]   {n:>6,} rows  ->  {csv_out.name}")

    # JSON (mimics pharmacy API payload)
    sample = df.head(5000)
    records = sample.to_dict(orient="records")
    json_out = LANDING / "prescriptions" / f"prescriptions_{RUN_DATE}.json"
    with open(json_out, "w") as f:
        json.dump(records, f, indent=2, default=str)
    print(f"[prescriptions/json]  {len(records):>6,} rows  ->  {json_out.name}")

    return df["prescription_id"].tolist()


if __name__ == "__main__":
    pat_df = pd.read_csv(LANDING / "patients"  / f"patients_{RUN_DATE}.csv")
    prv_df = pd.read_csv(LANDING / "providers" / f"providers_{RUN_DATE}.csv")
    pay_df = pd.read_csv(LANDING / "payers"    / f"payers_{RUN_DATE}.csv")
    generate_prescriptions(
        pat_df["patient_id"].tolist(),
        prv_df["provider_id"].tolist(),
        pay_df["payer_id"].tolist()
    )

