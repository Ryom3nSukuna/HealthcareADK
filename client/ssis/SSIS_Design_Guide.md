# HealthcareADK — SSIS Design Guide

Build these packages in **Visual Studio 2019/2022 with SSDT** (SQL Server Data Tools).
Create a new **Integration Services Project** named `HealthcareADK_ETL`.

---

## Prerequisites

- SQL Server with HealthcareADK database created (run sql/00 through sql/08 in SSMS first)
- ODBC Driver 17 or 18 for SQL Server installed
- Landing zone data generated (`python scripts/generate_all.py`)

---

## Connection Managers (shared across all packages)

Create these at the **project level** so all packages share them.

| Name | Type | Settings |
|------|------|----------|
| `CM_HealthcareADK` | OLE DB | Server: `localhost` (or your instance), Database: `HealthcareADK`, Auth: Windows |

> `CM_LandingZone` is **not** a Connection Manager — it was a doc error. The landing zone path is handled via Project Parameters + expressions on each Flat File Connection Manager (see below).

### Project Parameters

Create these under **Project → Project Parameters**:

| Parameter | Type | Default |
|-----------|------|---------|
| `LandingZonePath` | String | `C:\LocalRepo\HealthcareADK\landing_zone` |
| `RunDate` | String | `20260519` *(update to match your generated file date)* |

### Flat File Connection Managers (one per entity)

For each DFT in Package_Load_Staging, create a **Flat File Connection Manager**. After creating it, right-click → **Properties** → **Expressions** → set `ConnectionString` to the expression for that entity:

| CM Name | ConnectionString Expression |
|---------|----------------------------|
| `FF_Payers` | `@[$Project::LandingZonePath] + "\\payers\\payers_" + @[$Project::RunDate] + ".csv"` |
| `FF_Facilities` | `@[$Project::LandingZonePath] + "\\facilities\\facilities_" + @[$Project::RunDate] + ".csv"` |
| `FF_Providers` | `@[$Project::LandingZonePath] + "\\providers\\providers_" + @[$Project::RunDate] + ".csv"` |
| `FF_Patients` | `@[$Project::LandingZonePath] + "\\patients\\patients_" + @[$Project::RunDate] + ".csv"` |
| `FF_Claims` | `@[$Project::LandingZonePath] + "\\claims\\claims_" + @[$Project::RunDate] + ".csv"` |
| `FF_Labs` | `@[$Project::LandingZonePath] + "\\labs\\labs_" + @[$Project::RunDate] + ".csv"` |
| `FF_Prescriptions` | `@[$Project::LandingZonePath] + "\\prescriptions\\prescriptions_" + @[$Project::RunDate] + ".csv"` |

> **Financials** uses an **Excel Connection Manager** (not Flat File) — see the Load stg.Financials section.

---

## Package 1 — `Package_Load_Staging.dtsx`

**Purpose:** Reads all CSV/Excel files from `landing_zone/` and bulk-loads them into the `stg.*` tables.

**Control Flow:** 8 Data Flow Tasks in a Sequence Container, connected with success constraints.

```
[SEQ: Load All Staging]
  ├── DFT: Load stg.Payers
  ├── DFT: Load stg.Facilities
  ├── DFT: Load stg.Providers
  ├── DFT: Load stg.Patients
  ├── DFT: Load stg.Claims
  ├── DFT: Load stg.Labs
  ├── DFT: Load stg.Prescriptions
  └── DFT: Load stg.Financials
```

### Data Flow: Load stg.Payers
| Component | Type | Settings |
|-----------|------|----------|
| Source | Flat File Source | File: `@[$Project::LandingZonePath]\payers\payers_@[$Project::RunDate].csv`, Header row, comma delimited |
| Derived Column | Derived Column | Add column: `stg_source_file` = `"payers_" + @[$Project::RunDate] + ".csv"` |
| Destination | OLE DB Destination | Connection: `CM_HealthcareADK`, Table: `[stg].[Payers]`, Fast Load ON |

**Column mapping** (Flat File → stg.Payers):

| Source Column | Destination Column |
|---|---|
| payer_id | payer_id |
| payer_name | payer_name |
| payer_type | payer_type |
| plan_name | plan_name |
| plan_type | plan_type |
| address | address |
| city | city |
| state | state |
| zip_code | zip_code |
| phone | phone |
| created_at | created_at |
| *(Derived)* stg_source_file | stg_source_file |

> All other stg columns (`stg_load_id`, `stg_load_date`, `stg_status`) use SQL Server defaults — do **not** map them.

---

### Data Flow: Load stg.Facilities
Same pattern as Payers. Source file: `facilities\facilities_@RunDate.csv`

Columns to map: `facility_id`, `facility_name`, `facility_type`, `npi`, `address`, `city`, `state`, `zip_code`, `phone`, `bed_count`, `created_at`, + derived `stg_source_file`

---

### Data Flow: Load stg.Providers
Source file: `providers\providers_@RunDate.csv`

Columns: `provider_id`, `npi`, `first_name`, `last_name`, `specialty`, `license_number`, `facility_id`, `phone`, `email`, `years_experience`, `created_at`, + derived `stg_source_file`

---

### Data Flow: Load stg.Patients
Source file: `patients\patients_@RunDate.csv`

