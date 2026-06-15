# HealthcareADK — Power BI Design Guide

Report: **HealthcareADK Analytics**
Mode: Import | Server: localhost | Database: HealthcareADK | Schema: rpt

---

## Step 1 — Connect to SQL Server

1. **Home** → **Get Data** → **SQL Server**
2. Server: `localhost`, Database: `HealthcareADK`, Mode: **Import**
3. In the Navigator expand **rpt** and select all 5 views → **Load**

---

## Step 3 — Data Model Relationships

Go to **Model view** (left sidebar icon). Create these relationships:

| From | Column | To | Column | Cardinality | Cross-filter |
|---|---|---|---|---|---|
| `vw_ClaimsSummary` | `PatientID` | `vw_LabResults` | `PatientID` | Many-to-Many | Both |
| `vw_ClaimsSummary` | `PatientID` | `vw_Prescriptions` | `PatientID` | Many-to-Many | Both |

> `vw_FinancialKPIs` and `vw_ProviderPerformance` are standalone — no relationships needed.

---

## Step 4 — Create Measures Table

1. **Home** → **Enter Data** → rename column to `ID`, type `1` in row 1, name table `_Measures` → **Load**
2. In Fields pane, right-click `ID` column under `_Measures` → **Hide**
3. See [DAX_Measures.md](DAX_Measures.md) for all measures — add them one at a time via **Modeling** → **New Measure**

---

## Step 5 — How to Add Visuals

#### Add a page
Bottom of screen → click **+** → double-click tab to rename

#### Add a visual
Click an empty canvas area → pick visual type from **Visualizations** pane → resize by dragging corners

#### Assign fields
Select the visual → in the **Visualizations** pane drag fields from the **Fields** pane into the correct slot (X-axis, Y-axis, Legend, Values, etc.)

#### Add a slicer
Pick the **Slicer** icon → drag a column into **Field** → right-click the slicer → **Slicer settings** → choose **Dropdown** (saves canvas space)

#### Top N filter on a chart
Select the chart → **Filters** pane → expand the field → change **Basic filtering** to **Top N** → set count → drag the ranking measure into **By value** → **Apply filter**

#### Sort a chart
Click the **...** (More options) on the chart → **Sort axis** → pick the column and direction

---

## Step 6 — Report Pages

---

### Page 1: Claims Overview

**Purpose:** Executive summary of claims volume, financials, and denial performance.

#### KPI Cards — place in a row across the top

| Card | Field slot | Value |
|---|---|---|
| Total Claims | Fields | `[Total Claims]` |
| Total Billed | Fields | `[Total Billed]` |
| Total Paid | Fields | `[Total Paid]` |
| Denial Rate | Fields | `[Denial Rate %]` |

#### Visuals

**Clustered Bar Chart — Billed vs Paid by Payer Type**

| Slot | Value |
|---|---|
| Y-axis | `Claims[PayerType]` |
| X-axis | `[Total Billed]` |
| X-axis (add second) | `[Total Paid]` |

Sort by Total Billed descending.

---

**Donut Chart — Claims by Status**

| Slot | Value |
|---|---|
| Legend | `Claims[ClaimStatus]` |
| Values | `[Total Claims]` |

---

**Line Chart — Claims Volume Over Time**

| Slot | Value |
|---|---|
| X-axis | `Claims[ServiceYear]` then `Claims[ServiceMonthNum]` (drag both) |
| Y-axis | `[Total Claims]` |

---

**Bar Chart — Top 10 Denial Reasons**

| Slot | Value |
|---|---|
| Y-axis | `Claims[DenialReason]` |
| X-axis | `[Denied Claims]` |

Top N filter: Top 10 by `[Denied Claims]`. Sort by `[Denied Claims]` descending.

---

**Filled Map — Claims by Patient State**

| Slot | Value |
|---|---|
| Location | `Claims[PatientState]` |
| Bubble size | `[Total Claims]` |

---

**Slicers** (all Dropdown style)

| Slicer | Field |
|---|---|
| Year | `Claims[ServiceYear]` |
| Payer Type | `Claims[PayerType]` |
| Claim Status | `Claims[ClaimStatus]` |
| State | `Claims[PatientState]` |

