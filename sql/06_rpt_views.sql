-- ============================================================
-- HealthcareADK : Reporting Views (rpt schema)
-- Power BI connects to these views — never directly to dw facts.
-- All views are read-only and pre-join dimensions for ease of use.
-- ============================================================
USE HealthcareADK;
GO

-- ------------------------------------------------------------
-- rpt.vw_ClaimsSummary
-- One row per claim with all dimension attributes resolved.
-- ------------------------------------------------------------
CREATE OR ALTER VIEW rpt.vw_ClaimsSummary AS
SELECT
    fc.ClaimID,
    fc.ClaimStatus,
    fc.DenialReason,
    fc.BilledAmount,
    fc.AllowedAmount,
    fc.PaidAmount,
    fc.WriteOffAmount,

    -- Service date
    sd.FullDate        AS ServiceDate,
    sd.[Year]          AS ServiceYear,
    sd.Quarter         AS ServiceQuarter,
    sd.MonthName       AS ServiceMonth,
    sd.MonthNumber     AS ServiceMonthNum,

    -- Claim date
    cd.FullDate        AS ClaimDate,

    -- Patient
    pat.PatientID,
    pat.FullName       AS PatientName,
    pat.Gender,
    pat.DateOfBirth,
    DATEDIFF(YEAR, pat.DateOfBirth, sd.FullDate) AS PatientAgeAtService,
    pat.[State]        AS PatientState,

    -- Provider
    prv.ProviderID,
    prv.FullName       AS ProviderName,
    prv.Specialty      AS ProviderSpecialty,

    -- Facility
    fac.FacilityName,
    fac.FacilityType,
    fac.[State]        AS FacilityState,

    -- Payer
    pay.PayerName,
    pay.PayerType,
    pay.PlanType,

    -- Diagnosis
    dx.ICD10Code,
    dx.Description     AS DiagnosisDescription,

    -- Procedure
    px.CPTCode,
    px.Description     AS ProcedureDescription,
    px.BasePrice       AS ProcedureBasePrice

FROM dw.FactClaims          fc
JOIN dw.DimDate             sd  ON sd.DateKey    = fc.ServiceDateKey
JOIN dw.DimDate             cd  ON cd.DateKey    = fc.ClaimDateKey
JOIN dw.DimPatient          pat ON pat.PatientKey = fc.PatientKey   AND pat.IsCurrent = 1
JOIN dw.DimProvider         prv ON prv.ProviderKey= fc.ProviderKey
JOIN dw.DimFacility         fac ON fac.FacilityKey= fc.FacilityKey
JOIN dw.DimPayer            pay ON pay.PayerKey   = fc.PayerKey
JOIN dw.DimDiagnosis        dx  ON dx.DiagnosisKey = fc.DiagnosisKey
JOIN dw.DimProcedure        px  ON px.ProcedureKey = fc.ProcedureKey;
GO

-- ------------------------------------------------------------
-- rpt.vw_FinancialKPIs
-- Aggregated financials by facility / year / quarter / type.
-- Used for YoY charts and KPI cards in Power BI.
-- ------------------------------------------------------------
CREATE OR ALTER VIEW rpt.vw_FinancialKPIs AS
SELECT
    fac.FacilityName,
    fac.FacilityType,
    fac.[State]        AS FacilityState,
    ff.TransactionType,
    ff.Department,
    ff.GLAccount,
    ff.FiscalYear,
    ff.FiscalQuarter,
    dt.MonthName,
    dt.MonthNumber,
    dt.FullDate        AS TransactionDate,
    ff.Amount,
    ff.CostCenter
FROM dw.FactFinancials ff
JOIN dw.DimFacility    fac ON fac.FacilityKey        = ff.FacilityKey
JOIN dw.DimDate        dt  ON dt.DateKey             = ff.TransactionDateKey;
GO

-- ------------------------------------------------------------
-- rpt.vw_LabResults
-- Lab results with patient context and abnormal flagging.
-- ------------------------------------------------------------
CREATE OR ALTER VIEW rpt.vw_LabResults AS
SELECT
    fl.LabID,
    fl.TestName,
    fl.LOINCCode,
    fl.ResultValue,
    fl.ResultUnit,
    fl.ReferenceRangeLow,
    fl.ReferenceRangeHigh,
    fl.AbnormalFlag,
    fl.DeviationFromMid,

    -- Dates
    od.FullDate        AS OrderDate,
    od.[Year]          AS OrderYear,
    od.Quarter         AS OrderQuarter,
    rd.FullDate        AS ResultDate,

    -- Patient
    pat.PatientID,
    pat.FullName       AS PatientName,
    pat.Gender,
    DATEDIFF(YEAR, pat.DateOfBirth, od.FullDate) AS PatientAge,
    pat.[State]        AS PatientState,

    -- Provider
    prv.FullName       AS ProviderName,
    prv.Specialty,

    -- Facility
    fac.FacilityName,
    fac.FacilityType