Columns: `patient_id`, `first_name`, `last_name`, `date_of_birth`, `gender`, `blood_type`, `address`, `city`, `state`, `zip_code`, `phone`, `email`, `primary_payer_id`, `primary_provider_id`, `created_at`, + derived `stg_source_file`

---

### Data Flow: Load stg.Claims
Source file: `claims\claims_@RunDate.csv`

Columns: `claim_id`, `patient_id`, `provider_id`, `facility_id`, `payer_id`, `claim_date`, `service_date`, `icd10_primary`, `icd10_secondary`, `procedure_code`, `billed_amount`, `allowed_amount`, `paid_amount`, `claim_status`, `denial_reason`, `created_at`, + derived `stg_source_file`

> **EDI X12 837P files** (`claims\edi\*.edi`) are also present in the landing zone (50 batch files, 1,000 claims each). SSIS does not load these — they are a transaction interchange format for payer submission, not a DW data source. The CSV is the authoritative source for staging. The EDI files will be consumed in **Phase 5** by the ClaimsAgent for parsing and validation.

---

### Data Flow: Load stg.Labs
Source file: `labs\labs_@RunDate.csv`

Columns: `lab_id`, `patient_id`, `provider_id`, `facility_id`, `order_date`, `result_date`, `test_name`, `loinc_code`, `result_value`, `result_unit`, `reference_range_low`, `reference_range_high`, `abnormal_flag`, `created_at`, + derived `stg_source_file`

> **PDF lab reports** (`labs\pdf\lab_report_*.pdf`) are also present in the landing zone (100 reports). These are human-readable documents and cannot be loaded by SSIS. The CSV is the authoritative source for staging. The PDF files will be consumed in **Phase 5** by the ClinicalAgent as a RAG source for document summarization and Q&A.

---

### Data Flow: Load stg.Prescriptions
Source file: `prescriptions\prescriptions_@RunDate.csv`

Columns: `prescription_id`, `patient_id`, `provider_id`, `drug_name`, `ndc_code`, `dosage`, `frequency`, `days_supply`, `quantity`, `refills_authorized`, `refills_remaining`, `prescribed_date`, `fill_date`, `payer_id`, `cost_to_patient`, `cost_to_payer`, `created_at`, + derived `stg_source_file`

---

### Data Flow: Load stg.Financials
Source: **Excel Source** (not Flat File)

| Setting | Value |
|---------|-------|
| Connection Manager | Excel — `landing_zone\financials\financials_@RunDate.xlsx` |
| Sheet | `Sheet1$` |
| Component | Excel Source → OLE DB Destination |

Columns: `transaction_id`, `transaction_date`, `transaction_type`, `department`, `facility_id`, `amount`, `fiscal_year`, `fiscal_quarter`, `cost_center`, `gl_account`, `description`, `created_at`, + derived `stg_source_file`

> **Note:** Excel source outputs all columns as Unicode strings. SSIS will handle the cast to `VARCHAR` on the OLE DB destination side since stg columns are already `VARCHAR`.

---

## Package 2 — `Package_Load_DW.dtsx`

**Purpose:** Transforms `stg.*` data into the star schema by calling the ETL stored procedures.

**Control Flow:** Single Execute SQL Task.

```
[SQL Task: Run ETL]
  Connection : CM_HealthcareADK
  SQLStatement: EXEC dw.usp_ETL_RunAll
  ResultSet   : None
```

That's it — all the transform logic lives in `sql/08_etl_stg_to_dw.sql`. SSIS just pulls the trigger.

---

## Package 3 — `Package_Master.dtsx`

**Purpose:** Orchestrator — runs Package 1 then Package 2 in sequence.

```
[Execute Package Task: Load Staging]  →(Success)→  [Execute Package Task: Load DW]
```

| Task | Package |
|------|---------|
| Execute Package Task 1 | `Package_Load_Staging.dtsx` |
| Execute Package Task 2 | `Package_Load_DW.dtsx` |

Set both to **reference type: Project reference**.

---

## ETL Run Order (enforced by stored procedures)

```
DimPayer → DimFacility → DimProvider → DimPatient
                                           ↓
                    FactClaims + FactLabResults + FactPrescriptions + FactFinancials
```

---

## Verifying a successful run

After running `Package_Master.dtsx`, check in SSMS:

```sql
-- ETL run summary
SELECT Entity, RowsInserted, RowsUpdated, RowsSkipped, Status,
       DATEDIFF(SECOND, RunStarted, RunFinished) AS DurationSec
FROM dw.ETLLog
ORDER BY LogID DESC;

-- Row counts
SELECT 'DimPatient'       , COUNT(*) FROM dw.DimPatient   WHERE IsCurrent = 1
UNION ALL
SELECT 'DimProvider'      , COUNT(*) FROM dw.DimProvider
UNION ALL
SELECT 'FactClaims'       , COUNT(*) FROM dw.FactClaims
UNION ALL
SELECT 'FactLabResults'   , COUNT(*) FROM dw.FactLabResults
UNION ALL
SELECT 'FactPrescriptions', COUNT(*) FROM dw.FactPrescriptions
UNION ALL
SELECT 'FactFinancials'   , COUNT(*) FROM dw.FactFinancials;
```

Expected: ~50,000 rows in each fact table, ~50,000 patients, ~5,000 providers.