---

### Page 2: Patient Demographics

**Purpose:** Patient population breakdown by age, gender, geography, and payer mix.

#### KPI Cards

| Card | Field slot | Value |
|---|---|---|
| Unique Patients | Fields | `[Unique Patients]` |
| Avg Age at Service | Fields | `[Avg Patient Age]` |

#### Calculated Column — Age Band

> Before adding the Age Band chart, create this calculated column on the `vw_ClaimsSummary` table:
> Right-click `vw_ClaimsSummary` in Fields pane → **New Column** → paste:

```dax
Age Band =
SWITCH(
    TRUE(),
    vw_ClaimsSummary[PatientAgeAtService] <= 18, "1. 0-18",
    vw_ClaimsSummary[PatientAgeAtService] <= 35, "2. 19-35",
    vw_ClaimsSummary[PatientAgeAtService] <= 50, "3. 36-50",
    vw_ClaimsSummary[PatientAgeAtService] <= 65, "4. 51-65",
    "5. 65+"
)
```

> The numeric prefix forces correct sort order.

#### Visuals

**Bar Chart — Patients by Age Band**

| Slot | Value |
|---|---|
| Y-axis | `Claims[Age Band]` |
| X-axis | `[Unique Patients]` |

Sort by Age Band ascending.

---

**Donut Chart — Gender Split**

| Slot | Value |
|---|---|
| Legend | `Claims[Gender]` |
| Values | `[Unique Patients]` |

---

**Donut Chart — Payer Mix**

| Slot | Value |
|---|---|
| Legend | `Claims[PayerType]` |
| Values | `[Unique Patients]` |

---

**Bar Chart — Claims by Plan Type**

| Slot | Value |
|---|---|
| Y-axis | `Claims[PlanType]` |
| X-axis | `[Total Claims]` |

Sort by `[Total Claims]` descending.

---

**Filled Map — Patients by State**

| Slot | Value |
|---|---|
| Location | `Claims[PatientState]` |
| Bubble size | `[Unique Patients]` |

---

**Slicers**

| Slicer | Field |
|---|---|
| Year | `Claims[ServiceYear]` |
| Gender | `Claims[Gender]` |
| Payer Type | `Claims[PayerType]` |
| State | `Claims[PatientState]` |

---

### Page 3: Provider Performance

**Purpose:** Provider leaderboard — claims volume, revenue generated, and denial rates.

> This page uses the `vw_ProviderPerformance` table which is pre-aggregated per provider per year/quarter.

#### KPI Cards

| Card | Field slot | Value |
|---|---|---|
| Total Providers | Fields | `[Total Providers]` |
| Avg Denial Rate | Fields | `[Avg Denial Rate %]` |
| Total Billed | Fields | `[Provider Total Billed]` |

#### Visuals

**Table — Provider Leaderboard**

Drag these columns into the **Columns** slot in order:

`ProviderPerformance[ProviderName]`, `ProviderPerformance[Specialty]`, `ProviderPerformance[TotalClaims]`, `ProviderPerformance[TotalBilled]`, `ProviderPerformance[TotalPaid]`, `ProviderPerformance[DenialRatePct]`

Sort by `TotalBilled` descending. In **Format** → **Conditional formatting** → enable **Data bars** on `TotalBilled` column.

---

**Bar Chart — Top 10 Providers by Total Billed**

| Slot | Value |
|---|---|
| Y-axis | `ProviderPerformance[ProviderName]` |
| X-axis | `ProviderPerformance[TotalBilled]` |

Top N filter: Top 10 by `TotalBilled`. Sort by `TotalBilled` descending.

---

**Bar Chart — Claims Volume by Specialty**

| Slot | Value |
|---|---|
| Y-axis | `ProviderPerformance[Specialty]` |
| X-axis | `ProviderPerformance[TotalClaims]` |

Sort by `TotalClaims` descending.

---

**Scatter Chart — Denial Rate vs Claims Volume**

