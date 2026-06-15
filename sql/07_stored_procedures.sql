-- ============================================================
-- HealthcareADK : Stored Procedures
--
-- usp_GetClaimsSummary        — claims with filters (agent-safe)
-- usp_GetFinancialYoY         — YoY revenue vs expense comparison
-- usp_GetProviderPerformance  — provider KPIs for a given period
-- usp_GetAbnormalLabResults   — abnormal/critical labs for a patient
-- usp_GetPatientTimeline      — full care timeline for one patient
-- ============================================================
USE HealthcareADK;
GO

-- ------------------------------------------------------------
-- usp_GetClaimsSummary
-- Filters: date range, payer type, claim status, state
-- Used by: ClaimsAgent, ReportingAgent
-- ------------------------------------------------------------
CREATE OR ALTER PROCEDURE dw.usp_GetClaimsSummary
    @StartDate      DATE         = NULL,
    @EndDate        DATE         = NULL,
    @PayerType      VARCHAR(20)  = NULL,   -- Commercial | Medicare | Medicaid | Self-Pay | NULL=all
    @ClaimStatus    VARCHAR(20)  = NULL,   -- Approved | Denied | Pending | Appealed | NULL=all
    @State          CHAR(2)      = NULL,
    @TopN           INT          = 100
AS
BEGIN
    SET NOCOUNT ON;

    SELECT TOP (@TopN)
        ClaimID,
        ClaimStatus,
        DenialReason,
        BilledAmount,
        AllowedAmount,
        PaidAmount,
        WriteOffAmount,
        ServiceDate,
        ServiceYear,
        ServiceMonth,
        PatientName,
        PatientAgeAtService,
        PatientState,
        ProviderName,
        ProviderSpecialty,
        FacilityName,
        PayerName,
        PayerType,
        ICD10Code,
        DiagnosisDescription,
        CPTCode,
        ProcedureDescription
    FROM rpt.vw_ClaimsSummary
    WHERE
        (@StartDate  IS NULL OR ServiceDate >= @StartDate)
    AND (@EndDate    IS NULL OR ServiceDate <= @EndDate)
    AND (@PayerType  IS NULL OR PayerType   = @PayerType)
    AND (@ClaimStatus IS NULL OR ClaimStatus = @ClaimStatus)
    AND (@State      IS NULL OR PatientState = @State)
    ORDER BY ServiceDate DESC;
END;
GO

-- ------------------------------------------------------------
-- usp_GetFinancialYoY
-- Returns revenue, expense, reimbursement, write-off by year/quarter.
-- Used by: FinancialAgent, ReportingAgent
-- ------------------------------------------------------------
CREATE OR ALTER PROCEDURE dw.usp_GetFinancialYoY
    @StartYear  SMALLINT = NULL,
    @EndYear    SMALLINT = NULL,
    @FacilityID VARCHAR(36) = NULL   -- NULL = all facilities
AS
BEGIN
    SET NOCOUNT ON;

    SELECT
        ff.FiscalYear,
        ff.FiscalQuarter,
        ff.TransactionType,
        fac.FacilityName,
        fac.[State]                             AS FacilityState,
        SUM(ff.Amount)                          AS TotalAmount,
        COUNT(*)                                AS TransactionCount,
        AVG(ff.Amount)                          AS AvgTransactionAmount
    FROM dw.FactFinancials  ff
    JOIN dw.DimFacility     fac ON fac.FacilityKey = ff.FacilityKey
    WHERE
        (@StartYear  IS NULL OR ff.FiscalYear >= @StartYear)
    AND (@EndYear    IS NULL OR ff.FiscalYear <= @EndYear)
    AND (@FacilityID IS NULL OR fac.FacilityID = @FacilityID)
    GROUP BY
        ff.FiscalYear, ff.FiscalQuarter, ff.TransactionType,
        fac.FacilityName, fac.[State]
    ORDER BY
        ff.FiscalYear, ff.FiscalQuarter, ff.TransactionType;
END;
GO

-- ------------------------------------------------------------
-- usp_GetProviderPerformance
-- Provider claim KPIs for a given year / specialty.
-- Used by: ProviderAgent, ReportingAgent
-- ------------------------------------------------------------
CREATE OR ALTER PROCEDURE dw.usp_GetProviderPerformance
    @Year       SMALLINT    = NULL,
    @Specialty  VARCHAR(100)= NULL,
    @State      CHAR(2)     = NULL,
    @TopN       INT         = 50
