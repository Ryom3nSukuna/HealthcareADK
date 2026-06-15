-- ============================================================
-- HealthcareADK : Dimension Tables (dw schema)
--
-- SCD policy:
--   DimPatient   : Type 2  (track address / payer changes)
--   DimProvider  : Type 1  (overwrite — specialty changes ok)
--   DimFacility  : Type 1
--   DimPayer     : Type 1
--   DimDiagnosis : Static reference (ICD-10)
--   DimProcedure : Static reference (CPT)
--   DimDrug      : Static reference (NDC)
-- ============================================================
USE HealthcareADK;
GO

-- ------------------------------------------------------------
-- dw.DimPayer  (Type 1 — overwrite)
-- ------------------------------------------------------------
IF OBJECT_ID('dw.DimPayer', 'U') IS NOT NULL DROP TABLE dw.DimPayer;
CREATE TABLE dw.DimPayer (
    PayerKey        INT           IDENTITY(1,1) NOT NULL,
    PayerID         VARCHAR(36)   NOT NULL,        -- source UUID
    PayerName       VARCHAR(100)  NOT NULL,
    PayerType       VARCHAR(20)   NOT NULL,        -- Commercial | Medicare | Medicaid | Self-Pay
    PlanName        VARCHAR(100)  NULL,
    PlanType        VARCHAR(10)   NULL,            -- HMO | PPO | EPO | POS
    Address         VARCHAR(200)  NULL,
    City            VARCHAR(100)  NULL,
    [State]         CHAR(2)       NULL,
    ZipCode         VARCHAR(10)   NULL,
    Phone           VARCHAR(20)   NULL,
    CreatedAt       DATETIME      NULL,
    DWUpdatedAt     DATETIME      NOT NULL DEFAULT GETDATE(),

    CONSTRAINT PK_dw_DimPayer PRIMARY KEY (PayerKey)
);
CREATE UNIQUE INDEX UX_DimPayer_PayerID ON dw.DimPayer (PayerID);
GO

-- Unknown sentinel
INSERT INTO dw.DimPayer (PayerID, PayerName, PayerType)
VALUES ('00000000-0000-0000-0000-000000000000', 'Unknown', 'Unknown');
GO

-- ------------------------------------------------------------
-- dw.DimFacility  (Type 1 — overwrite)
-- ------------------------------------------------------------
IF OBJECT_ID('dw.DimFacility', 'U') IS NOT NULL DROP TABLE dw.DimFacility;
CREATE TABLE dw.DimFacility (
    FacilityKey     INT           IDENTITY(1,1) NOT NULL,
    FacilityID      VARCHAR(36)   NOT NULL,
    FacilityName    VARCHAR(200)  NOT NULL,
    FacilityType    VARCHAR(30)   NOT NULL,   -- Hospital | Clinic | Laboratory | Pharmacy | Urgent Care
    NPI             VARCHAR(10)   NULL,
    Address         VARCHAR(200)  NULL,
    City            VARCHAR(100)  NULL,
    [State]         CHAR(2)       NULL,
    ZipCode         VARCHAR(10)   NULL,
    Phone           VARCHAR(20)   NULL,
    BedCount        SMALLINT      NULL DEFAULT 0,
    CreatedAt       DATETIME      NULL,
    DWUpdatedAt     DATETIME      NOT NULL DEFAULT GETDATE(),

    CONSTRAINT PK_dw_DimFacility PRIMARY KEY (FacilityKey)
);
CREATE UNIQUE INDEX UX_DimFacility_FacilityID ON dw.DimFacility (FacilityID);
GO

INSERT INTO dw.DimFacility (FacilityID, FacilityName, FacilityType)
VALUES ('00000000-0000-0000-0000-000000000000', 'Unknown', 'Unknown');
GO

