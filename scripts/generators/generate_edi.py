"""
Generates X12 EDI 837P (Professional Claims) files from claims CSV.
Batches 1,000 claims per file -> 50 EDI files for 50,000 claims.
Simplified but structurally valid X12 837P segments.
"""
import pandas as pd
from datetime import datetime
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import LANDING, RUN_DATE

BATCH_SIZE = 1_000
SENDER_ID  = "HEALTHCAREADK    "   # 15 chars (ISA06 requires 15)
RECEIVER_ID= "CLEARINGHOUSE    "   # 15 chars


def _isa_header(interchange_num: int, dt: datetime) -> str:
    date_str = dt.strftime("%y%m%d")
    time_str = dt.strftime("%H%M")
    return (
        f"ISA*00*          *00*          *ZZ*{SENDER_ID}*ZZ*{RECEIVER_ID}"
        f"*{date_str}*{time_str}*^*00501*{interchange_num:09d}*0*P*:~\n"
    )


def _isa_trailer(interchange_num: int) -> str:
    return f"IEA*1*{interchange_num:09d}~\n"


def _gs_header(group_num: int, dt: datetime) -> str:
    return (
        f"GS*HC*HEALTHADK*CLEARINGHS*{dt.strftime('%Y%m%d')}*{dt.strftime('%H%M')}"
        f"*{group_num}*X*005010X222A1~\n"
    )


def _gs_trailer(group_num: int, tx_count: int) -> str:
    return f"GE*{tx_count}*{group_num}~\n"


def _claim_transaction(row, tx_num: int) -> str:
    st  = f"ST*837*{tx_num:04d}*005010X222A1~\n"
    bht = f"BHT*0019*00*{tx_num:04d}*{row['claim_date'].replace('-','')}*1200*CH~\n"

    # Submitter (NM1*41)
    sub = f"NM1*41*2*HEALTHCARE ADK*****46*{tx_num:010d}~\n"
    # Subscriber (NM1*IL) — simplified
    sbr = f"SBR*P*18*{row['payer_id'][:9]}*{row['payer_id'][:9]}****CI~\n"
    pat = f"NM1*IL*1*PATIENT*LAST*****MI*{row['patient_id'][:12]}~\n"
    # Claim (CLM)
    clm = (
        f"CLM*{row['claim_id'][:20]}*{row['billed_amount']:.2f}***11:B:1*Y*A*Y*I~\n"
        f"DTP*472*D8*{row['service_date'].replace('-','')}~\n"
        f"HI*ABK:{row['icd10_primary'].replace('.', '')}~\n"
        f"NM1*82*1*PROVIDER*FIRST*****XX*{row['provider_id'][:10]}~\n"
        f"LX*1~\n"
        f"SV1*HC:{row['procedure_code']}*{row['billed_amount']:.2f}*UN*1***1~\n"
        f"DTP*472*D8*{row['service_date'].replace('-','')}~\n"
    )
    se_count = 12
    se = f"SE*{se_count}*{tx_num:04d}~\n"
    return st + bht + sub + sbr + pat + clm + se


def generate_edi():
    claims_path = LANDING / "claims" / f"claims_{RUN_DATE}.csv"
    if not claims_path.exists():
        print(f"[edi] claims CSV not found: {claims_path} — run generate_claims.py first")
        return

    df = pd.read_csv(claims_path)
    total     = len(df)
    batches   = (total + BATCH_SIZE - 1) // BATCH_SIZE
    now       = datetime.now()
    files_out = []

    for batch_idx in range(batches):
        batch   = df.iloc[batch_idx * BATCH_SIZE : (batch_idx + 1) * BATCH_SIZE]
        out_path = LANDING / "claims" / f"claims_{RUN_DATE}_batch{batch_idx+1:03d}.edi"

        lines = []
        lines.append(_isa_header(batch_idx + 1, now))
        lines.append(_gs_header(batch_idx + 1, now))

        for tx_num, (_, row) in enumerate(batch.iterrows(), start=1):
            lines.append(_claim_transaction(row, tx_num))

        lines.append(_gs_trailer(batch_idx + 1, len(batch)))
        lines.append(_isa_trailer(batch_idx + 1))

        with open(out_path, "w") as f:
            f.writelines(lines)

        files_out.append(out_path.name)

    print(f"[edi]  {total:>6,} claims  ->  {batches} EDI files (batch size {BATCH_SIZE})")
    return files_out


if __name__ == "__main__":
    generate_edi()

