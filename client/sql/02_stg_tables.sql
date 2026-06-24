-- ============================================================
-- HealthcareADK : Staging Tables (stg schema)
-- Mirror the landing zone CSVs exactly — no business logic.
-- Extra columns: stg_load_id, stg_load_date, stg_source_file,
--                stg_status ('Pending' | 'Processed' | 'Error')
-- ============================================================
USE HealthcareADK;
GO

-- ------------------------------------------------------------
-- stg.Payers
-- ------------------------------------------------------------
IF OBJECT_ID('stg.Payers', 'U') IS NOT NULL DROP TABLE stg.Payers;
CREATE TABLE stg.Payers (
    stg_load_id       INT            IDENTITY(1,1) NOT NULL,
    stg_load_date     DATETIME       NOT NULL DEFAULT GETDATE(),
    stg_source_file   VARCHAR(200)   NOT NULL,
    stg_status        VARCHAR(20)    NOT NULL DEFAULT 'Pending',

    payer_id          VARCHAR(36)    NOT NULL,
    payer_name        VARCHAR(100)   NULL,
    payer_type        VARCHAR(20)    NULL,
    plan_name         VARCHAR(100)   NULL,
    plan_type         VARCHAR(10)    NULL,
    address           VARCHAR(200)   NULL,
    city              VARCHAR(100)   NULL,
    state             CHAR(2)        NULL,
    zip_code          VARCHAR(10)    NULL,
    phone             VARCHAR(20)    NULL,
    created_at        VARCHAR(30)    NULL,   -- loaded as string, cast during DW load

    CONSTRAINT PK_stg_Payers PRIMARY KEY (stg_load_id)
);
GO

-- ------------------------------------------------------------
-- stg.Facilities
-- ------------------------------------------------------------
IF OBJECT_ID('stg.Facilities', 'U') IS NOT NULL DROP TABLE stg.Facilities;
CREATE TABLE stg.Facilities (
    stg_load_id       INT            IDENTITY(1,1) NOT NULL,
    stg_load_date     DATETIME       NOT NULL DEFAULT GETDATE(),
    stg_source_file   VARCHAR(200)   NOT NULL,
    stg_status        VARCHAR(20)    NOT NULL DEFAULT 'Pending',

    facility_id       VARCHAR(36)    NOT NULL,
    facility_name     VARCHAR(200)   NULL,
    facility_type     VARCHAR(30)    NULL,
    npi               VARCHAR(10)    NULL,
    address           VARCHAR(200)   NULL,
    city              VARCHAR(100)   NULL,
    state             CHAR(2)        NULL,
    zip_code          VARCHAR(10)    NULL,
    phone             VARCHAR(20)    NULL,
    bed_count         VARCHAR(10)    NULL,
    created_at        VARCHAR(30)    NULL,

    CONSTRAINT PK_stg_Facilities PRIMARY KEY (stg_load_id)
);
GO

-- ------------------------------------------------------------
-- stg.Providers
-- ------------------------------------------------------------
IF OBJECT_ID('stg.Providers', 'U') IS NOT NULL DROP TABLE stg.Providers;
CREATE TABLE stg.Providers (
    stg_load_id       INT            IDENTITY(1,1) NOT NULL,
    stg_load_date     DATETIME       NOT NULL DEFAULT GETDATE(),
    stg_source_file   VARCHAR(200)   NOT NULL,
    stg_status        VARCHAR(20)    NOT NULL DEFAULT 'Pending',

    provider_id       VARCHAR(36)    NOT NULL,
    npi               VARCHAR(10)    NULL,
    first_name        VARCHAR(100)   NULL,
    last_name         VARCHAR(100)   NULL,
    specialty         VARCHAR(100)   NULL,
    license_number    VARCHAR(20)    NULL,
    facility_id       VARCHAR(36)    NULL,
    phone             VARCHAR(20)    NULL,
    email             VARCHAR(200)   NULL,
    years_experience  VARCHAR(5)     NULL,
    created_at        VARCHAR(30)    NULL,

    CONSTRAINT PK_stg_Providers PRIMARY KEY (stg_load_id)
);
GO

-- ------------------------------------------------------------
-- stg.Patients
-- ------------------------------------------------------------
IF OBJECT_ID('stg.Patients', 'U') IS NOT NULL DROP TABLE stg.Patients;
CREATE TABLE stg.Patients (
    stg_load_id          INT            IDENTITY(1,1) NOT NULL,
    stg_load_date        DATETIME       NOT NULL DEFAULT GETDATE(),
    stg_source_file      VARCHAR(200)   NOT NULL,
    stg_status           VARCHAR(20)    NOT NULL DEFAULT 'Pending',

    patient_id           VARCHAR(36)    NOT NULL,
    first_name           VARCHAR(100)   NULL,
    last_name            VARCHAR(100)   NULL,
    date_of_birth        VARCHAR(12)    NULL,
    gender               VARCHAR(10)    NULL,
    blood_type           VARCHAR(5)     NULL,
    address              VARCHAR(200)   NULL,
    city                 VARCHAR(100)   NULL,
    state                CHAR(2)        NULL,
    zip_code             VARCHAR(10)    NULL,
    phone                VARCHAR(20)    NULL,
    email                VARCHAR(200)   NULL,
    primary_payer_id     VARCHAR(36)    NULL,
    primary_provider_id  VARCHAR(36)    NULL,
    created_at           VARCHAR(30)    NULL,

    CONSTRAINT PK_stg_Patients PRIMARY KEY (stg_load_id)
);
GO

