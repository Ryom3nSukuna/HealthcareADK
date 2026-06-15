-- ============================================================
-- HealthcareADK : ETL Stored Procedures  stg -> dw
--
-- Called by SSIS Package 2 "Load_DW" via Execute SQL Tasks.
-- Run order:
--   1. usp_ETL_LoadDimPayer
--   2. usp_ETL_LoadDimFacility
--   3. usp_ETL_LoadDimProvider    (needs Facility loaded first)
--   4. usp_ETL_LoadDimPatient     (needs Payer + Provider)
--   5. usp_ETL_LoadFactClaims
--   6. usp_ETL_LoadFactLabResults
--   7. usp_ETL_LoadFactPrescriptions
--   8. usp_ETL_LoadFactFinancials
--
-- Master: usp_ETL_RunAll  (calls all 8 in order, used by SSIS)
-- ============================================================
USE HealthcareADK;
GO

-- ------------------------------------------------------------
-- ETL Log table  (one row per SP execution)
-- ------------------------------------------------------------
IF OBJECT_ID('dw.ETLLog', 'U') IS NULL
CREATE TABLE dw.ETLLog (
    LogID           INT           IDENTITY(1,1) NOT NULL,
    RunStarted      DATETIME      NOT NULL DEFAULT GETDATE(),
    RunFinished     DATETIME      NULL,
    Entity          VARCHAR(50)   NOT NULL,
    RowsInserted    INT           NULL DEFAULT 0,
    RowsUpdated     INT           NULL DEFAULT 0,
    RowsSkipped     INT           NULL DEFAULT 0,
    Status          VARCHAR(20)   NOT NULL DEFAULT 'Running',  -- Running | Success | Error
    ErrorMessage    NVARCHAR(MAX) NULL,
    CONSTRAINT PK_ETLLog PRIMARY KEY (LogID)
);
GO

-- ============================================================
-- HELPER: inline date string -> DateKey (INT YYYYMMDD)
-- Returns 0 (sentinel) if date is NULL or unparseable.
-- ============================================================
-- Used inline in every SP as:
--   dw.fn_DateKey(s.some_date_string)
-- ============================================================
CREATE OR ALTER FUNCTION dw.fn_DateKey(@d VARCHAR(30))
RETURNS INT
WITH SCHEMABINDING
AS
BEGIN
    RETURN ISNULL(
        CAST(CONVERT(VARCHAR(8), TRY_CAST(@d AS DATE), 112) AS INT),
        0
    );
END;
GO

-- ============================================================
-- 1. usp_ETL_LoadDimPayer   (Type 1 — overwrite on match)
-- ============================================================
CREATE OR ALTER PROCEDURE dw.usp_ETL_LoadDimPayer
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @log INT, @ins INT = 0, @upd INT = 0;

    INSERT dw.ETLLog (Entity) VALUES ('DimPayer');
    SET @log = SCOPE_IDENTITY();

    BEGIN TRY
        MERGE dw.DimPayer AS tgt
        USING (
            SELECT DISTINCT
                payer_id, payer_name, payer_type, plan_name, plan_type,
                address, city, state, zip_code, phone,
                TRY_CAST(created_at AS DATETIME) AS created_at
            FROM stg.Payers
            WHERE stg_status = 'Pending'
        ) AS src ON tgt.PayerID = src.payer_id
        WHEN MATCHED THEN UPDATE SET
            tgt.PayerName   = src.payer_name,
            tgt.PayerType   = src.payer_type,
            tgt.PlanName    = src.plan_name,
            tgt.PlanType    = src.plan_type,
            tgt.Address     = src.address,
            tgt.City        = src.city,
            tgt.[State]     = src.state,
            tgt.ZipCode     = src.zip_code,
            tgt.Phone       = src.phone,
            tgt.DWUpdatedAt = GETDATE()
        WHEN NOT MATCHED BY TARGET THEN INSERT
            (PayerID, PayerName, PayerType, PlanName, PlanType,
             Address, City, [State], ZipCode, Phone, CreatedAt)
        VALUES
            (src.payer_id, src.payer_name, src.payer_type, src.plan_name, src.plan_type,
             src.address, src.city, src.state, src.zip_code, src.phone, src.created_at);

        SET @ins = @@ROWCOUNT;

        UPDATE stg.Payers SET stg_status = 'Processed'
        WHERE stg_status = 'Pending';

        UPDATE dw.ETLLog SET RunFinished = GETDATE(), RowsInserted = @ins,
               Status = 'Success' WHERE LogID = @log;
    END TRY
    BEGIN CATCH
        UPDATE dw.ETLLog SET RunFinished = GETDATE(), Status = 'Error',
               ErrorMessage = ERROR_MESSAGE() WHERE LogID = @log;
        UPDATE stg.Payers SET stg_status = 'Error' WHERE stg_status = 'Pending';
        THROW;
    END CATCH;
