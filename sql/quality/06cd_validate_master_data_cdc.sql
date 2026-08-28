-- ============================================================================
-- EPIP Milestone 6C + 6D
-- AUTO CDC / SCD Type 1 / SCD Type 2 validation
-- ============================================================================


-- ============================================================================
-- 1. Customer current-state count
--
-- One baseline customer is deleted by the CDC scenario.
-- ============================================================================

SELECT
    (
        SELECT COUNT(*)
        FROM payments_dev.ingestion.customers_snapshot
    ) AS snapshot_customers,

    (
        SELECT COUNT(*)
        FROM payments_dev.silver.customers_current
    ) AS current_customers;


-- Expected:
-- current_customers = snapshot_customers - 1


-- ============================================================================
-- 2. Deleted customer must not be resurrected
-- ============================================================================

SELECT *

FROM payments_dev.silver.customers_current

WHERE customer_id = 'cust-000001';


-- Expected:
-- zero rows


-- ============================================================================
-- 3. Customer SCD Type 2 history
-- ============================================================================

SELECT
    customer_id,
    record_version,
    address_line_1,
    city,
    state,
    __START_AT,
    __END_AT

FROM payments_dev.silver.customer_history

WHERE customer_id = 'cust-000001'

ORDER BY __START_AT;


-- Expected logical history:
--
-- v1 -> v2
-- v2 -> v3 delete


-- ============================================================================
-- 4. Current vs active customer-history reconciliation
-- ============================================================================

SELECT
    (
        SELECT COUNT(*)
        FROM payments_dev.silver.customers_current
    ) AS current_customers,

    (
        SELECT COUNT(*)
        FROM payments_dev.silver.customer_history
        WHERE __END_AT IS NULL
    ) AS active_history_customers;


-- Expected:
-- equal


-- ============================================================================
-- 5. Account SCD Type 1
-- ============================================================================

SELECT
    account_id,
    customer_id,
    account_status,
    record_version

FROM payments_dev.silver.accounts_current

WHERE account_id = 'acct-000001';


-- Expected:
-- BLOCKED / version 2


-- ============================================================================
-- 6. Account SCD Type 2
-- ============================================================================

SELECT
    account_id,
    account_status,
    record_version,
    __START_AT,
    __END_AT

FROM payments_dev.silver.account_history

WHERE account_id = 'acct-000001'

ORDER BY __START_AT;


-- ============================================================================
-- 7. Merchant SCD Type 1
-- ============================================================================

SELECT
    merchant_id,
    merchant_risk_rating,
    merchant_status,
    record_version

FROM payments_dev.silver.merchants_current

WHERE merchant_id = 'merchant-000001';


-- Expected:
-- HIGH / SUSPENDED / version 2


-- ============================================================================
-- 8. Merchant SCD Type 2
-- ============================================================================

SELECT
    merchant_id,
    merchant_risk_rating,
    merchant_status,
    record_version,
    __START_AT,
    __END_AT

FROM payments_dev.silver.merchant_history

WHERE merchant_id = 'merchant-000001'

ORDER BY __START_AT;


-- ============================================================================
-- 9. Current vs active history reconciliation
-- ============================================================================

SELECT
    (
        SELECT COUNT(*)
        FROM payments_dev.silver.accounts_current
    ) AS current_accounts,

    (
        SELECT COUNT(*)
        FROM payments_dev.silver.account_history
        WHERE __END_AT IS NULL
    ) AS active_account_history,

    (
        SELECT COUNT(*)
        FROM payments_dev.silver.merchants_current
    ) AS current_merchants,

    (
        SELECT COUNT(*)
        FROM payments_dev.silver.merchant_history
        WHERE __END_AT IS NULL
    ) AS active_merchant_history;


-- ============================================================================
-- 10. Enrichment now uses AUTO CDC current state
-- ============================================================================

SELECT
    COUNT(*) AS transactions,

    SUM(
        CASE
            WHEN account_dimension_match = false
            THEN 1
            ELSE 0
        END
    ) AS missing_accounts,

    SUM(
        CASE
            WHEN customer_dimension_match = false
            THEN 1
            ELSE 0
        END
    ) AS missing_customers,

    SUM(
        CASE
            WHEN merchant_dimension_match = false
            THEN 1
            ELSE 0
        END
    ) AS missing_merchants

FROM payments_dev.silver.payment_transactions_enriched;