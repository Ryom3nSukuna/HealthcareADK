Query abnormal and critical lab results from the HealthcareADK data warehouse.

User arguments (optional): $ARGUMENTS

Steps:
1. Parse any filters from $ARGUMENTS. Supported filters:
   - patient_id: UUID to scope to a single patient
   - start_date / end_date: YYYY-MM-DD
   - flag: High | Low | Critical  (omit for all abnormal results)
   - top_n: integer (default 200)
   If no arguments are given, return all abnormal results (High + Low + Critical) up to 200 rows.

2. Call `get_abnormal_labs` with the parsed filters.

3. Present results as a markdown table ordered by ServiceDate descending.

4. Below the table, add a summary line:
   "Critical: N | High: N | Low: N | Total abnormal: N"

5. If any Critical results are present, call them out explicitly:
   list the patient IDs and test names for every Critical row (or the top 5 if more than 5).
