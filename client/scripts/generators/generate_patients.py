import pandas as pd
import numpy as np
from faker import Faker
import uuid
from datetime import datetime, timedelta
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import LANDING, VOLUMES, SEED, RUN_DATE

fake = Faker()
Faker.seed(SEED + 3)
np.random.seed(SEED + 3)

STATES = ["CA","TX","FL","NY","PA","IL","OH","GA","NC","MI","WA","AZ","MA","TN","IN","MO","MD","WI","CO","MN"]
EMAIL_DOMAINS = ["gmail.com","yahoo.com","outlook.com","healthmail.org","email.net"]


def generate_patients(payer_ids, provider_ids):
    n = VOLUMES["patients"]
    rng = np.random.default_rng(SEED + 3)
    base_date = datetime(2026, 5, 15)

    POOL = 2000
    first_names = [fake.first_name() for _ in range(POOL)]
    last_names  = [fake.last_name()  for _ in range(POOL)]
    addresses   = [fake.street_address() for _ in range(POOL)]
    cities      = [fake.city() for _ in range(POOL)]

    fns = rng.choice(first_names, n)
    lns = rng.choice(last_names,  n)

    days_old = rng.integers(365, 365 * 90, n)
    dobs = [(base_date - timedelta(days=int(d))).strftime("%Y-%m-%d") for d in days_old]

    df = pd.DataFrame({
        "patient_id":          [str(uuid.uuid4()) for _ in range(n)],
        "first_name":          fns,
        "last_name":           lns,
        "date_of_birth":       dobs,
        "gender":              rng.choice(["M", "F", "Other"], n, p=[0.49, 0.49, 0.02]),
        "blood_type":          rng.choice(["A+","A-","B+","B-","AB+","AB-","O+","O-"], n, p=[0.34,0.06,0.09,0.02,0.03,0.01,0.38,0.07]),
        "address":             rng.choice(addresses, n),
        "city":                rng.choice(cities, n),
        "state":               rng.choice(STATES, n),
        "zip_code":            [f"{rng.integers(10000,99999):05d}" for _ in range(n)],
        "phone":               [f"({rng.integers(200,999)}){rng.integers(200,999)}-{rng.integers(1000,9999)}" for _ in range(n)],
        "email":               [f"{fns[i].lower()}.{lns[i].lower()}{rng.integers(1,999)}@{rng.choice(EMAIL_DOMAINS)}" for i in range(n)],
        "primary_payer_id":    rng.choice(payer_ids, n),
        "primary_provider_id": rng.choice(provider_ids, n),
        "created_at":          [(base_date - timedelta(days=int(rng.integers(0, 365*5)))).strftime("%Y-%m-%d %H:%M:%S") for _ in range(n)],
    })

    out = LANDING / "patients" / f"patients_{RUN_DATE}.csv"
    df.to_csv(out, index=False)
    print(f"[patients]  {n:>6,} rows  ->  {out.name}")
    return df["patient_id"].tolist()


if __name__ == "__main__":
    pay_df = pd.read_csv(LANDING / "payers"    / f"payers_{RUN_DATE}.csv")
    prv_df = pd.read_csv(LANDING / "providers" / f"providers_{RUN_DATE}.csv")
    generate_patients(pay_df["payer_id"].tolist(), prv_df["provider_id"].tolist())

