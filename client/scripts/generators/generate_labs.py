import pandas as pd
import numpy as np
import uuid
import json
from datetime import datetime, timedelta
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import LANDING, VOLUMES, SEED, RUN_DATE, LAB_TESTS

np.random.seed(SEED + 5)


def generate_labs(patient_ids, provider_ids, facility_ids):
    n = VOLUMES["labs"]
    rng = np.random.default_rng(SEED + 5)
    base_date = datetime(2026, 5, 15)

    test_indices = rng.integers(0, len(LAB_TESTS), n)
    order_days   = rng.integers(0, 365 * 3, n)
    order_dates  = [(base_date - timedelta(days=int(d))).strftime("%Y-%m-%d") for d in order_days]
    result_dates = [(datetime.strptime(od, "%Y-%m-%d") + timedelta(days=int(rng.integers(1, 5)))).strftime("%Y-%m-%d") for od in order_dates]

    results, units, ref_lows, ref_highs, flags = [], [], [], [], []
    for i in test_indices:
        name, loinc, unit, ref_lo, ref_hi, min_v, max_v = LAB_TESTS[i]
        val = float(rng.uniform(min_v, max_v))
        results.append(round(val, 2))
        units.append(unit)
        ref_lows.append(ref_lo)
        ref_highs.append(ref_hi)
        if val < ref_lo:
            flags.append("Low")
        elif val > ref_hi * 1.5:
            flags.append("Critical")
        elif val > ref_hi:
            flags.append("High")
        else:
            flags.append("Normal")

    df = pd.DataFrame({
        "lab_id":              [str(uuid.uuid4()) for _ in range(n)],
        "patient_id":          rng.choice(patient_ids, n),
        "provider_id":         rng.choice(provider_ids, n),
        "facility_id":         rng.choice(facility_ids, n),
        "order_date":          order_dates,
        "result_date":         result_dates,
        "test_name":           [LAB_TESTS[i][0] for i in test_indices],
        "loinc_code":          [LAB_TESTS[i][1] for i in test_indices],
        "result_value":        results,
        "result_unit":         units,
        "reference_range_low": ref_lows,
        "reference_range_high":ref_highs,
        "abnormal_flag":       flags,
        "created_at":          result_dates,
    })

    # Save CSV
    csv_out = LANDING / "labs" / f"labs_{RUN_DATE}.csv"
    df.to_csv(csv_out, index=False)
    print(f"[labs/csv]   {n:>6,} rows  ->  {csv_out.name}")

    # Save JSON (nested format — mimics API/instrument output)
    sample = df.head(5000)
    records = []
    for _, row in sample.iterrows():
        records.append({
            "lab_id":     row["lab_id"],
            "patient_id": row["patient_id"],
            "order_date": row["order_date"],
            "result": {
                "test_name":       row["test_name"],
                "loinc_code":      row["loinc_code"],
                "value":           row["result_value"],
                "unit":            row["result_unit"],
                "reference_range": {"low": row["reference_range_low"], "high": row["reference_range_high"]},
                "flag":            row["abnormal_flag"],
                "result_date":     row["result_date"],
            }
        })
    json_out = LANDING / "labs" / f"labs_{RUN_DATE}.json"
    with open(json_out, "w") as f:
        json.dump(records, f, indent=2)
    print(f"[labs/json]  {len(records):>6,} rows  ->  {json_out.name}")

    return df["lab_id"].tolist()


if __name__ == "__main__":
    pat_df = pd.read_csv(LANDING / "patients"   / f"patients_{RUN_DATE}.csv")
    prv_df = pd.read_csv(LANDING / "providers"  / f"providers_{RUN_DATE}.csv")
    fac_df = pd.read_csv(LANDING / "facilities" / f"facilities_{RUN_DATE}.csv")
    generate_labs(
        pat_df["patient_id"].tolist(),
        prv_df["provider_id"].tolist(),
        fac_df["facility_id"].tolist()
    )