-- ------------------------------------------------------------
-- dw.DimProvider  (Type 1 — overwrite)
-- ------------------------------------------------------------
IF OBJECT_ID('dw.DimProvider', 'U') IS NOT NULL DROP TABLE dw.DimProvider;
CREATE TABLE dw.DimProvider (
    ProviderKey         INT           IDENTITY(1,1) NOT NULL,
    ProviderID          VARCHAR(36)   NOT NULL,
    NPI                 VARCHAR(10)   NULL,
    FirstName           VARCHAR(100)  NULL,
    LastName            VARCHAR(100)  NULL,
    FullName            AS (ISNULL(FirstName,'') + ' ' + ISNULL(LastName,'')),
    Specialty           VARCHAR(100)  NULL,
    LicenseNumber       VARCHAR(20)   NULL,
    FacilityKey         INT           NULL,
    Phone               VARCHAR(20)   NULL,
    Email               VARCHAR(200)  NULL,
    YearsExperience     TINYINT       NULL,
    CreatedAt           DATETIME      NULL,
    DWUpdatedAt         DATETIME      NOT NULL DEFAULT GETDATE(),

    CONSTRAINT PK_dw_DimProvider PRIMARY KEY (ProviderKey),
    CONSTRAINT FK_DimProvider_Facility FOREIGN KEY (FacilityKey)
        REFERENCES dw.DimFacility (FacilityKey)
);
CREATE UNIQUE INDEX UX_DimProvider_ProviderID ON dw.DimProvider (ProviderID);
GO

INSERT INTO dw.DimProvider (ProviderID, FirstName, LastName, FacilityKey)
VALUES ('00000000-0000-0000-0000-000000000000', 'Unknown', 'Unknown', 1);
GO

-- ------------------------------------------------------------
-- dw.DimPatient  (Type 2 — track history)
-- ------------------------------------------------------------
IF OBJECT_ID('dw.DimPatient', 'U') IS NOT NULL DROP TABLE dw.DimPatient;
CREATE TABLE dw.DimPatient (
    PatientKey          INT           IDENTITY(1,1) NOT NULL,
    PatientID           VARCHAR(36)   NOT NULL,        -- source UUID (repeated across versions)
    FirstName           VARCHAR(100)  NULL,
    LastName            VARCHAR(100)  NULL,
    FullName            AS (ISNULL(FirstName,'') + ' ' + ISNULL(LastName,'')),
    DateOfBirth         DATE          NULL,
    Gender              VARCHAR(10)   NULL,
    BloodType           VARCHAR(5)    NULL,
    Address             VARCHAR(200)  NULL,
    City                VARCHAR(100)  NULL,
    [State]             CHAR(2)       NULL,
    ZipCode             VARCHAR(10)   NULL,
    Phone               VARCHAR(20)   NULL,
    Email               VARCHAR(200)  NULL,
    PrimaryPayerKey     INT           NULL,
    PrimaryProviderKey  INT           NULL,
    -- SCD Type 2 control columns
    EffectiveDate       DATE          NOT NULL DEFAULT CAST(GETDATE() AS DATE),
    ExpirationDate      DATE          NULL,            -- NULL = current record
    IsCurrent           BIT           NOT NULL DEFAULT 1,
    CreatedAt           DATETIME      NULL,
    DWUpdatedAt         DATETIME      NOT NULL DEFAULT GETDATE(),

    CONSTRAINT PK_dw_DimPatient PRIMARY KEY (PatientKey),
    CONSTRAINT FK_DimPatient_Payer    FOREIGN KEY (PrimaryPayerKey)    REFERENCES dw.DimPayer    (PayerKey),
    CONSTRAINT FK_DimPatient_Provider FOREIGN KEY (PrimaryProviderKey) REFERENCES dw.DimProvider (ProviderKey)
);
CREATE INDEX IX_DimPatient_PatientID ON dw.DimPatient (PatientID, IsCurrent);
GO

INSERT INTO dw.DimPatient (PatientID, FirstName, LastName, EffectiveDate, IsCurrent)
VALUES ('00000000-0000-0000-0000-000000000000', 'Unknown', 'Unknown', '1900-01-01', 1);
GO

-- ------------------------------------------------------------
-- dw.DimDiagnosis  (static ICD-10 reference)
-- ------------------------------------------------------------
IF OBJECT_ID('dw.DimDiagnosis', 'U') IS NOT NULL DROP TABLE dw.DimDiagnosis;
CREATE TABLE dw.DimDiagnosis (
    DiagnosisKey    INT          IDENTITY(1,1) NOT NULL,
    ICD10Code       VARCHAR(10)  NOT NULL,
    Description     VARCHAR(200) NULL,

    CONSTRAINT PK_dw_DimDiagnosis PRIMARY KEY (DiagnosisKey)
);
CREATE UNIQUE INDEX UX_DimDiagnosis_Code ON dw.DimDiagnosis (ICD10Code);
GO

