import pandas as pd
import numpy as np
from faker import Faker
import uuid
from datetime import datetime, timedelta
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import LANDING, VOLUMES, SEED, RUN_DATE, SPECIALTIES

fake = Faker()
Faker.seed(SEED + 2)
np.random.seed(SEED + 2)


def generate_providers(facility_ids):
    n = VOLUMES["providers"]
    rng = np.random.default_rng(SEED + 2)
    base_date = datetime(2026, 5, 15)

    POOL = 1000
    first_names = [fake.first_name() for _ in range(POOL)]
    last_names  = [fake.last_name()  for _ in range(POOL)]

    specialties      = rng.choice(SPECIALTIES, n)
    years_experience = rng.integers(1, 40, n)

    df = pd.DataFrame({
        "provider_id":       [str(uuid.uuid4()) for _ in range(n)],
        "npi":               [f"{rng.integers(1000000000, 9999999999)}" for _ in range(n)],
        "first_name":        rng.choice(first_names, n),
        "last_name":         rng.choice(last_names, n),
        "specialty":         specialties,
        "license_number":    [f"MD{rng.integers(100000, 999999)}" for _ in range(n)],
        "facility_id":       rng.choice(facility_ids, n),
        "phone":             [f"({rng.integers(200,999)}){rng.integers(200,999)}-{rng.integers(1000,9999)}" for _ in range(n)],
        "email":             [f"dr.{first_names[rng.integers(0,POOL)].lower()}.{last_names[rng.integers(0,POOL)].lower()}@healthsystem.org" for _ in range(n)],
        "years_experience":  years_experience,
        "created_at":        [(base_date - timedelta(days=int(rng.integers(0, 365*15)))).strftime("%Y-%m-%d %H:%M:%S") for _ in range(n)],
    })

    out = LANDING / "providers" / f"providers_{RUN_DATE}.csv"
    df.to_csv(out, index=False)
    print(f"[providers]  {n:>6,} rows  ->  {out.name}")
    return df["provider_id"].tolist()


if __name__ == "__main__":
    fac_df = pd.read_csv(LANDING / "facilities" / f"facilities_{RUN_DATE}.csv")
    generate_providers(fac_df["facility_id"].tolist())