END;
GO

-- ============================================================
-- 2. usp_ETL_LoadDimFacility   (Type 1)
-- ============================================================
CREATE OR ALTER PROCEDURE dw.usp_ETL_LoadDimFacility
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @log INT, @ins INT = 0;

    INSERT dw.ETLLog (Entity) VALUES ('DimFacility');
    SET @log = SCOPE_IDENTITY();

    BEGIN TRY
        MERGE dw.DimFacility AS tgt
        USING (
            SELECT DISTINCT
                facility_id, facility_name, facility_type, npi,
                address, city, state, zip_code, phone,
                TRY_CAST(NULLIF(bed_count,'') AS SMALLINT) AS bed_count,
                TRY_CAST(created_at AS DATETIME) AS created_at
            FROM stg.Facilities
            WHERE stg_status = 'Pending'
        ) AS src ON tgt.FacilityID = src.facility_id
        WHEN MATCHED THEN UPDATE SET
            tgt.FacilityName = src.facility_name,
            tgt.FacilityType = src.facility_type,
            tgt.NPI          = src.npi,
            tgt.Address      = src.address,
            tgt.City         = src.city,
            tgt.[State]      = src.state,
            tgt.ZipCode      = src.zip_code,
            tgt.Phone        = src.phone,
            tgt.BedCount     = src.bed_count,
            tgt.DWUpdatedAt  = GETDATE()
        WHEN NOT MATCHED BY TARGET THEN INSERT
            (FacilityID, FacilityName, FacilityType, NPI,
             Address, City, [State], ZipCode, Phone, BedCount, CreatedAt)
        VALUES
            (src.facility_id, src.facility_name, src.facility_type, src.npi,
             src.address, src.city, src.state, src.zip_code, src.phone,
             src.bed_count, src.created_at);

        SET @ins = @@ROWCOUNT;
        UPDATE stg.Facilities SET stg_status = 'Processed' WHERE stg_status = 'Pending';
        UPDATE dw.ETLLog SET RunFinished = GETDATE(), RowsInserted = @ins,
               Status = 'Success' WHERE LogID = @log;
    END TRY
    BEGIN CATCH
        UPDATE dw.ETLLog SET RunFinished = GETDATE(), Status = 'Error',
               ErrorMessage = ERROR_MESSAGE() WHERE LogID = @log;
        UPDATE stg.Facilities SET stg_status = 'Error' WHERE stg_status = 'Pending';
        THROW;
    END CATCH;
END;
GO

-- ============================================================
-- 3. usp_ETL_LoadDimProvider   (Type 1, resolves FacilityKey)
-- ============================================================
CREATE OR ALTER PROCEDURE dw.usp_ETL_LoadDimProvider
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @log INT, @ins INT = 0;

    INSERT dw.ETLLog (Entity) VALUES ('DimProvider');
    SET @log = SCOPE_IDENTITY();

    BEGIN TRY
        MERGE dw.DimProvider AS tgt
        USING (
            SELECT
                s.provider_id, s.npi, s.first_name, s.last_name, s.specialty,
                s.license_number, s.phone, s.email,
                TRY_CAST(NULLIF(s.years_experience,'') AS TINYINT) AS years_experience,
                TRY_CAST(s.created_at AS DATETIME) AS created_at,
                ISNULL(f.FacilityKey, 1) AS FacilityKey
            FROM stg.Providers s
            LEFT JOIN dw.DimFacility f ON f.FacilityID = s.facility_id
            WHERE s.stg_status = 'Pending'
        ) AS src ON tgt.ProviderID = src.provider_id
        WHEN MATCHED THEN UPDATE SET
            tgt.NPI             = src.npi,
            tgt.FirstName       = src.first_name,
            tgt.LastName        = src.last_name,
            tgt.Specialty       = src.specialty,
            tgt.LicenseNumber   = src.license_number,
            tgt.FacilityKey     = src.FacilityKey,
            tgt.Phone           = src.phone,
            tgt.Email           = src.email,
            tgt.YearsExperience = src.years_experience,
            tgt.DWUpdatedAt     = GETDATE()
        WHEN NOT MATCHED BY TARGET THEN INSERT
            (ProviderID, NPI, FirstName, LastName, Specialty, LicenseNumber,
             FacilityKey, Phone, Email, YearsExperience, CreatedAt)
        VALUES
            (src.provider_id, src.npi, src.first_name, src.last_name, src.specialty,
             src.license_number, src.FacilityKey, src.phone, src.email,
             src.years_experience, src.created_at);

        SET @ins = @@ROWCOUNT;
        UPDATE stg.Providers SET stg_status = 'Processed' WHERE stg_status = 'Pending';
        UPDATE dw.ETLLog SET RunFinished = GETDATE(), RowsInserted = @ins,
               Status = 'Success' WHERE LogID = @log;
    END TRY
    BEGIN CATCH
        UPDATE dw.ETLLog SET RunFinished = GETDATE(), Status = 'Error',
               ErrorMessage = ERROR_MESSAGE() WHERE LogID = @log;
        UPDATE stg.Providers SET stg_status = 'Error' WHERE stg_status = 'Pending';
        THROW;
    END CATCH;
