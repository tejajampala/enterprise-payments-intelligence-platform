-- ============================================================================
-- EPIP Milestone 5 Medallion Reconciliation
-- ============================================================================


-- 1. Ingestion -> Silver transaction count

SELECT
    'transaction_count' AS check_name,
    (
        SELECT COUNT(*)
        FROM payments_dev.ingestion.payment_transactions_batch_s3
    ) AS source_value,
    (
        SELECT COUNT(*)
        FROM payments_dev.silver.payment_transactions
    ) AS target_value;


-- 2. Silver -> enriched count

SELECT
    'enriched_transaction_count' AS check_name,
    (
        SELECT COUNT(*)
        FROM payments_dev.silver.payment_transactions
    ) AS source_value,
    (
        SELECT COUNT(*)
        FROM payments_dev.silver.payment_transactions_enriched
    ) AS target_value;


-- 3. Silver -> enriched amount

SELECT
    'enriched_payment_amount' AS check_name,
    (
        SELECT ROUND(SUM(amount), 2)
        FROM payments_dev.silver.payment_transactions
    ) AS source_value,
    (
        SELECT ROUND(SUM(amount), 2)
        FROM payments_dev.silver.payment_transactions_enriched
    ) AS target_value;


-- 4. Dimension reference integrity

SELECT
    COUNT(*) AS transactions,

    SUM(
        CASE
            WHEN account_dimension_match = false THEN 1
            ELSE 0
        END
    ) AS missing_accounts,

    SUM(
        CASE
            WHEN customer_dimension_match = false THEN 1
            ELSE 0
        END
    ) AS missing_customers,

    SUM(
        CASE
            WHEN merchant_dimension_match = false THEN 1
            ELSE 0
        END
    ) AS missing_merchants

FROM payments_dev.silver.payment_transactions_enriched;


-- 5. Silver -> Gold daily count

SELECT
    (
        SELECT COUNT(*)
        FROM payments_dev.silver.payment_transactions_enriched
    ) AS silver_transactions,

    (
        SELECT SUM(transaction_count)
        FROM payments_dev.gold.daily_payment_metrics
    ) AS gold_transactions;


-- 6. Silver -> Gold daily amount

SELECT
    (
        SELECT ROUND(SUM(amount), 2)
        FROM payments_dev.silver.payment_transactions_enriched
    ) AS silver_amount,

    (
        SELECT ROUND(SUM(total_payment_amount), 2)
        FROM payments_dev.gold.daily_payment_metrics
    ) AS gold_amount;


-- 7. Merchant aggregation reconciliation

SELECT
    (
        SELECT COUNT(*)
        FROM payments_dev.silver.payment_transactions_enriched
    ) AS silver_transactions,

    (
        SELECT SUM(transaction_count)
        FROM payments_dev.gold.merchant_payment_metrics
    ) AS merchant_gold_transactions;


-- 8. Transaction status completeness

SELECT
    SUM(transaction_count) AS total_transactions,

    SUM(
        authorized_transactions
        + declined_transactions
        + settled_transactions
        + reversed_transactions
        + refunded_transactions
    ) AS classified_transactions

FROM payments_dev.gold.daily_payment_metrics;


-- 9. Fraud reconciliation

SELECT
    (
        SELECT COUNT(*)
        FROM payments_dev.silver.payment_transactions_enriched
        WHERE has_fraud_case = true
    ) AS silver_fraud_case_transactions,

    (
        SELECT SUM(fraud_case_transactions)
        FROM payments_dev.gold.fraud_operations_metrics
    ) AS gold_fraud_case_transactions;


-- 10. Streaming event profile.
-- Duplicates remain intentionally preserved until Milestone 6.

SELECT
    COUNT(*) AS physical_records,

    COUNT(DISTINCT event_id)
        AS distinct_business_events,

    COUNT(*) - COUNT(DISTINCT event_id)
        AS additional_physical_deliveries

FROM payments_dev.silver.payment_events_standardized;