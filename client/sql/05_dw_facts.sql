-- ============================================================
-- HealthcareADK : Fact Tables (dw schema)
--
-- Grain:
--   FactClaims        — one row per insurance claim
--   FactLabResults    — one row per lab test result
--   FactPrescriptions — one row per prescription fill
--   FactFinancials    — one row per financial transaction
--
-- All date FKs reference dw.DimDate (DateKey INT = YYYYMMDD).
-- FK violations resolve to sentinel key 0 ('Unknown' date)
-- or sentinel key 1 ('Unknown' dimension record).
-- ============================================================
USE HealthcareADK;
GO

-- ------------------------------------------------------------
-- dw.FactClaims
-- ------------------------------------------------------------
IF OBJECT_ID('dw.FactClaims', 'U') IS NOT NULL DROP TABLE dw.FactClaims;
CREATE TABLE dw.FactClaims (
    ClaimKey            INT             IDENTITY(1,1) NOT NULL,
    ClaimID             VARCHAR(36)     NOT NULL,         -- source UUID (natural key)
    -- Dimension FKs
    PatientKey          INT             NOT NULL DEFAULT 1,
    ProviderKey         INT             NOT NULL DEFAULT 1,
    FacilityKey         INT             NOT NULL DEFAULT 1,
    PayerKey            INT             NOT NULL DEFAULT 1,
    ServiceDateKey      INT             NOT NULL DEFAULT 0,
    ClaimDateKey        INT             NOT NULL DEFAULT 0,
    DiagnosisKey        INT             NOT NULL DEFAULT 1,
    ProcedureKey        INT             NOT NULL DEFAULT 1,
    -- Measures
    BilledAmount        DECIMAL(10,2)   NOT NULL DEFAULT 0,
    AllowedAmount       DECIMAL(10,2)   NOT NULL DEFAULT 0,
    PaidAmount          DECIMAL(10,2)   NOT NULL DEFAULT 0,
    WriteOffAmount      AS (AllowedAmount - PaidAmount),  -- computed
    -- Descriptive attributes (low-cardinality, ok to denormalise)
    ClaimStatus         VARCHAR(20)     NULL,
    DenialReason        VARCHAR(200)    NULL,
    CreatedAt           DATETIME        NULL,
    DWLoadedAt          DATETIME        NOT NULL DEFAULT GETDATE(),

    CONSTRAINT PK_dw_FactClaims      PRIMARY KEY (ClaimKey),
    CONSTRAINT FK_FC_Patient         FOREIGN KEY (PatientKey)     REFERENCES dw.DimPatient   (PatientKey),
    CONSTRAINT FK_FC_Provider        FOREIGN KEY (ProviderKey)    REFERENCES dw.DimProvider  (ProviderKey),
    CONSTRAINT FK_FC_Facility        FOREIGN KEY (FacilityKey)    REFERENCES dw.DimFacility  (FacilityKey),
    CONSTRAINT FK_FC_Payer           FOREIGN KEY (PayerKey)       REFERENCES dw.DimPayer     (PayerKey),
    CONSTRAINT FK_FC_ServiceDate     FOREIGN KEY (ServiceDateKey) REFERENCES dw.DimDate      (DateKey),
    CONSTRAINT FK_FC_ClaimDate       FOREIGN KEY (ClaimDateKey)   REFERENCES dw.DimDate      (DateKey),
    CONSTRAINT FK_FC_Diagnosis       FOREIGN KEY (DiagnosisKey)   REFERENCES dw.DimDiagnosis (DiagnosisKey),
    CONSTRAINT FK_FC_Procedure       FOREIGN KEY (ProcedureKey)   REFERENCES dw.DimProcedure (ProcedureKey)
);
CREATE UNIQUE INDEX UX_FactClaims_ClaimID  ON dw.FactClaims (ClaimID);
CREATE        INDEX IX_FactClaims_Patient  ON dw.FactClaims (PatientKey);
CREATE        INDEX IX_FactClaims_Service  ON dw.FactClaims (ServiceDateKey);
CREATE        INDEX IX_FactClaims_Status   ON dw.FactClaims (ClaimStatus);
GO