END;
GO

-- ============================================================
-- 4. usp_ETL_LoadDimPatient   (SCD Type 2)
--    Tracks changes on: Address, City, State, ZipCode, PrimaryPayerKey
--    New record: INSERT as current.
--    Changed record: expire old, INSERT new current version.
--    Unchanged: skip.
-- ============================================================
CREATE OR ALTER PROCEDURE dw.usp_ETL_LoadDimPatient
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @log INT, @ins INT = 0, @upd INT = 0, @today DATE = CAST(GETDATE() AS DATE);

    INSERT dw.ETLLog (Entity) VALUES ('DimPatient');
    SET @log = SCOPE_IDENTITY();

    BEGIN TRY
        -- Step 1: expire records where tracked attributes changed
        UPDATE dw.DimPatient
        SET    ExpirationDate = DATEADD(DAY, -1, @today),
               IsCurrent      = 0,
               DWUpdatedAt    = GETDATE()
        WHERE  IsCurrent = 1
        AND    PatientID IN (
            SELECT s.patient_id
            FROM   stg.Patients s
            JOIN   dw.DimPatient d ON d.PatientID = s.patient_id AND d.IsCurrent = 1
            WHERE  s.stg_status = 'Pending'
            AND (
                ISNULL(d.Address, '') <> ISNULL(s.address, '')   OR
                ISNULL(d.City,    '') <> ISNULL(s.city,    '')   OR
                ISNULL(d.[State], '') <> ISNULL(s.state,   '')   OR
                ISNULL(d.ZipCode, '') <> ISNULL(s.zip_code,'')   OR
                ISNULL(CAST(d.PrimaryPayerKey AS VARCHAR), '') <>
                    ISNULL((SELECT CAST(PayerKey AS VARCHAR) FROM dw.DimPayer
                            WHERE PayerID = s.primary_payer_id), '')
            )
        );
        SET @upd = @@ROWCOUNT;

        -- Step 2: insert new + just-expired (no current record now)
        INSERT INTO dw.DimPatient
            (PatientID, FirstName, LastName, DateOfBirth, Gender, BloodType,
             Address, City, [State], ZipCode, Phone, Email,
             PrimaryPayerKey, PrimaryProviderKey,
             EffectiveDate, IsCurrent, CreatedAt)
        SELECT
            s.patient_id,
            s.first_name,
            s.last_name,
            TRY_CAST(s.date_of_birth AS DATE),
            s.gender,
            s.blood_type,
            s.address, s.city, s.state, s.zip_code, s.phone, s.email,
            ISNULL((SELECT PayerKey    FROM dw.DimPayer    WHERE PayerID    = s.primary_payer_id), 1),
            ISNULL((SELECT ProviderKey FROM dw.DimProvider WHERE ProviderID = s.primary_provider_id), 1),
            @today,
            1,
            TRY_CAST(s.created_at AS DATETIME)
        FROM stg.Patients s
        WHERE s.stg_status = 'Pending'
        AND NOT EXISTS (
            SELECT 1 FROM dw.DimPatient d
            WHERE d.PatientID = s.patient_id AND d.IsCurrent = 1
        );
        SET @ins = @@ROWCOUNT;

        UPDATE stg.Patients SET stg_status = 'Processed' WHERE stg_status = 'Pending';
        UPDATE dw.ETLLog SET RunFinished = GETDATE(), RowsInserted = @ins,
               RowsUpdated = @upd, Status = 'Success' WHERE LogID = @log;
    END TRY
    BEGIN CATCH
        UPDATE dw.ETLLog SET RunFinished = GETDATE(), Status = 'Error',
               ErrorMessage = ERROR_MESSAGE() WHERE LogID = @log;
        UPDATE stg.Patients SET stg_status = 'Error' WHERE stg_status = 'Pending';
        THROW;
    END CATCH;