FROM dw.FactLabResults      fl
JOIN dw.DimDate             od  ON od.DateKey    = fl.OrderDateKey
JOIN dw.DimDate             rd  ON rd.DateKey    = fl.ResultDateKey
JOIN dw.DimPatient          pat ON pat.PatientKey = fl.PatientKey  AND pat.IsCurrent = 1
JOIN dw.DimProvider         prv ON prv.ProviderKey= fl.ProviderKey
JOIN dw.DimFacility         fac ON fac.FacilityKey= fl.FacilityKey;
GO

-- ------------------------------------------------------------
-- rpt.vw_Prescriptions
-- Prescription fills with cost breakdown and drug detail.
-- ------------------------------------------------------------
CREATE OR ALTER VIEW rpt.vw_Prescriptions AS
SELECT
    fp.PrescriptionID,
    fp.DaysSupply,
    fp.Quantity,
    fp.RefillsAuthorized,
    fp.RefillsRemaining,
    fp.CostToPatient,
    fp.CostToPayer,
    fp.TotalCost,

    -- Dates
    pd.FullDate        AS PrescribedDate,
    pd.[Year]          AS PrescribedYear,
    pd.Quarter         AS PrescribedQuarter,
    fd.FullDate        AS FillDate,

    -- Drug
    drg.DrugName,
    drg.NDCCode,
    drg.Dosage,
    drg.Frequency,

    -- Patient
    pat.PatientID,
    pat.FullName       AS PatientName,
    pat.Gender,
    pat.[State]        AS PatientState,

    -- Provider
    prv.FullName       AS ProviderName,
    prv.Specialty,

    -- Payer
    pay.PayerName,
    pay.PayerType,
    pay.PlanType

FROM dw.FactPrescriptions   fp
JOIN dw.DimDate             pd  ON pd.DateKey    = fp.PrescribedDateKey
JOIN dw.DimDate             fd  ON fd.DateKey    = fp.FillDateKey
JOIN dw.DimDrug             drg ON drg.DrugKey   = fp.DrugKey
JOIN dw.DimPatient          pat ON pat.PatientKey = fp.PatientKey  AND pat.IsCurrent = 1
JOIN dw.DimProvider         prv ON prv.ProviderKey= fp.ProviderKey
JOIN dw.DimPayer            pay ON pay.PayerKey   = fp.PayerKey;
GO

-- ------------------------------------------------------------
-- rpt.vw_ProviderPerformance
-- Aggregated claim metrics per provider — used for leaderboards.
-- ------------------------------------------------------------
CREATE OR ALTER VIEW rpt.vw_ProviderPerformance AS
SELECT
    prv.ProviderID,
    prv.FullName           AS ProviderName,
    prv.Specialty,
    prv.YearsExperience,
    fac.FacilityName,
    fac.[State]            AS FacilityState,
    sd.[Year]              AS ServiceYear,
    sd.Quarter             AS ServiceQuarter,
    COUNT(fc.ClaimKey)              AS TotalClaims,
    SUM(fc.BilledAmount)            AS TotalBilled,
    SUM(fc.PaidAmount)              AS TotalPaid,
    AVG(fc.BilledAmount)            AS AvgClaimValue,
    SUM(CASE WHEN fc.ClaimStatus = 'Denied'  THEN 1 ELSE 0 END) AS DeniedClaims,
    SUM(CASE WHEN fc.ClaimStatus = 'Approved'THEN 1 ELSE 0 END) AS ApprovedClaims,
    CAST(
        SUM(CASE WHEN fc.ClaimStatus = 'Denied' THEN 1.0 ELSE 0 END)
        / NULLIF(COUNT(fc.ClaimKey), 0) * 100
    AS DECIMAL(5,2))                AS DenialRatePct
FROM dw.FactClaims      fc
JOIN dw.DimProvider     prv ON prv.ProviderKey = fc.ProviderKey
JOIN dw.DimFacility     fac ON fac.FacilityKey = fc.FacilityKey
JOIN dw.DimDate         sd  ON sd.DateKey      = fc.ServiceDateKey
GROUP BY
    prv.ProviderID, prv.FullName, prv.Specialty, prv.YearsExperience,
    fac.FacilityName, fac.[State],
    sd.[Year], sd.Quarter;
GO

PRINT 'Reporting views created: vw_ClaimsSummary, vw_FinancialKPIs, vw_LabResults, vw_Prescriptions, vw_ProviderPerformance';
GO
