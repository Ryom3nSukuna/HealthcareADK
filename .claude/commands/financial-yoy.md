Run a year-over-year financial comparison against the HealthcareADK data warehouse.

User arguments (optional): $ARGUMENTS

Steps:
1. Parse any filters from $ARGUMENTS. Supported filters:
   - start_year: integer e.g. 2022
   - end_year: integer e.g. 2025
   - facility_id: UUID string to scope to a single facility
   If no arguments are given, run across all years and facilities.

2. Call `get_financial_yoy` with the parsed filters.

3. Present results as a markdown table grouped by FiscalYear, showing Revenue and Expense totals side by side.

4. Below the table, for each consecutive year pair compute and show:
   - Revenue YoY change: amount and percentage
   - Expense YoY change: amount and percentage
   - Net margin per year: (Revenue - Expense) / Revenue × 100

5. Call out the best and worst margin year in one sentence.