END;
GO

-- ============================================================
-- 5. usp_ETL_LoadFactClaims
-- ============================================================
CREATE OR ALTER PROCEDURE dw.usp_ETL_LoadFactClaims
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @log INT, @ins INT = 0, @skip INT = 0;

    INSERT dw.ETLLog (Entity) VALUES ('FactClaims');
    SET @log = SCOPE_IDENTITY();

    BEGIN TRY
        INSERT INTO dw.FactClaims
            (ClaimID, PatientKey, ProviderKey, FacilityKey, PayerKey,
             ServiceDateKey, ClaimDateKey, DiagnosisKey, ProcedureKey,
             BilledAmount, AllowedAmount, PaidAmount,
             ClaimStatus, DenialReason, CreatedAt)
        SELECT
            s.claim_id,
            ISNULL(pat.PatientKey,  1),
            ISNULL(prv.ProviderKey, 1),
            ISNULL(fac.FacilityKey, 1),
            ISNULL(pay.PayerKey,    1),
            dw.fn_DateKey(s.service_date),
            dw.fn_DateKey(s.claim_date),
            ISNULL(dx.DiagnosisKey, 1),
            ISNULL(px.ProcedureKey, 1),
            ISNULL(TRY_CAST(s.billed_amount  AS DECIMAL(10,2)), 0),
            ISNULL(TRY_CAST(s.allowed_amount AS DECIMAL(10,2)), 0),
            ISNULL(TRY_CAST(s.paid_amount    AS DECIMAL(10,2)), 0),
            s.claim_status,
            NULLIF(s.denial_reason, ''),
            TRY_CAST(s.created_at AS DATETIME)
        FROM stg.Claims s
        LEFT JOIN dw.DimPatient   pat ON pat.PatientID  = s.patient_id   AND pat.IsCurrent = 1
        LEFT JOIN dw.DimProvider  prv ON prv.ProviderID = s.provider_id
        LEFT JOIN dw.DimFacility  fac ON fac.FacilityID = s.facility_id
        LEFT JOIN dw.DimPayer     pay ON pay.PayerID     = s.payer_id
        LEFT JOIN dw.DimDiagnosis dx  ON dx.ICD10Code    = s.icd10_primary
        LEFT JOIN dw.DimProcedure px  ON px.CPTCode      = s.procedure_code
        WHERE s.stg_status = 'Pending'
        AND NOT EXISTS (SELECT 1 FROM dw.FactClaims fc WHERE fc.ClaimID = s.claim_id);

        SET @ins = @@ROWCOUNT;
        SELECT @skip = COUNT(*) FROM stg.Claims
        WHERE stg_status = 'Pending'
        AND EXISTS (SELECT 1 FROM dw.FactClaims fc WHERE fc.ClaimID = claim_id);

        UPDATE stg.Claims SET stg_status = 'Processed' WHERE stg_status = 'Pending';
        UPDATE dw.ETLLog SET RunFinished = GETDATE(), RowsInserted = @ins,
               RowsSkipped = @skip, Status = 'Success' WHERE LogID = @log;
    END TRY
    BEGIN CATCH
        UPDATE dw.ETLLog SET RunFinished = GETDATE(), Status = 'Error',
               ErrorMessage = ERROR_MESSAGE() WHERE LogID = @log;
        UPDATE stg.Claims SET stg_status = 'Error' WHERE stg_status = 'Pending';
        THROW;
    END CATCH;
END;
GO