| Slot | Value |
|---|---|
| X-axis | `ProviderPerformance[TotalClaims]` |
| Y-axis | `ProviderPerformance[DenialRatePct]` |
| Values (bubble size) | `ProviderPerformance[TotalBilled]` |
| Details | `ProviderPerformance[ProviderName]` |

> Each bubble = one provider. Large bubble = high billed amount. High on Y-axis = high denial rate. Providers in the top-left quadrant (low volume, high denial) need attention.

---

**Slicers**

| Slicer | Field |
|---|---|
| Year | `ProviderPerformance[ServiceYear]` |
| Quarter | `ProviderPerformance[ServiceQuarter]` |
| Specialty | `ProviderPerformance[Specialty]` |
| State | `ProviderPerformance[FacilityState]` |

---

### Page 4: Financial KPIs

**Purpose:** Revenue vs expense trends with year-over-year comparison and departmental breakdown.

> This page uses the `vw_FinancialKPIs` table.

#### KPI Cards — Row 1

| Card | Field slot | Value |
|---|---|---|
| Total Revenue | Fields | `[Total Revenue]` |
| Total Expenses | Fields | `[Total Expenses]` |
| Net Margin | Fields | `[Net Margin]` |
| Net Margin % | Fields | `[Net Margin %]` |

#### KPI Card — Row 2 (standalone, larger)

| Card | Field slot | Value |
|---|---|---|
| Revenue YoY % | Fields | `[Revenue YoY %]` |

#### Visuals

**Clustered Column Chart — Revenue vs Expenses by Fiscal Year**

| Slot | Value |
|---|---|
| X-axis | `Financials[FiscalYear]` |
| Y-axis | `[Total Revenue]` |
| Y-axis (add second) | `[Total Expenses]` |

Sort X-axis ascending by FiscalYear.

---

**Line Chart — Quarterly Revenue Trend**

| Slot | Value |
|---|---|
| X-axis | `Financials[FiscalYear]` then `Financials[FiscalQuarter]` |
| Y-axis | `[Total Revenue]` |
| Secondary Y-axis | `[Total Expenses]` |

---

**Bar Chart — Amount by Transaction Type**

| Slot | Value |
|---|---|
| Y-axis | `Financials[TransactionType]` |
| X-axis | `SUM of Financials[Amount]` |

Sort by Amount descending.

---

**Bar Chart — Top 10 Departments by Amount**

| Slot | Value |
|---|---|
| Y-axis | `Financials[Department]` |
| X-axis | `SUM of Financials[Amount]` |

Top N filter: Top 10 by `SUM of Amount`. Sort descending.

---

**Slicers**

| Slicer | Field |
|---|---|
| Fiscal Year | `Financials[FiscalYear]` |
| Transaction Type | `Financials[TransactionType]` |
| Facility | `Financials[FacilityName]` |
| State | `Financials[FacilityState]` |

---

### Page 5: Lab Trends

**Purpose:** Lab test volumes, abnormal result rates, and critical flag monitoring.

> This page uses the `vw_LabResults` table.

#### KPI Cards

| Card | Field slot | Value |
|---|---|---|
| Total Tests | Fields | `[Total Labs]` |
| Abnormal Rate | Fields | `[Abnormal Rate %]` |
| Critical Results | Fields | `[Critical Labs]` |

#### Visuals

**Bar Chart — Test Volume by Test Name**

| Slot | Value |
|---|---|
| Y-axis | `Labs[TestName]` |
| X-axis | `[Total Labs]` |

Sort by `[Total Labs]` descending.

---

**Donut Chart — Results by Abnormal Flag**

| Slot | Value |
|---|---|
| Legend | `Labs[AbnormalFlag]` |
| Values | `[Total Labs]` |

---

**Line Chart — Lab Volume Over Time**

| Slot | Value |
|---|---|
| X-axis | `Labs[OrderYear]` then `Labs[OrderQuarter]` |
| Y-axis | `[Total Labs]` |
| Legend | `Labs[AbnormalFlag]` |

> Adding AbnormalFlag to Legend shows Normal vs Abnormal trend lines on the same chart.

---

**Bar Chart — Abnormal Rate by Test**

| Slot | Value |
|---|---|
| Y-axis | `Labs[TestName]` |
| X-axis | `[Abnormal Rate %]` |