-- ------------------------------------------------------------
-- dw.FactLabResults
-- ------------------------------------------------------------
IF OBJECT_ID('dw.FactLabResults', 'U') IS NOT NULL DROP TABLE dw.FactLabResults;
CREATE TABLE dw.FactLabResults (
    LabKey              INT             IDENTITY(1,1) NOT NULL,
    LabID               VARCHAR(36)     NOT NULL,
    -- Dimension FKs
    PatientKey          INT             NOT NULL DEFAULT 1,
    ProviderKey         INT             NOT NULL DEFAULT 1,
    FacilityKey         INT             NOT NULL DEFAULT 1,
    OrderDateKey        INT             NOT NULL DEFAULT 0,
    ResultDateKey       INT             NOT NULL DEFAULT 0,
    -- Descriptive (low-cardinality, denormalised for query speed)
    TestName            VARCHAR(100)    NULL,
    LOINCCode           VARCHAR(20)     NULL,
    AbnormalFlag        VARCHAR(10)     NULL,   -- Normal | High | Low | Critical
    -- Measures
    ResultValue         DECIMAL(10,3)   NULL,
    ResultUnit          VARCHAR(20)     NULL,
    ReferenceRangeLow   DECIMAL(10,3)   NULL,
    ReferenceRangeHigh  DECIMAL(10,3)   NULL,
    DeviationFromMid    AS (                    -- computed: how far from midpoint
        CASE
            WHEN ReferenceRangeLow IS NOT NULL AND ReferenceRangeHigh IS NOT NULL
            THEN ResultValue - ((ReferenceRangeLow + ReferenceRangeHigh) / 2.0)
            ELSE NULL
        END
    ),
    CreatedAt           DATETIME        NULL,
    DWLoadedAt          DATETIME        NOT NULL DEFAULT GETDATE(),

    CONSTRAINT PK_dw_FactLabResults   PRIMARY KEY (LabKey),
    CONSTRAINT FK_FL_Patient          FOREIGN KEY (PatientKey)   REFERENCES dw.DimPatient  (PatientKey),
    CONSTRAINT FK_FL_Provider         FOREIGN KEY (ProviderKey)  REFERENCES dw.DimProvider (ProviderKey),
    CONSTRAINT FK_FL_Facility         FOREIGN KEY (FacilityKey)  REFERENCES dw.DimFacility (FacilityKey),
    CONSTRAINT FK_FL_OrderDate        FOREIGN KEY (OrderDateKey) REFERENCES dw.DimDate     (DateKey),
    CONSTRAINT FK_FL_ResultDate       FOREIGN KEY (ResultDateKey)REFERENCES dw.DimDate     (DateKey)
);
CREATE UNIQUE INDEX UX_FactLabResults_LabID    ON dw.FactLabResults (LabID);
CREATE        INDEX IX_FactLabResults_Patient  ON dw.FactLabResults (PatientKey);
CREATE        INDEX IX_FactLabResults_LOINC    ON dw.FactLabResults (LOINCCode);
CREATE        INDEX IX_FactLabResults_Flag     ON dw.FactLabResults (AbnormalFlag);
GO