-- ============================================================
-- 6. usp_ETL_LoadFactLabResults
-- ============================================================
CREATE OR ALTER PROCEDURE dw.usp_ETL_LoadFactLabResults
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @log INT, @ins INT = 0;

    INSERT dw.ETLLog (Entity) VALUES ('FactLabResults');
    SET @log = SCOPE_IDENTITY();

    BEGIN TRY
        INSERT INTO dw.FactLabResults
            (LabID, PatientKey, ProviderKey, FacilityKey,
             OrderDateKey, ResultDateKey,
             TestName, LOINCCode, AbnormalFlag,
             ResultValue, ResultUnit, ReferenceRangeLow, ReferenceRangeHigh,
             CreatedAt)
        SELECT
            s.lab_id,
            ISNULL(pat.PatientKey,  1),
            ISNULL(prv.ProviderKey, 1),
            ISNULL(fac.FacilityKey, 1),
            dw.fn_DateKey(s.order_date),
            dw.fn_DateKey(s.result_date),
            s.test_name,
            s.loinc_code,
            s.abnormal_flag,
            TRY_CAST(s.result_value          AS DECIMAL(10,3)),
            s.result_unit,
            TRY_CAST(s.reference_range_low   AS DECIMAL(10,3)),
            TRY_CAST(s.reference_range_high  AS DECIMAL(10,3)),
            TRY_CAST(s.created_at AS DATETIME)
        FROM stg.Labs s
        LEFT JOIN dw.DimPatient  pat ON pat.PatientID  = s.patient_id  AND pat.IsCurrent = 1
        LEFT JOIN dw.DimProvider prv ON prv.ProviderID = s.provider_id
        LEFT JOIN dw.DimFacility fac ON fac.FacilityID = s.facility_id
        WHERE s.stg_status = 'Pending'
        AND NOT EXISTS (SELECT 1 FROM dw.FactLabResults fl WHERE fl.LabID = s.lab_id);

        SET @ins = @@ROWCOUNT;
        UPDATE stg.Labs SET stg_status = 'Processed' WHERE stg_status = 'Pending';
        UPDATE dw.ETLLog SET RunFinished = GETDATE(), RowsInserted = @ins,
               Status = 'Success' WHERE LogID = @log;
    END TRY
    BEGIN CATCH
        UPDATE dw.ETLLog SET RunFinished = GETDATE(), Status = 'Error',
               ErrorMessage = ERROR_MESSAGE() WHERE LogID = @log;
        UPDATE stg.Labs SET stg_status = 'Error' WHERE stg_status = 'Pending';
        THROW;
    END CATCH;
END;
GO

-- ============================================================
-- 7. usp_ETL_LoadFactPrescriptions
-- ============================================================
CREATE OR ALTER PROCEDURE dw.usp_ETL_LoadFactPrescriptions
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @log INT, @ins INT = 0;

    INSERT dw.ETLLog (Entity) VALUES ('FactPrescriptions');
    SET @log = SCOPE_IDENTITY();

    BEGIN TRY
        INSERT INTO dw.FactPrescriptions
            (PrescriptionID, PatientKey, ProviderKey, PayerKey, DrugKey,
             PrescribedDateKey, FillDateKey,
             DaysSupply, Quantity, RefillsAuthorized, RefillsRemaining,
             CostToPatient, CostToPayer, CreatedAt)
        SELECT
            s.prescription_id,
            ISNULL(pat.PatientKey,  1),
            ISNULL(prv.ProviderKey, 1),
            ISNULL(pay.PayerKey,    1),
            ISNULL(drg.DrugKey,     1),
            dw.fn_DateKey(s.prescribed_date),
            dw.fn_DateKey(s.fill_date),
            TRY_CAST(s.days_supply        AS SMALLINT),
            TRY_CAST(s.quantity           AS SMALLINT),
            TRY_CAST(s.refills_authorized AS TINYINT),
            TRY_CAST(s.refills_remaining  AS TINYINT),
            TRY_CAST(s.cost_to_patient    AS DECIMAL(10,2)),
            TRY_CAST(s.cost_to_payer      AS DECIMAL(10,2)),
            TRY_CAST(s.created_at AS DATETIME)
        FROM stg.Prescriptions s
        LEFT JOIN dw.DimPatient  pat ON pat.PatientID  = s.patient_id  AND pat.IsCurrent = 1
        LEFT JOIN dw.DimProvider prv ON prv.ProviderID = s.provider_id
        LEFT JOIN dw.DimPayer    pay ON pay.PayerID     = s.payer_id
        LEFT JOIN dw.DimDrug     drg ON drg.NDCCode     = s.ndc_code
        WHERE s.stg_status = 'Pending'
        AND NOT EXISTS (SELECT 1 FROM dw.FactPrescriptions fp
                        WHERE fp.PrescriptionID = s.prescription_id);

        SET @ins = @@ROWCOUNT;
        UPDATE stg.Prescriptions SET stg_status = 'Processed' WHERE stg_status = 'Pending';
        UPDATE dw.ETLLog SET RunFinished = GETDATE(), RowsInserted = @ins,
               Status = 'Success' WHERE LogID = @log;
    END TRY
    BEGIN CATCH
        UPDATE dw.ETLLog SET RunFinished = GETDATE(), Status = 'Error',
               ErrorMessage = ERROR_MESSAGE() WHERE LogID = @log;
        UPDATE stg.Prescriptions SET stg_status = 'Error' WHERE stg_status = 'Pending';
        THROW;
    END CATCH;