INSERT INTO dw.DimDiagnosis (ICD10Code, Description) VALUES
    ('UNKNOWN', 'Unknown / Not Coded'),
    ('E11.9',   'Type 2 diabetes mellitus without complications'),
    ('I10',     'Essential (primary) hypertension'),
    ('J45.909', 'Unspecified asthma, uncomplicated'),
    ('M54.5',   'Low back pain'),
    ('F41.1',   'Generalized anxiety disorder'),
    ('K21.0',   'GERD with esophagitis'),
    ('E78.5',   'Hyperlipidemia, unspecified'),
    ('N39.0',   'Urinary tract infection'),
    ('J06.9',   'Acute upper respiratory infection'),
    ('Z00.00',  'General adult medical exam without abnormal findings'),
    ('I25.10',  'Atherosclerotic heart disease, unspecified'),
    ('F32.9',   'Major depressive disorder, single episode'),
    ('J18.9',   'Pneumonia, unspecified organism'),
    ('K92.1',   'Melena'),
    ('R51',     'Headache');
GO

-- ------------------------------------------------------------
-- dw.DimProcedure  (static CPT reference)
-- ------------------------------------------------------------
IF OBJECT_ID('dw.DimProcedure', 'U') IS NOT NULL DROP TABLE dw.DimProcedure;
CREATE TABLE dw.DimProcedure (
    ProcedureKey    INT            IDENTITY(1,1) NOT NULL,
    CPTCode         VARCHAR(10)    NOT NULL,
    Description     VARCHAR(200)   NULL,
    BasePrice       DECIMAL(10,2)  NULL,

    CONSTRAINT PK_dw_DimProcedure PRIMARY KEY (ProcedureKey)
);
CREATE UNIQUE INDEX UX_DimProcedure_Code ON dw.DimProcedure (CPTCode);
GO

INSERT INTO dw.DimProcedure (CPTCode, Description, BasePrice) VALUES
    ('UNKNOWN', 'Unknown / Not Coded',                                          0.00),
    ('99213',   'Office visit, established patient, low-moderate complexity',  150.00),
    ('99214',   'Office visit, established patient, moderate-high complexity', 250.00),
    ('99215',   'Office visit, established patient, high complexity',          350.00),
    ('99203',   'Office visit, new patient, moderate complexity',              200.00),
    ('99204',   'Office visit, new patient, moderate-high complexity',         300.00),
    ('93000',   'Electrocardiogram (ECG/EKG)',                                  75.00),
    ('80053',   'Comprehensive metabolic panel',                                85.00),
    ('85025',   'Complete blood count (CBC)',                                   60.00),
    ('71046',   'Chest X-ray, 2 views',                                        120.00),
    ('99285',   'Emergency department visit, high complexity',                 650.00);
GO

-- ------------------------------------------------------------
-- dw.DimDrug  (static NDC reference)
-- ------------------------------------------------------------
IF OBJECT_ID('dw.DimDrug', 'U') IS NOT NULL DROP TABLE dw.DimDrug;
CREATE TABLE dw.DimDrug (
    DrugKey         INT           IDENTITY(1,1) NOT NULL,
    DrugName        VARCHAR(100)  NOT NULL,
    NDCCode         VARCHAR(20)   NOT NULL,
    Dosage          VARCHAR(20)   NULL,
    Frequency       VARCHAR(50)   NULL,

    CONSTRAINT PK_dw_DimDrug PRIMARY KEY (DrugKey)
);
CREATE UNIQUE INDEX UX_DimDrug_NDC ON dw.DimDrug (NDCCode);
GO

INSERT INTO dw.DimDrug (DrugName, NDCCode, Dosage, Frequency) VALUES
    ('Unknown',       'UNKNOWN',          NULL,    NULL),
    ('Metformin',     '00093-1048-01',    '500mg', 'Twice daily'),
    ('Lisinopril',    '00093-1046-01',    '10mg',  'Once daily'),
    ('Atorvastatin',  '00069-0155-30',    '20mg',  'Once daily at bedtime'),
    ('Amlodipine',    '00069-1540-30',    '5mg',   'Once daily'),
    ('Omeprazole',    '00093-7366-56',    '20mg',  'Once daily before meal'),
    ('Levothyroxine', '00074-4137-13',    '50mcg', 'Once daily'),
    ('Sertraline',    '00049-4900-66',    '50mg',  'Once daily'),
    ('Albuterol',     '00173-0682-20',    '90mcg', 'Every 4-6 hours as needed'),
    ('Gabapentin',    '00093-0636-56',    '300mg', 'Three times daily'),
    ('Amoxicillin',   '00093-4159-01',    '500mg', 'Every 8 hours');
GO

PRINT 'Dimension tables created: DimPayer, DimFacility, DimProvider, DimPatient, DimDiagnosis, DimProcedure, DimDrug';
GO
