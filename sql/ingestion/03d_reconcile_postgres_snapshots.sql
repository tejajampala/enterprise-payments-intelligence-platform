-- ============================================================================
-- Enterprise Payments Intelligence Platform
-- Milestone 3 / Step 3D
--
-- PostgreSQL snapshot ingestion reconciliation.
-- ============================================================================


-- ============================================================================
-- 1. SOURCE VS TARGET ROW COUNTS
-- ============================================================================

WITH source_counts AS
(
    SELECT
        'customers' AS dataset,
        COUNT(*) AS source_rows
    FROM read_files(
        '/Volumes/payments_dev/landing/postgres_batch_source/snapshots/customers.csv',
        format => 'csv',
        header => true
    )

    UNION ALL

    SELECT
        'accounts',
        COUNT(*)
    FROM read_files(
        '/Volumes/payments_dev/landing/postgres_batch_source/snapshots/accounts.csv',
        format => 'csv',
        header => true
    )

    UNION ALL

    SELECT
        'merchants',
        COUNT(*)
    FROM read_files(
        '/Volumes/payments_dev/landing/postgres_batch_source/snapshots/merchants.csv',
        format => 'csv',
        header => true
    )

    UNION ALL

    SELECT
        'fraud_cases',
        COUNT(*)
    FROM read_files(
        '/Volumes/payments_dev/landing/postgres_batch_source/snapshots/fraud_cases.csv',
        format => 'csv',
        header => true
    )
),

target_counts AS
(
    SELECT
        'customers' AS dataset,
        COUNT(*) AS target_rows
    FROM payments_dev.ingestion.customers_snapshot

    UNION ALL

    SELECT
        'accounts',
        COUNT(*)
    FROM payments_dev.ingestion.accounts_snapshot

    UNION ALL

    SELECT
        'merchants',
        COUNT(*)
    FROM payments_dev.ingestion.merchants_snapshot

    UNION ALL

    SELECT
        'fraud_cases',
        COUNT(*)
    FROM payments_dev.ingestion.fraud_cases_snapshot
)

SELECT
    source.dataset,
    source.source_rows,
    target.target_rows,
    source.source_rows - target.target_rows AS difference
FROM source_counts source
INNER JOIN target_counts target
    ON source.dataset = target.dataset
ORDER BY source.dataset;


-- Expected:
--
-- difference = 0
-- for every dataset.



-- ============================================================================
-- 2. PRIMARY-KEY DUPLICATES
-- ============================================================================

SELECT
    customer_id,
    COUNT(*) AS occurrence_count
FROM payments_dev.ingestion.customers_snapshot
GROUP BY customer_id
HAVING COUNT(*) > 1;


-- Expected: no rows


SELECT
    account_id,
    COUNT(*) AS occurrence_count
FROM payments_dev.ingestion.accounts_snapshot
GROUP BY account_id
HAVING COUNT(*) > 1;


-- Expected: no rows


SELECT
    merchant_id,
    COUNT(*) AS occurrence_count
FROM payments_dev.ingestion.merchants_snapshot
GROUP BY merchant_id
HAVING COUNT(*) > 1;


-- Expected: no rows


SELECT
    case_id,
    COUNT(*) AS occurrence_count
FROM payments_dev.ingestion.fraud_cases_snapshot
GROUP BY case_id
HAVING COUNT(*) > 1;


-- Expected: no rows



-- ============================================================================
-- 3. NULL BUSINESS KEYS
-- ============================================================================

SELECT COUNT(*) AS null_customer_ids
FROM payments_dev.ingestion.customers_snapshot
WHERE customer_id IS NULL;


SELECT COUNT(*) AS null_account_ids
FROM payments_dev.ingestion.accounts_snapshot
WHERE account_id IS NULL;


SELECT COUNT(*) AS null_merchant_ids
FROM payments_dev.ingestion.merchants_snapshot
WHERE merchant_id IS NULL;


SELECT COUNT(*) AS null_case_ids
FROM payments_dev.ingestion.fraud_cases_snapshot
WHERE case_id IS NULL;


-- Expected:
--
-- all = 0



-- ============================================================================
-- 4. ACCOUNT -> CUSTOMER REFERENTIAL INTEGRITY
-- ============================================================================

