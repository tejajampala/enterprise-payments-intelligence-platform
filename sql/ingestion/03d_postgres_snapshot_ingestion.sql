-- ============================================================================
-- Enterprise Payments Intelligence Platform
-- Milestone 3 / Step 3D
--
-- PostgreSQL-style master-data snapshot ingestion.
--
-- Source:
-- /Volumes/payments_dev/landing/postgres_batch_source/snapshots/
--
-- These tables represent raw snapshot ingestion.
-- CDC / SCD Type 2 processing is intentionally deferred to Milestone 6.
-- ============================================================================


-- ============================================================================
-- CUSTOMERS
-- ============================================================================

CREATE TABLE IF NOT EXISTS
    payments_dev.ingestion.customers_snapshot
(
    customer_id STRING,
    first_name STRING,
    last_name STRING,
    date_of_birth DATE,
    email STRING,
    phone STRING,
    address_line_1 STRING,
    city STRING,
    state STRING,
    postcode STRING,
    country STRING,
    risk_rating STRING,
    kyc_status STRING,
    status STRING,
    record_version INT,
    source_updated_at TIMESTAMP,
    is_deleted BOOLEAN,

    source_file STRING,
    source_file_name STRING,
    ingested_at TIMESTAMP
)
USING DELTA
COMMENT 'Raw customer snapshot extracted from the PostgreSQL source system';


COPY INTO payments_dev.ingestion.customers_snapshot
FROM
(
    SELECT
        CAST(customer_id AS STRING) AS customer_id,
        CAST(first_name AS STRING) AS first_name,
        CAST(last_name AS STRING) AS last_name,
        CAST(date_of_birth AS DATE) AS date_of_birth,
        CAST(email AS STRING) AS email,
        CAST(phone AS STRING) AS phone,
        CAST(address_line_1 AS STRING) AS address_line_1,
        CAST(city AS STRING) AS city,
        CAST(state AS STRING) AS state,
        CAST(postcode AS STRING) AS postcode,
        CAST(country AS STRING) AS country,
        CAST(risk_rating AS STRING) AS risk_rating,
        CAST(kyc_status AS STRING) AS kyc_status,
        CAST(status AS STRING) AS status,
        CAST(record_version AS INT) AS record_version,
        CAST(source_updated_at AS TIMESTAMP) AS source_updated_at,
        CAST(is_deleted AS BOOLEAN) AS is_deleted,

        _metadata.file_path AS source_file,
        _metadata.file_name AS source_file_name,
        current_timestamp() AS ingested_at

    FROM
        '/Volumes/payments_dev/landing/postgres_batch_source/snapshots/customers.csv'
)
FILEFORMAT = CSV
FORMAT_OPTIONS
(
    'header' = 'true'
);


-- ============================================================================
-- ACCOUNTS
-- ============================================================================

CREATE TABLE IF NOT EXISTS
    payments_dev.ingestion.accounts_snapshot
(
    account_id STRING,
    customer_id STRING,
    account_type STRING,
    currency STRING,
    status STRING,
    opened_date DATE,
    current_balance DECIMAL(18, 2),
    record_version INT,
    source_updated_at TIMESTAMP,
    is_deleted BOOLEAN,

    source_file STRING,
    source_file_name STRING,
    ingested_at TIMESTAMP
)
USING DELTA
COMMENT 'Raw account snapshot extracted from the PostgreSQL source system';


COPY INTO payments_dev.ingestion.accounts_snapshot
FROM
(
    SELECT
        CAST(account_id AS STRING) AS account_id,
        CAST(customer_id AS STRING) AS customer_id,
        CAST(account_type AS STRING) AS account_type,
        CAST(currency AS STRING) AS currency,
        CAST(status AS STRING) AS status,
        CAST(opened_date AS DATE) AS opened_date,
        CAST(current_balance AS DECIMAL(18, 2)) AS current_balance,
        CAST(record_version AS INT) AS record_version,
        CAST(source_updated_at AS TIMESTAMP) AS source_updated_at,
        CAST(is_deleted AS BOOLEAN) AS is_deleted,

        _metadata.file_path AS source_file,
        _metadata.file_name AS source_file_name,
        current_timestamp() AS ingested_at

    FROM
        '/Volumes/payments_dev/landing/postgres_batch_source/snapshots/accounts.csv'
)
FILEFORMAT = CSV
FORMAT_OPTIONS
(
    'header' = 'true'
);


-- ============================================================================
-- MERCHANTS
-- ============================================================================

CREATE TABLE IF NOT EXISTS
    payments_dev.ingestion.merchants_snapshot
(
    merchant_id STRING,
    merchant_name STRING,
    merchant_category_code STRING,
    city STRING,
    country STRING,
    risk_rating STRING,
    status STRING,
    record_version INT,
    source_updated_at TIMESTAMP,
    is_deleted BOOLEAN,

    source_file STRING,
    source_file_name STRING,
    ingested_at TIMESTAMP
)
USING DELTA
COMMENT 'Raw merchant snapshot extracted from the PostgreSQL source system';


COPY INTO payments_dev.ingestion.merchants_snapshot
FROM
(
    SELECT
        CAST(merchant_id AS STRING) AS merchant_id,
        CAST(merchant_name AS STRING) AS merchant_name,
        CAST(merchant_category_code AS STRING) AS merchant_category_code,
        CAST(city AS STRING) AS city,
        CAST(country AS STRING) AS country,
        CAST(risk_rating AS STRING) AS risk_rating,
        CAST(status AS STRING) AS status,
        CAST(record_version AS INT) AS record_version,
        CAST(source_updated_at AS TIMESTAMP) AS source_updated_at,
        CAST(is_deleted AS BOOLEAN) AS is_deleted,

        _metadata.file_path AS source_file,
        _metadata.file_name AS source_file_name,
        current_timestamp() AS ingested_at

    FROM
        '/Volumes/payments_dev/landing/postgres_batch_source/snapshots/merchants.csv'
)
FILEFORMAT = CSV
FORMAT_OPTIONS
(
    'header' = 'true'
);


-- ============================================================================
-- FRAUD CASES
-- ============================================================================

CREATE TABLE IF NOT EXISTS
    payments_dev.ingestion.fraud_cases_snapshot
(
    case_id STRING,
    transaction_id STRING,
    opened_at TIMESTAMP,
    status STRING,
    suspected_reason STRING,
    outcome STRING,
    analyst_notes STRING,
    closed_at TIMESTAMP,

    source_file STRING,
    source_file_name STRING,
    ingested_at TIMESTAMP
)
USING DELTA
COMMENT 'Raw fraud-case snapshot extracted from the PostgreSQL source system';


COPY INTO payments_dev.ingestion.fraud_cases_snapshot
FROM
(
    SELECT
        CAST(case_id AS STRING) AS case_id,
        CAST(transaction_id AS STRING) AS transaction_id,
        CAST(opened_at AS TIMESTAMP) AS opened_at,
        CAST(status AS STRING) AS status,
        CAST(suspected_reason AS STRING) AS suspected_reason,
        CAST(outcome AS STRING) AS outcome,
        CAST(analyst_notes AS STRING) AS analyst_notes,
        CAST(NULLIF(closed_at, '') AS TIMESTAMP) AS closed_at,

        _metadata.file_path AS source_file,
        _metadata.file_name AS source_file_name,
        current_timestamp() AS ingested_at

    FROM
        '/Volumes/payments_dev/landing/postgres_batch_source/snapshots/fraud_cases.csv'
)
FILEFORMAT = CSV
FORMAT_OPTIONS
(
    'header' = 'true'
);