AS
BEGIN
    SET NOCOUNT ON;

    SELECT TOP (@TopN)
        ProviderName,
        Specialty,
        FacilityName,
        FacilityState,
        ServiceYear,
        ServiceQuarter,
        TotalClaims,
        TotalBilled,
        TotalPaid,
        AvgClaimValue,
        DeniedClaims,
        ApprovedClaims,
        DenialRatePct
    FROM rpt.vw_ProviderPerformance
    WHERE
        (@Year      IS NULL OR ServiceYear    = @Year)
    AND (@Specialty IS NULL OR Specialty      = @Specialty)
    AND (@State     IS NULL OR FacilityState  = @State)
    ORDER BY TotalBilled DESC;
END;
GO

-- ------------------------------------------------------------
-- usp_GetAbnormalLabResults
-- Returns abnormal or critical lab results for a patient or period.
-- Used by: ClinicalAgent
-- ------------------------------------------------------------
CREATE OR ALTER PROCEDURE dw.usp_GetAbnormalLabResults
    @PatientID  VARCHAR(36) = NULL,   -- NULL = all patients
    @StartDate  DATE        = NULL,
    @EndDate    DATE        = NULL,
    @FlagFilter VARCHAR(10) = NULL,   -- High | Low | Critical | NULL=all abnormal
    @TopN       INT         = 200
AS
BEGIN
    SET NOCOUNT ON;

    SELECT TOP (@TopN)
        LabID,
        PatientID,
        PatientName,
        PatientAge,
        Gender,
        TestName,
        LOINCCode,
        ResultValue,
        ResultUnit,
        ReferenceRangeLow,
        ReferenceRangeHigh,
        AbnormalFlag,
        DeviationFromMid,
        ResultDate,
        ProviderName,
        FacilityName
    FROM rpt.vw_LabResults
    WHERE AbnormalFlag <> 'Normal'
    AND (@PatientID  IS NULL OR PatientID   = @PatientID)
    AND (@StartDate  IS NULL OR ResultDate >= @StartDate)
    AND (@EndDate    IS NULL OR ResultDate <= @EndDate)
    AND (@FlagFilter IS NULL OR AbnormalFlag = @FlagFilter)
    ORDER BY ResultDate DESC;
END;
GO

-- ------------------------------------------------------------
-- usp_GetPatientTimeline
-- Full care timeline for one patient: claims + labs + prescriptions.
-- Used by: ClinicalAgent, OrchestratorAgent
-- ------------------------------------------------------------
CREATE OR ALTER PROCEDURE dw.usp_GetPatientTimeline
    @PatientID  VARCHAR(36),
    @StartDate  DATE = NULL,
    @EndDate    DATE = NULL
AS
BEGIN
    SET NOCOUNT ON;

    -- Claims
    SELECT
        'Claim'             AS EventType,
        CAST(ServiceDate AS VARCHAR(12)) AS EventDate,
        ClaimStatus         AS Status,
        DiagnosisDescription AS Detail,
        BilledAmount        AS Amount,
        ProviderName,
        FacilityName
    FROM rpt.vw_ClaimsSummary
    WHERE PatientID = @PatientID
    AND   (@StartDate IS NULL OR ServiceDate >= @StartDate)
    AND   (@EndDate   IS NULL OR ServiceDate <= @EndDate)

    UNION ALL

    -- Lab Results
    SELECT
        'Lab'               AS EventType,
        CAST(ResultDate AS VARCHAR(12)) AS EventDate,
        AbnormalFlag        AS Status,
        TestName + ' = ' + CAST(ResultValue AS VARCHAR(20)) + ' ' + ResultUnit AS Detail,
        NULL                AS Amount,
        ProviderName,
        FacilityName
    FROM rpt.vw_LabResults
    WHERE PatientID = @PatientID
    AND   (@StartDate IS NULL OR ResultDate >= @StartDate)
    AND   (@EndDate   IS NULL OR ResultDate <= @EndDate)

    UNION ALL

    -- Prescriptions
    SELECT
        'Prescription'      AS EventType,
        CAST(FillDate AS VARCHAR(12)) AS EventDate,
        'Filled'            AS Status,
        DrugName + ' ' + Dosage + ' — ' + Frequency AS Detail,
        TotalCost           AS Amount,
        ProviderName,
        NULL                AS FacilityName
    FROM rpt.vw_Prescriptions
    WHERE PatientID = @PatientID
    AND   (@StartDate IS NULL OR FillDate >= @StartDate)
    AND   (@EndDate   IS NULL OR FillDate <= @EndDate)

    ORDER BY EventDate DESC;
END;
GO

PRINT 'Stored procedures created: usp_GetClaimsSummary, usp_GetFinancialYoY, usp_GetProviderPerformance, usp_GetAbnormalLabResults, usp_GetPatientTimeline';
GO