SELECT COUNT(*) AS accounts_without_customer
FROM payments_dev.ingestion.accounts_snapshot account
LEFT ANTI JOIN payments_dev.ingestion.customers_snapshot customer
    ON account.customer_id = customer.customer_id;


-- Expected:
--
-- 0



-- ============================================================================
-- 5. TRANSACTION -> ACCOUNT REFERENTIAL INTEGRITY
--
-- Use the production-style S3 transaction table created in Step 3C.
-- ============================================================================

SELECT COUNT(*) AS transactions_without_account
FROM payments_dev.ingestion.payment_transactions_batch_s3 transaction
LEFT ANTI JOIN payments_dev.ingestion.accounts_snapshot account
    ON transaction.account_id = account.account_id;


-- Expected:
--
-- 0



-- ============================================================================
-- 6. TRANSACTION -> MERCHANT REFERENTIAL INTEGRITY
-- ============================================================================

SELECT COUNT(*) AS transactions_without_merchant
FROM payments_dev.ingestion.payment_transactions_batch_s3 transaction
LEFT ANTI JOIN payments_dev.ingestion.merchants_snapshot merchant
    ON transaction.merchant_id = merchant.merchant_id;


-- Expected:
--
-- 0



-- ============================================================================
-- 7. FRAUD CASE -> TRANSACTION REFERENTIAL INTEGRITY
-- ============================================================================

SELECT COUNT(*) AS fraud_cases_without_transaction
FROM payments_dev.ingestion.fraud_cases_snapshot fraud
LEFT ANTI JOIN payments_dev.ingestion.payment_transactions_batch_s3 transaction
    ON fraud.transaction_id = transaction.transaction_id;


-- Expected:
--
-- 0



-- ============================================================================
-- 8. SNAPSHOT RECORD VERSION CHECK
--
-- Initial snapshots should represent the baseline source version.
-- CDC updates will be processed separately in Milestone 6.
-- ============================================================================

SELECT
    record_version,
    COUNT(*) AS customer_count
FROM payments_dev.ingestion.customers_snapshot
GROUP BY record_version
ORDER BY record_version;


SELECT
    record_version,
    COUNT(*) AS account_count
FROM payments_dev.ingestion.accounts_snapshot
GROUP BY record_version
ORDER BY record_version;


SELECT
    record_version,
    COUNT(*) AS merchant_count
FROM payments_dev.ingestion.merchants_snapshot
GROUP BY record_version
ORDER BY record_version;


-- Baseline snapshot expectation:
--
-- record_version = 1



-- ============================================================================
-- 9. SOFT-DELETE CHECK
--
-- The clean baseline snapshot should not contain the later CDC soft-delete
-- scenario.
-- ============================================================================

SELECT COUNT(*) AS deleted_customers_in_snapshot
FROM payments_dev.ingestion.customers_snapshot
WHERE is_deleted = true;


SELECT COUNT(*) AS deleted_accounts_in_snapshot
FROM payments_dev.ingestion.accounts_snapshot
WHERE is_deleted = true;


SELECT COUNT(*) AS deleted_merchants_in_snapshot
FROM payments_dev.ingestion.merchants_snapshot
WHERE is_deleted = true;


-- Expected:
--
-- 0
-- 0
-- 0



-- ============================================================================
-- 10. SOURCE FILE LINEAGE
-- ============================================================================

SELECT
    'customers' AS dataset,
    source_file,
    source_file_name,
    COUNT(*) AS row_count
FROM payments_dev.ingestion.customers_snapshot
GROUP BY source_file, source_file_name

UNION ALL

SELECT
    'accounts',
    source_file,
    source_file_name,
    COUNT(*)
FROM payments_dev.ingestion.accounts_snapshot
GROUP BY source_file, source_file_name

UNION ALL

SELECT
    'merchants',
    source_file,
    source_file_name,
    COUNT(*)
FROM payments_dev.ingestion.merchants_snapshot
GROUP BY source_file, source_file_name

UNION ALL

SELECT
    'fraud_cases',
    source_file,
    source_file_name,
    COUNT(*)
FROM payments_dev.ingestion.fraud_cases_snapshot
GROUP BY source_file, source_file_name

ORDER BY dataset;