-- ------------------------------------------------------------
-- stg.Claims
-- ------------------------------------------------------------
IF OBJECT_ID('stg.Claims', 'U') IS NOT NULL DROP TABLE stg.Claims;
CREATE TABLE stg.Claims (
    stg_load_id       INT            IDENTITY(1,1) NOT NULL,
    stg_load_date     DATETIME       NOT NULL DEFAULT GETDATE(),
    stg_source_file   VARCHAR(200)   NOT NULL,
    stg_status        VARCHAR(20)    NOT NULL DEFAULT 'Pending',

    claim_id          VARCHAR(36)    NOT NULL,
    patient_id        VARCHAR(36)    NULL,
    provider_id       VARCHAR(36)    NULL,
    facility_id       VARCHAR(36)    NULL,
    payer_id          VARCHAR(36)    NULL,
    claim_date        VARCHAR(12)    NULL,
    service_date      VARCHAR(12)    NULL,
    icd10_primary     VARCHAR(10)    NULL,
    icd10_secondary   VARCHAR(10)    NULL,
    procedure_code    VARCHAR(10)    NULL,
    billed_amount     VARCHAR(15)    NULL,
    allowed_amount    VARCHAR(15)    NULL,
    paid_amount       VARCHAR(15)    NULL,
    claim_status      VARCHAR(20)    NULL,
    denial_reason     VARCHAR(200)   NULL,
    created_at        VARCHAR(30)    NULL,

    CONSTRAINT PK_stg_Claims PRIMARY KEY (stg_load_id)
);
GO

-- ------------------------------------------------------------
-- stg.Labs
-- ------------------------------------------------------------
IF OBJECT_ID('stg.Labs', 'U') IS NOT NULL DROP TABLE stg.Labs;
CREATE TABLE stg.Labs (
    stg_load_id            INT            IDENTITY(1,1) NOT NULL,
    stg_load_date          DATETIME       NOT NULL DEFAULT GETDATE(),
    stg_source_file        VARCHAR(200)   NOT NULL,
    stg_status             VARCHAR(20)    NOT NULL DEFAULT 'Pending',

    lab_id                 VARCHAR(36)    NOT NULL,
    patient_id             VARCHAR(36)    NULL,
    provider_id            VARCHAR(36)    NULL,
    facility_id            VARCHAR(36)    NULL,
    order_date             VARCHAR(12)    NULL,
    result_date            VARCHAR(12)    NULL,
    test_name              VARCHAR(100)   NULL,
    loinc_code             VARCHAR(20)    NULL,
    result_value           VARCHAR(20)    NULL,
    result_unit            VARCHAR(20)    NULL,
    reference_range_low    VARCHAR(20)    NULL,
    reference_range_high   VARCHAR(20)    NULL,
    abnormal_flag          VARCHAR(10)    NULL,
    created_at             VARCHAR(30)    NULL,

    CONSTRAINT PK_stg_Labs PRIMARY KEY (stg_load_id)
);
GO

-- ------------------------------------------------------------
-- stg.Prescriptions
-- ------------------------------------------------------------
IF OBJECT_ID('stg.Prescriptions', 'U') IS NOT NULL DROP TABLE stg.Prescriptions;
CREATE TABLE stg.Prescriptions (
    stg_load_id         INT            IDENTITY(1,1) NOT NULL,
    stg_load_date       DATETIME       NOT NULL DEFAULT GETDATE(),
    stg_source_file     VARCHAR(200)   NOT NULL,
    stg_status          VARCHAR(20)    NOT NULL DEFAULT 'Pending',

    prescription_id     VARCHAR(36)    NOT NULL,
    patient_id          VARCHAR(36)    NULL,
    provider_id         VARCHAR(36)    NULL,
    drug_name           VARCHAR(100)   NULL,
    ndc_code            VARCHAR(20)    NULL,
    dosage              VARCHAR(20)    NULL,
    frequency           VARCHAR(50)    NULL,
    days_supply         VARCHAR(5)     NULL,
    quantity            VARCHAR(10)    NULL,
    refills_authorized  VARCHAR(5)     NULL,
    refills_remaining   VARCHAR(5)     NULL,
    prescribed_date     VARCHAR(12)    NULL,
    fill_date           VARCHAR(12)    NULL,
    payer_id            VARCHAR(36)    NULL,
    cost_to_patient     VARCHAR(15)    NULL,
    cost_to_payer       VARCHAR(15)    NULL,
    created_at          VARCHAR(30)    NULL,

    CONSTRAINT PK_stg_Prescriptions PRIMARY KEY (stg_load_id)
);
GO

-- ------------------------------------------------------------
-- stg.Financials
-- ------------------------------------------------------------
IF OBJECT_ID('stg.Financials', 'U') IS NOT NULL DROP TABLE stg.Financials;
CREATE TABLE stg.Financials (
    stg_load_id        INT            IDENTITY(1,1) NOT NULL,
    stg_load_date      DATETIME       NOT NULL DEFAULT GETDATE(),
    stg_source_file    VARCHAR(200)   NOT NULL,
    stg_status         VARCHAR(20)    NOT NULL DEFAULT 'Pending',

    transaction_id     VARCHAR(36)    NOT NULL,
    transaction_date   VARCHAR(12)    NULL,
    transaction_type   VARCHAR(20)    NULL,
    department         VARCHAR(50)    NULL,
    facility_id        VARCHAR(36)    NULL,
    amount             VARCHAR(20)    NULL,
    fiscal_year        VARCHAR(5)     NULL,
    fiscal_quarter     VARCHAR(2)     NULL,
    cost_center        VARCHAR(20)    NULL,
    gl_account         VARCHAR(50)    NULL,
    description        VARCHAR(200)   NULL,
    created_at         VARCHAR(30)    NULL,

    CONSTRAINT PK_stg_Financials PRIMARY KEY (stg_load_id)
);
GO

PRINT 'Staging tables created: Payers, Facilities, Providers, Patients, Claims, Labs, Prescriptions, Financials';
GO