-- ------------------------------------------------------------
-- dw.FactPrescriptions
-- ------------------------------------------------------------
IF OBJECT_ID('dw.FactPrescriptions', 'U') IS NOT NULL DROP TABLE dw.FactPrescriptions;
CREATE TABLE dw.FactPrescriptions (
    PrescriptionKey     INT             IDENTITY(1,1) NOT NULL,
    PrescriptionID      VARCHAR(36)     NOT NULL,
    -- Dimension FKs
    PatientKey          INT             NOT NULL DEFAULT 1,
    ProviderKey         INT             NOT NULL DEFAULT 1,
    PayerKey            INT             NOT NULL DEFAULT 1,
    DrugKey             INT             NOT NULL DEFAULT 1,
    PrescribedDateKey   INT             NOT NULL DEFAULT 0,
    FillDateKey         INT             NOT NULL DEFAULT 0,
    -- Measures
    DaysSupply          SMALLINT        NULL,
    Quantity            SMALLINT        NULL,
    RefillsAuthorized   TINYINT         NULL,
    RefillsRemaining    TINYINT         NULL,
    CostToPatient       DECIMAL(10,2)   NULL,
    CostToPayer         DECIMAL(10,2)   NULL,
    TotalCost           AS (ISNULL(CostToPatient,0) + ISNULL(CostToPayer,0)),
    CreatedAt           DATETIME        NULL,
    DWLoadedAt          DATETIME        NOT NULL DEFAULT GETDATE(),

    CONSTRAINT PK_dw_FactPrescriptions PRIMARY KEY (PrescriptionKey),
    CONSTRAINT FK_FP_Patient           FOREIGN KEY (PatientKey)        REFERENCES dw.DimPatient  (PatientKey),
    CONSTRAINT FK_FP_Provider          FOREIGN KEY (ProviderKey)       REFERENCES dw.DimProvider (ProviderKey),
    CONSTRAINT FK_FP_Payer             FOREIGN KEY (PayerKey)          REFERENCES dw.DimPayer    (PayerKey),
    CONSTRAINT FK_FP_Drug              FOREIGN KEY (DrugKey)           REFERENCES dw.DimDrug     (DrugKey),
    CONSTRAINT FK_FP_PrescribedDate    FOREIGN KEY (PrescribedDateKey) REFERENCES dw.DimDate     (DateKey),
    CONSTRAINT FK_FP_FillDate          FOREIGN KEY (FillDateKey)       REFERENCES dw.DimDate     (DateKey)
);
CREATE UNIQUE INDEX UX_FactPrescriptions_ID     ON dw.FactPrescriptions (PrescriptionID);
CREATE        INDEX IX_FactPrescriptions_Patient ON dw.FactPrescriptions (PatientKey);
CREATE        INDEX IX_FactPrescriptions_Drug    ON dw.FactPrescriptions (DrugKey);
GO

-- ------------------------------------------------------------
-- dw.FactFinancials
-- ------------------------------------------------------------
IF OBJECT_ID('dw.FactFinancials', 'U') IS NOT NULL DROP TABLE dw.FactFinancials;
CREATE TABLE dw.FactFinancials (
    FinancialKey        INT             IDENTITY(1,1) NOT NULL,
    TransactionID       VARCHAR(36)     NOT NULL,
    -- Dimension FKs
    TransactionDateKey  INT             NOT NULL DEFAULT 0,
    FacilityKey         INT             NOT NULL DEFAULT 1,
    -- Descriptive
    TransactionType     VARCHAR(20)     NULL,   -- Revenue | Expense | Reimbursement | Write-off
    Department          VARCHAR(50)     NULL,
    CostCenter          VARCHAR(20)     NULL,
    GLAccount           VARCHAR(50)     NULL,
    Description         VARCHAR(200)    NULL,
    -- Measures
    Amount              DECIMAL(15,2)   NOT NULL DEFAULT 0,
    FiscalYear          SMALLINT        NULL,
    FiscalQuarter       TINYINT         NULL,
    CreatedAt           DATETIME        NULL,
    DWLoadedAt          DATETIME        NOT NULL DEFAULT GETDATE(),

    CONSTRAINT PK_dw_FactFinancials    PRIMARY KEY (FinancialKey),
    CONSTRAINT FK_FF_Date              FOREIGN KEY (TransactionDateKey) REFERENCES dw.DimDate    (DateKey),
    CONSTRAINT FK_FF_Facility          FOREIGN KEY (FacilityKey)        REFERENCES dw.DimFacility(FacilityKey)
);
CREATE UNIQUE INDEX UX_FactFinancials_TxID        ON dw.FactFinancials (TransactionID);
CREATE        INDEX IX_FactFinancials_Date         ON dw.FactFinancials (TransactionDateKey);
CREATE        INDEX IX_FactFinancials_Type         ON dw.FactFinancials (TransactionType);
CREATE        INDEX IX_FactFinancials_FiscalYear   ON dw.FactFinancials (FiscalYear, FiscalQuarter);
GO

PRINT 'Fact tables created: FactClaims, FactLabResults, FactPrescriptions, FactFinancials';
GO
