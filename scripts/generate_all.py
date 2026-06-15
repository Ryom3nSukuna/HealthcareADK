"""
Master runner for Phase 1 synthetic data generation.
Run from the project root:  python scripts/generate_all.py

Generation order (respects FK dependencies):
  1. payers, facilities   (no deps)
  2. providers            (needs facilities)
  3. patients             (needs payers, providers)
  4. claims               (needs patients, providers, facilities, payers)
  5. labs                 (needs patients, providers, facilities)
  6. prescriptions        (needs patients, providers, payers)
  7. financials           (needs facilities)
  8. EDI 837              (needs claims CSV)
  9. lab PDFs             (needs labs + patients CSVs)
"""
import time
import json
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from utils import LANDING, RUN_DATE

from generators.generate_payers        import generate_payers
from generators.generate_facilities    import generate_facilities
from generators.generate_providers     import generate_providers
from generators.generate_patients      import generate_patients
from generators.generate_claims        import generate_claims
from generators.generate_labs          import generate_labs
from generators.generate_prescriptions import generate_prescriptions
from generators.generate_financials    import generate_financials
from generators.generate_edi           import generate_edi
from generators.generate_lab_pdfs      import generate_lab_pdfs


def write_manifest(manifest: dict):
    out = LANDING / "manifest" / f"manifest_{RUN_DATE}.json"
    with open(out, "w") as f:
        json.dump(manifest, f, indent=2, default=str)
    print(f"\n[manifest]  ->  {out.name}")


def main():
    start_total = time.time()
    print("=" * 60)
    print(f"  HealthcareADK — Synthetic Data Generator")
    print(f"  Run date : {RUN_DATE}")
    print(f"  Started  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    manifest = {"run_date": RUN_DATE, "started_at": datetime.now().isoformat(), "entities": {}}

    def timed(label, fn, *args):
        t0 = time.time()
        result = fn(*args)
        elapsed = round(time.time() - t0, 1)
        manifest["entities"][label] = {"elapsed_sec": elapsed, "status": "ok"}
        return result

    # Step 1 — foundation (no deps)
    print("\n--- Step 1: Foundation entities ---")
    payer_ids    = timed("payers",    generate_payers)
    facility_ids = timed("facilities",generate_facilities)

    # Step 2 — providers (needs facilities)
    print("\n--- Step 2: Providers ---")
    provider_ids = timed("providers", generate_providers, facility_ids)

    # Step 3 — patients (needs payers + providers)
    print("\n--- Step 3: Patients ---")
    patient_ids  = timed("patients",  generate_patients, payer_ids, provider_ids)

    # Step 4 — transactional data
    print("\n--- Step 4: Transactional data ---")
    timed("claims",        generate_claims,        patient_ids, provider_ids, facility_ids, payer_ids)
    timed("labs",          generate_labs,           patient_ids, provider_ids, facility_ids)
    timed("prescriptions", generate_prescriptions,  patient_ids, provider_ids, payer_ids)
    timed("financials",    generate_financials,     facility_ids)

    # Step 5 — derived formats
    print("\n--- Step 5: Derived formats (EDI, PDF) ---")
    timed("edi_837",  generate_edi)
    timed("lab_pdfs", generate_lab_pdfs)

    # Manifest
    manifest["completed_at"]   = datetime.now().isoformat()
    manifest["total_elapsed_sec"] = round(time.time() - start_total, 1)
    write_manifest(manifest)

    print("\n" + "=" * 60)
    print(f"  ALL DONE in {manifest['total_elapsed_sec']}s")
    print("=" * 60)


if __name__ == "__main__":
    main()

