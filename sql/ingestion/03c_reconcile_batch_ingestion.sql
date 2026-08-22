-- ============================================================================
-- Enterprise Payments Intelligence Platform
-- Milestone 3 / Step 3C
--
-- Reconciliation between:
--
-- Step 3A:
-- payments_dev.ingestion.payment_transactions_batch
--
-- Step 3C:
-- payments_dev.ingestion.payment_transactions_batch_s3
--
-- File lineage and ingestion timestamps are intentionally excluded from
-- business-data comparisons because the physical ingestion sources differ.
-- ============================================================================


-- ----------------------------------------------------------------------------
-- 1. High-level row-count reconciliation
-- ----------------------------------------------------------------------------

SELECT
    managed.managed_volume_rows,
    s3.s3_rows,
    managed.managed_volume_rows - s3.s3_rows AS row_count_difference
FROM
(
    SELECT
        COUNT(*) AS managed_volume_rows
    FROM payments_dev.ingestion.payment_transactions_batch
) managed
CROSS JOIN
(
    SELECT
        COUNT(*) AS s3_rows
    FROM payments_dev.ingestion.payment_transactions_batch_s3
) s3;


-- Expected:
--
-- managed_volume_rows = 1000
-- s3_rows             = 1000
-- row_count_difference = 0



-- ----------------------------------------------------------------------------
-- 2. Distinct transaction reconciliation
-- ----------------------------------------------------------------------------

SELECT
    managed.managed_transactions,
    s3.s3_transactions,
    managed.managed_transactions - s3.s3_transactions
        AS transaction_difference
FROM
(
    SELECT
        COUNT(DISTINCT transaction_id) AS managed_transactions
    FROM payments_dev.ingestion.payment_transactions_batch
) managed
CROSS JOIN
(
    SELECT
        COUNT(DISTINCT transaction_id) AS s3_transactions
    FROM payments_dev.ingestion.payment_transactions_batch_s3
) s3;


-- Expected:
--
-- managed_transactions = 1000
-- s3_transactions       = 1000
-- transaction_difference = 0



-- ----------------------------------------------------------------------------
-- 3. Transactions missing from S3 ingestion
-- ----------------------------------------------------------------------------

SELECT
    COUNT(*) AS transactions_missing_from_s3
FROM payments_dev.ingestion.payment_transactions_batch managed
LEFT ANTI JOIN
    payments_dev.ingestion.payment_transactions_batch_s3 s3
ON managed.transaction_id = s3.transaction_id;


-- Expected:
--
-- 0



-- ----------------------------------------------------------------------------
-- 4. Unexpected transactions in S3 ingestion
-- ----------------------------------------------------------------------------

SELECT
    COUNT(*) AS unexpected_transactions_in_s3
FROM payments_dev.ingestion.payment_transactions_batch_s3 s3
LEFT ANTI JOIN
    payments_dev.ingestion.payment_transactions_batch managed
ON s3.transaction_id = managed.transaction_id;


-- Expected:
--
-- 0



-- ----------------------------------------------------------------------------
-- 5. Full business-record comparison:
--    records in Step 3A that do not exist identically in Step 3C.
-- ----------------------------------------------------------------------------

SELECT COUNT(*) AS business_records_missing_or_different_in_s3
FROM
(
    SELECT
        transaction_id,
        account_id,
        merchant_id,
        event_timestamp,
        amount,
        currency,
        channel,
        payment_method,
        status,
        card_present,
        device_id,
        ip_address,
        country

    FROM payments_dev.ingestion.payment_transactions_batch

    EXCEPT ALL

    SELECT
        transaction_id,
        account_id,
        merchant_id,
        event_timestamp,
        amount,
        currency,
        channel,
        payment_method,
        status,
        card_present,
        device_id,
        ip_address,
        country

    FROM payments_dev.ingestion.payment_transactions_batch_s3
);


-- Expected:
--
-- 0



-- ----------------------------------------------------------------------------
-- 6. Reverse full business-record comparison:
--    records in Step 3C that do not exist identically in Step 3A.
-- ----------------------------------------------------------------------------

SELECT COUNT(*) AS unexpected_or_different_business_records_in_s3
FROM
(
    SELECT
        transaction_id,
        account_id,
        merchant_id,
        event_timestamp,
        amount,
        currency,
        channel,
        payment_method,
        status,
        card_present,
        device_id,
        ip_address,
        country

    FROM payments_dev.ingestion.payment_transactions_batch_s3

    EXCEPT ALL

    SELECT
        transaction_id,
        account_id,
        merchant_id,
        event_timestamp,
        amount,
        currency,
        channel,
        payment_method,
        status,
        card_present,
        device_id,
        ip_address,
        country

    FROM payments_dev.ingestion.payment_transactions_batch
);


-- Expected:
--
-- 0



-- ----------------------------------------------------------------------------
-- 7. Duplicate transaction check
-- ----------------------------------------------------------------------------

SELECT
    transaction_id,
    COUNT(*) AS occurrence_count
FROM payments_dev.ingestion.payment_transactions_batch_s3
GROUP BY transaction_id
HAVING COUNT(*) > 1
ORDER BY occurrence_count DESC;


-- Expected:
--
-- no rows



-- ----------------------------------------------------------------------------
-- 8. File-level ingestion reconciliation
-- ----------------------------------------------------------------------------

SELECT
    source_file,
    source_file_name,
    COUNT(*) AS records_loaded
FROM payments_dev.ingestion.payment_transactions_batch_s3
GROUP BY
    source_file,
    source_file_name
ORDER BY
    source_file;


-- Expected:
--
-- one result per source transactions.jsonl file
-- total across all files = 1000