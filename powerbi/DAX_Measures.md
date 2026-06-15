# HealthcareADK — DAX Measures Reference

All measures live in the `_Measures` table.
Create each via: right-click `_Measures` → **New Measure**.

---

## Claims Measures
*(Source: `vw_ClaimsSummary`)*

```dax
Total Claims =
COUNTROWS(vw_ClaimsSummary)

Total Billed =
SUM(vw_ClaimsSummary[BilledAmount])

Total Allowed =
SUM(vw_ClaimsSummary[AllowedAmount])

Total Paid =
SUM(vw_ClaimsSummary[PaidAmount])

Total Write-Off =
SUM(vw_ClaimsSummary[WriteOffAmount])

Denied Claims =
CALCULATE(
    COUNTROWS(vw_ClaimsSummary),
    vw_ClaimsSummary[ClaimStatus] = "Denied"
)

Denial Rate % =
DIVIDE([Denied Claims], [Total Claims], 0) * 100

Approval Rate % =
DIVIDE(
    CALCULATE(COUNTROWS(vw_ClaimsSummary), vw_ClaimsSummary[ClaimStatus] = "Approved"),
    [Total Claims],
    0
) * 100

Avg Claim Value =
DIVIDE([Total Billed], [Total Claims], 0)

Collection Rate % =
DIVIDE([Total Paid], [Total Billed], 0) * 100
```

---

## Patient Measures
*(Source: `vw_ClaimsSummary`)*

```dax
Unique Patients =
DISTINCTCOUNT(vw_ClaimsSummary[PatientID])

Avg Patient Age =
AVERAGE(vw_ClaimsSummary[PatientAgeAtService])
```

---

## Provider Measures
*(Source: `vw_ProviderPerformance`)*

```dax
Total Providers =
DISTINCTCOUNT(vw_ProviderPerformance[ProviderID])

Provider Total Billed =
SUM(vw_ProviderPerformance[TotalBilled])

Provider Total Paid =
SUM(vw_ProviderPerformance[TotalPaid])

Avg Denial Rate % =
AVERAGE(vw_ProviderPerformance[DenialRatePct])
```

---

## Financial Measures
*(Source: `vw_FinancialKPIs`)*

```dax
Total Revenue =
CALCULATE(
    SUM(vw_FinancialKPIs[Amount]),
    vw_FinancialKPIs[TransactionType] = "Revenue"
)

Total Expenses =
CALCULATE(
    SUM(vw_FinancialKPIs[Amount]),
    vw_FinancialKPIs[TransactionType] = "Expense"
)

Net Margin =
[Total Revenue] - [Total Expenses]

Net Margin % =
DIVIDE([Net Margin], [Total Revenue], 0) * 100

Revenue PY =
CALCULATE(
    [Total Revenue],
    FILTER(
        ALL(vw_FinancialKPIs),
        vw_FinancialKPIs[FiscalYear] = MAX(vw_FinancialKPIs[FiscalYear]) - 1
    )
)

Revenue YoY % =
DIVIDE([Total Revenue] - [Revenue PY], [Revenue PY], 0) * 100

Expenses PY =
CALCULATE(
    [Total Expenses],
    FILTER(
        ALL(vw_FinancialKPIs),
        vw_FinancialKPIs[FiscalYear] = MAX(vw_FinancialKPIs[FiscalYear]) - 1
    )
)

Expenses YoY % =
DIVIDE([Total Expenses] - [Expenses PY], [Expenses PY], 0) * 100
```

---

## Lab Measures
*(Source: `vw_LabResults`)*

```dax
Total Labs =
COUNTROWS(vw_LabResults)

Abnormal Labs =
CALCULATE(
    COUNTROWS(vw_LabResults),
    vw_LabResults[AbnormalFlag] <> "Normal"
)

Abnormal Rate % =
DIVIDE([Abnormal Labs], [Total Labs], 0) * 100

Critical Labs =
CALCULATE(
    COUNTROWS(vw_LabResults),
    vw_LabResults[AbnormalFlag] = "Critical"
)

Critical Rate % =
DIVIDE([Critical Labs], [Total Labs], 0) * 100
```

---

## Prescription Measures
*(Source: `vw_Prescriptions`)*

```dax
Total Prescriptions =
COUNTROWS(vw_Prescriptions)

Total Rx Cost =
SUM(vw_Prescriptions[TotalCost])

Total Patient Cost =
SUM(vw_Prescriptions[CostToPatient])

Total Payer Cost =
SUM(vw_Prescriptions[CostToPayer])

Avg Cost per Rx =
DIVIDE([Total Rx Cost], [Total Prescriptions], 0)

Patient Cost Share % =
DIVIDE([Total Patient Cost], [Total Rx Cost], 0) * 100

Payer Cost Share % =
DIVIDE([Total Payer Cost], [Total Rx Cost], 0) * 100
```

---

## Calculated Column — Age Band
*(Add to `vw_ClaimsSummary` table in Power BI)*

```dax
Age Band =
SWITCH(
    TRUE(),
    vw_ClaimsSummary[PatientAgeAtService] <= 18, "0–18",
    vw_ClaimsSummary[PatientAgeAtService] <= 35, "19–35",
    vw_ClaimsSummary[PatientAgeAtService] <= 50, "36–50",
    vw_ClaimsSummary[PatientAgeAtService] <= 65, "51–65",
    "65+"
)
```

> Add this as a **calculated column** (not a measure): right-click `vw_ClaimsSummary` in Fields pane → **New Column**.
