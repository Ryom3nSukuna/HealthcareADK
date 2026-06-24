import pandas as pd
import numpy as np
from faker import Faker
import uuid
from datetime import datetime, timedelta
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import LANDING, VOLUMES, SEED, RUN_DATE, HOSPITAL_NAMES

fake = Faker()
Faker.seed(SEED + 1)
np.random.seed(SEED + 1)


def generate_facilities():
    n = VOLUMES["facilities"]
    rng = np.random.default_rng(SEED + 1)
    base_date = datetime(2026, 5, 15)

    fac_types = rng.choice(["Hospital", "Clinic", "Laboratory", "Pharmacy", "Urgent Care"], n, p=[0.25, 0.40, 0.15, 0.10, 0.10])
    states    = rng.choice(["CA","TX","FL","NY","PA","IL","OH","GA","NC","MI","WA","AZ","MA","TN","IN","MO","MD","WI","CO","MN"], n)

    cities = [fake.city() for _ in range(n)]
    name_pool = HOSPITAL_NAMES * ((n // len(HOSPITAL_NAMES)) + 1)

    df = pd.DataFrame({
        "facility_id":   [str(uuid.uuid4()) for _ in range(n)],
        "facility_name": [f"{cities[i]} {name_pool[i]}" for i in range(n)],
        "facility_type": fac_types,
        "npi":           [f"{rng.integers(1000000000, 9999999999)}" for _ in range(n)],
        "address":       [fake.street_address() for _ in range(n)],
        "city":          cities,
        "state":         states,
        "zip_code":      [f"{rng.integers(10000,99999):05d}" for _ in range(n)],
        "phone":         [f"({rng.integers(200,999)}){rng.integers(200,999)}-{rng.integers(1000,9999)}" for _ in range(n)],
        "bed_count":     [int(rng.integers(20, 800)) if t == "Hospital" else 0 for t in fac_types],
        "created_at":    [(base_date - timedelta(days=int(rng.integers(0, 365*20)))).strftime("%Y-%m-%d %H:%M:%S") for _ in range(n)],
    })

    out = LANDING / "facilities" / f"facilities_{RUN_DATE}.csv"
    df.to_csv(out, index=False)
    print(f"[facilities]  {n:>6,} rows  ->  {out.name}")
    return df["facility_id"].tolist()


if __name__ == "__main__":
    generate_facilities()

