import pandas as pd
import numpy as np
from faker import Faker
import uuid
from datetime import datetime, timedelta
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import LANDING, VOLUMES, SEED, RUN_DATE, PAYER_NAMES

fake = Faker()
Faker.seed(SEED)
np.random.seed(SEED)


def generate_payers():
    n = VOLUMES["payers"]
    rng = np.random.default_rng(SEED)
    base_date = datetime(2026, 5, 15)

    payer_types  = rng.choice(["Commercial", "Medicare", "Medicaid", "Self-Pay"], n, p=[0.50, 0.20, 0.20, 0.10])
    plan_types   = rng.choice(["HMO", "PPO", "EPO", "POS"], n, p=[0.30, 0.40, 0.15, 0.15])
    states       = rng.choice(["CA","TX","FL","NY","PA","IL","OH","GA","NC","MI","WA","AZ","MA","TN","IN","MO","MD","WI","CO","MN"], n)

    base_names = (PAYER_NAMES * ((n // len(PAYER_NAMES)) + 1))[:n]
    suffixes   = [f" Plan {i+1}" if i >= len(PAYER_NAMES) else "" for i in range(n)]

    df = pd.DataFrame({
        "payer_id":   [str(uuid.uuid4()) for _ in range(n)],
        "payer_name": [f"{base_names[i]}{suffixes[i]}" for i in range(n)],
        "payer_type": payer_types,
        "plan_name":  [f"{pt} {plan_types[i]} Plan" for i, pt in enumerate(payer_types)],
        "plan_type":  plan_types,
        "address":    [fake.street_address() for _ in range(n)],
        "city":       [fake.city()           for _ in range(n)],
        "state":      states,
        "zip_code":   [f"{rng.integers(10000,99999):05d}" for _ in range(n)],
        "phone":      [f"({rng.integers(200,999)}){rng.integers(200,999)}-{rng.integers(1000,9999)}" for _ in range(n)],
        "created_at": [(base_date - timedelta(days=int(rng.integers(0, 365*10)))).strftime("%Y-%m-%d %H:%M:%S") for _ in range(n)],
    })

    out = LANDING / "payers" / f"payers_{RUN_DATE}.csv"
    df.to_csv(out, index=False)
    print(f"[payers]  {n:>6,} rows  ->  {out.name}")
    return df["payer_id"].tolist()


if __name__ == "__main__":
    generate_payers()

