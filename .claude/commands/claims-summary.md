Run a claims summary analysis against the HealthcareADK data warehouse.

User arguments (optional, space-separated or natural language): $ARGUMENTS

Steps:
1. Parse any filters from $ARGUMENTS. Supported filters:
   - Date range: start_date and end_date (YYYY-MM-DD)
   - payer: Commercial | Medicare | Medicaid | Self-Pay
   - status: Approved | Denied | Pending | Appealed
   - state: 2-letter code e.g. TX, CA
   - top_n: integer (default 100)
   If no arguments are given, run unfiltered (all payers, all statuses, all time).

2. Call `get_claims_summary` with the parsed filters.

3. Present results as a markdown table.

4. Below the table, add a one-line summary:
   "Total claims: N | Total billed: $X | Total paid: $X | Denial rate: X%"
   Compute denial rate as (Denied claims / Total claims) × 100 if ClaimStatus is in the result set,
   otherwise use DenialRatePct if available.