END;
GO

-- ============================================================
-- 8. usp_ETL_LoadFactFinancials
-- ============================================================
CREATE OR ALTER PROCEDURE dw.usp_ETL_LoadFactFinancials
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @log INT, @ins INT = 0;

    INSERT dw.ETLLog (Entity) VALUES ('FactFinancials');
    SET @log = SCOPE_IDENTITY();

    BEGIN TRY
        INSERT INTO dw.FactFinancials
            (TransactionID, TransactionDateKey, FacilityKey,
             TransactionType, Department, CostCenter, GLAccount, Description,
             Amount, FiscalYear, FiscalQuarter, CreatedAt)
        SELECT
            s.transaction_id,
            dw.fn_DateKey(s.transaction_date),
            ISNULL(fac.FacilityKey, 1),
            s.transaction_type,
            s.department,
            s.cost_center,
            s.gl_account,
            s.description,
            ISNULL(TRY_CAST(s.amount AS DECIMAL(15,2)), 0),
            TRY_CAST(s.fiscal_year    AS SMALLINT),
            TRY_CAST(s.fiscal_quarter AS TINYINT),
            TRY_CAST(s.created_at AS DATETIME)
        FROM stg.Financials s
        LEFT JOIN dw.DimFacility fac ON fac.FacilityID = s.facility_id
        WHERE s.stg_status = 'Pending'
        AND NOT EXISTS (SELECT 1 FROM dw.FactFinancials ff
                        WHERE ff.TransactionID = s.transaction_id);

        SET @ins = @@ROWCOUNT;
        UPDATE stg.Financials SET stg_status = 'Processed' WHERE stg_status = 'Pending';
        UPDATE dw.ETLLog SET RunFinished = GETDATE(), RowsInserted = @ins,
               Status = 'Success' WHERE LogID = @log;
    END TRY
    BEGIN CATCH
        UPDATE dw.ETLLog SET RunFinished = GETDATE(), Status = 'Error',
               ErrorMessage = ERROR_MESSAGE() WHERE LogID = @log;
        UPDATE stg.Financials SET stg_status = 'Error' WHERE stg_status = 'Pending';
        THROW;
    END CATCH;
END;
GO

-- ============================================================
-- MASTER: usp_ETL_RunAll
-- Single entry point called by SSIS Package 2.
-- ============================================================
CREATE OR ALTER PROCEDURE dw.usp_ETL_RunAll
AS
BEGIN
    SET NOCOUNT ON;
    EXEC dw.usp_ETL_LoadDimPayer;
    EXEC dw.usp_ETL_LoadDimFacility;
    EXEC dw.usp_ETL_LoadDimProvider;
    EXEC dw.usp_ETL_LoadDimPatient;
    EXEC dw.usp_ETL_LoadFactClaims;
    EXEC dw.usp_ETL_LoadFactLabResults;
    EXEC dw.usp_ETL_LoadFactPrescriptions;
    EXEC dw.usp_ETL_LoadFactFinancials;

    -- Summary of this run
    SELECT Entity, RowsInserted, RowsUpdated, RowsSkipped, Status,
           DATEDIFF(SECOND, RunStarted, RunFinished) AS DurationSec
    FROM   dw.ETLLog
    WHERE  RunStarted >= DATEADD(MINUTE, -5, GETDATE())
    ORDER  BY LogID;
END;
GO

PRINT 'ETL objects created: ETLLog, fn_DateKey, 8 load SPs, usp_ETL_RunAll';
GO