Sort by `[Abnormal Rate %]` descending. Apply conditional formatting → **Data bars** on X-axis.

---

**Bar Chart — Labs by Facility**

| Slot | Value |
|---|---|
| Y-axis | `Labs[FacilityName]` |
| X-axis | `[Total Labs]` |

Sort by `[Total Labs]` descending.

---

**Slicers**

| Slicer | Field |
|---|---|
| Year | `Labs[OrderYear]` |
| Abnormal Flag | `Labs[AbnormalFlag]` |
| Test Name | `Labs[TestName]` |
| Specialty | `Labs[Specialty]` |

---

### Page 6: Prescription Analytics

**Purpose:** Drug utilization, cost burden split between patient and payer, and prescribing trends.

> This page uses the `vw_Prescriptions` table.

#### KPI Cards

| Card | Field slot | Value |
|---|---|---|
| Total Prescriptions | Fields | `[Total Prescriptions]` |
| Total Rx Cost | Fields | `[Total Rx Cost]` |
| Avg Cost per Rx | Fields | `[Avg Cost per Rx]` |
| Patient Cost Share | Fields | `[Patient Cost Share %]` |

#### Visuals

**Bar Chart — Top 10 Drugs by Volume**

| Slot | Value |
|---|---|
| Y-axis | `Prescriptions[DrugName]` |
| X-axis | `[Total Prescriptions]` |

Top N filter: Top 10 by `[Total Prescriptions]`. Sort descending.

---

**Bar Chart — Top 10 Drugs by Total Cost**

| Slot | Value |
|---|---|
| Y-axis | `Prescriptions[DrugName]` |
| X-axis | `[Total Rx Cost]` |

Top N filter: Top 10 by `[Total Rx Cost]`. Sort descending.

---

**Stacked Bar Chart — Patient vs Payer Cost by Drug**

| Slot | Value |
|---|---|
| Y-axis | `Prescriptions[DrugName]` |
| X-axis | `[Total Patient Cost]` |
| X-axis (add second) | `[Total Payer Cost]` |

> Switch visual type to **100% Stacked Bar** to show the cost share ratio per drug.

Top N filter: Top 10 by `[Total Rx Cost]`.

---

**Line Chart — Prescription Volume Over Time**

| Slot | Value |
|---|---|
| X-axis | `Prescriptions[PrescribedYear]` then `Prescriptions[PrescribedQuarter]` |
| Y-axis | `[Total Prescriptions]` |

---

**Donut Chart — Total Cost by Payer Type**

| Slot | Value |
|---|---|
| Legend | `Prescriptions[PayerType]` |
| Values | `[Total Rx Cost]` |

---

**Slicers**

| Slicer | Field |
|---|---|
| Year | `Prescriptions[PrescribedYear]` |
| Drug | `Prescriptions[DrugName]` |
| Payer Type | `Prescriptions[PayerType]` |
| State | `Prescriptions[PatientState]` |

---

## Step 7 — Formatting

- **Theme:** View → Themes → **Accessible Default** (clean, contrast-friendly)
- **Page size:** View → Page view → **16:9** on every page
- **Currency measures:** Select each currency measure in Fields pane → Modeling tab → Format: `Currency`, Symbol: `$`, Decimal places: `0`
- **Percentage measures:** Format: `Percentage`, Decimal places: `1`
- **Card titles:** Double-click a card's title area to rename it to a plain English label (e.g. "Denial Rate" not "Denial Rate %")
- **Slicer layout:** Right-click each slicer → **Slicer settings** → Orientation: **Dropdown**
- **Persistent filters:** File → Options → Report settings → turn on **Persistent filters**

---

## Step 8 — Verify Row Counts

After the report loads, the KPI cards on each page should show approximately:

| Page | Measure | Expected |
|---|---|---|
| Claims Overview | Total Claims | ~50,000 |
| Patient Demographics | Unique Patients | ~50,000 |
| Provider Performance | Total Providers | ~5,000 |
| Lab Trends | Total Tests | ~50,000 |
| Prescription Analytics | Total Prescriptions | ~50,000 |
