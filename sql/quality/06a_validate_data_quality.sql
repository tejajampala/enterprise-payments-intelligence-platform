-- ============================================================================
-- EPIP Milestone 6 / Step 6A
-- Data Quality Foundation Validation
-- ============================================================================


-- ============================================================================
-- Payment-event quality reconciliation
-- ============================================================================

SELECT
    (
        SELECT COUNT(*)
        FROM payments_dev.silver.payment_events_standardized
    ) AS standardized_records,

    (
        SELECT COUNT(*)
        FROM payments_dev.silver.payment_events_validated
    ) AS validated_records,

    (
        SELECT COUNT(*)
        FROM payments_dev.silver.payment_events_quarantine
    ) AS quarantined_records;


-- Expected:
--
-- standardized_records
-- =
-- validated_records + quarantined_records


-- ============================================================================
-- Payment-transaction quality reconciliation
-- ============================================================================

SELECT
    (
        SELECT COUNT(*)
        FROM payments_dev.silver.payment_transactions
    ) AS standardized_transactions,

    (
        SELECT COUNT(*)
        FROM payments_dev.silver.payment_transactions_validated
    ) AS validated_transactions,

    (
        SELECT COUNT(*)
        FROM payments_dev.silver.payment_transactions_quarantine
    ) AS quarantined_transactions;


-- ============================================================================
-- Event duplicates remain intentionally present
-- ============================================================================

SELECT
    COUNT(*) AS physical_records,

    COUNT(DISTINCT event_id)
        AS distinct_business_events,

    COUNT(*) - COUNT(DISTINCT event_id)
        AS additional_physical_deliveries

FROM payments_dev.silver.payment_events_validated;


-- ============================================================================
-- Inspect event quarantine
-- ============================================================================

SELECT
    event_id,
    transaction_id,
    amount,
    currency,
    event_type,
    transaction_status,
    parse_status,
    dq_status,
    dq_failed_rules,
    dq_checked_at

FROM payments_dev.silver.payment_events_quarantine

ORDER BY dq_checked_at DESC;


-- ============================================================================
-- Inspect transaction quarantine
-- ============================================================================

SELECT
    transaction_id,
    account_id,
    merchant_id,
    amount,
    currency,
    channel,
    payment_method,
    transaction_status,
    dq_status,
    dq_failed_rules,
    dq_checked_at

FROM payments_dev.silver.payment_transactions_quarantine

ORDER BY dq_checked_at DESC;