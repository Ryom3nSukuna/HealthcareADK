-- ============================================================
-- HealthcareADK : DimDate
-- Pre-populated date dimension covering 2019-01-01 to 2030-12-31.
-- DateKey format: YYYYMMDD (INT) — use as FK in all fact tables.
-- ============================================================
USE HealthcareADK;
GO

IF OBJECT_ID('dw.DimDate', 'U') IS NOT NULL DROP TABLE dw.DimDate;
CREATE TABLE dw.DimDate (
    DateKey         INT          NOT NULL,   -- YYYYMMDD
    FullDate        DATE         NOT NULL,
    DayOfWeek       TINYINT      NOT NULL,   -- 1=Sun .. 7=Sat
    DayName         VARCHAR(10)  NOT NULL,
    DayOfMonth      TINYINT      NOT NULL,
    DayOfYear       SMALLINT     NOT NULL,
    WeekOfYear      TINYINT      NOT NULL,
    MonthNumber     TINYINT      NOT NULL,
    MonthName       VARCHAR(10)  NOT NULL,
    Quarter         TINYINT      NOT NULL,
    QuarterName     CHAR(2)      NOT NULL,   -- Q1 .. Q4
    [Year]          SMALLINT     NOT NULL,
    IsWeekend       BIT          NOT NULL,
    FiscalYear      SMALLINT     NOT NULL,   -- fiscal = calendar for now
    FiscalQuarter   TINYINT      NOT NULL,

    CONSTRAINT PK_dw_DimDate PRIMARY KEY (DateKey)
);
GO

-- ------------------------------------------------------------
-- Populate DimDate  2019-01-01 through 2030-12-31
-- ------------------------------------------------------------
DECLARE @start DATE = '2019-01-01';
DECLARE @end   DATE = '2030-12-31';
DECLARE @d     DATE = @start;

WHILE @d <= @end
BEGIN
    INSERT INTO dw.DimDate (
        DateKey, FullDate,
        DayOfWeek, DayName, DayOfMonth, DayOfYear, WeekOfYear,
        MonthNumber, MonthName, Quarter, QuarterName, [Year],
        IsWeekend, FiscalYear, FiscalQuarter
    )
    VALUES (
        CAST(FORMAT(@d, 'yyyyMMdd') AS INT),
        @d,
        DATEPART(WEEKDAY, @d),
        DATENAME(WEEKDAY, @d),
        DAY(@d),
        DATEPART(DAYOFYEAR, @d),
        DATEPART(WEEK, @d),
        MONTH(@d),
        DATENAME(MONTH, @d),
        DATEPART(QUARTER, @d),
        'Q' + CAST(DATEPART(QUARTER, @d) AS CHAR(1)),
        YEAR(@d),
        CASE WHEN DATEPART(WEEKDAY, @d) IN (1, 7) THEN 1 ELSE 0 END,
        YEAR(@d),
        DATEPART(QUARTER, @d)
    );

    SET @d = DATEADD(DAY, 1, @d);
END;
GO

-- Unknown date sentinel (used for NULLs in fact FKs)
INSERT INTO dw.DimDate (
    DateKey, FullDate, DayOfWeek, DayName, DayOfMonth, DayOfYear,
    WeekOfYear, MonthNumber, MonthName, Quarter, QuarterName, [Year],
    IsWeekend, FiscalYear, FiscalQuarter
)
VALUES (0, '1900-01-01', 0, 'Unknown', 0, 0, 0, 0, 'Unknown', 0, 'Q0', 0, 0, 0, 0);
GO

PRINT 'DimDate populated: 2019-01-01 to 2030-12-31 + sentinel row (DateKey=0).';
GO
