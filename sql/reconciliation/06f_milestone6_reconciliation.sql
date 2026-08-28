-- ============================================================================
-- EPIP Milestone 6 Final Reconciliation
--
-- Covers:
--   6A Data Quality
--   6B Streaming Event Trust
--   6C CDC Ingestion
--   6D AUTO CDC / SCD1 / SCD2
--   6E Trusted Enrichment
--   Gold reconciliation
-- ============================================================================


-- ============================================================================
-- 1. DATA QUALITY — PAYMENT EVENTS
-- ============================================================================

SELECT
    'EVENT_DQ_RECONCILIATION' AS validation,

    standardized_records,
    validated_records,
    quarantined_records,

    CASE
        WHEN standardized_records =
             validated_records + quarantined_records
        THEN 'PASS'
        ELSE 'FAIL'
    END AS status

FROM (
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
        ) AS quarantined_records
);


-- ============================================================================
-- 2. DATA QUALITY — PAYMENT TRANSACTIONS
-- ============================================================================

SELECT
    'TRANSACTION_DQ_RECONCILIATION' AS validation,

    standardized_records,
    validated_records,
    quarantined_records,

    CASE
        WHEN standardized_records =
             validated_records + quarantined_records
        THEN 'PASS'
        ELSE 'FAIL'
    END AS status

FROM (
    SELECT
        (
            SELECT COUNT(*)
            FROM payments_dev.silver.payment_transactions
        ) AS standardized_records,

        (
            SELECT COUNT(*)
            FROM payments_dev.silver.payment_transactions_validated
        ) AS validated_records,

        (
            SELECT COUNT(*)
            FROM payments_dev.silver.payment_transactions_quarantine
        ) AS quarantined_records
);


-- ============================================================================
-- 3. STREAMING TRUST — NO DUPLICATE EVENT IDs
-- ============================================================================

SELECT
    'TRUSTED_EVENT_UNIQUENESS' AS validation,

    COUNT(*) AS trusted_records,

    COUNT(DISTINCT event_id) AS distinct_event_ids,

    CASE
        WHEN COUNT(*) = COUNT(DISTINCT event_id)
        THEN 'PASS'
        ELSE 'FAIL'
    END AS status

FROM payments_dev.silver.payment_events_trusted;


-- ============================================================================
-- 4. STREAMING TRUST — PHYSICAL VS BUSINESS EVENTS
-- ============================================================================

SELECT
    'EVENT_DEDUPLICATION' AS validation,

    (
        SELECT COUNT(*)
        FROM payments_dev.silver.payment_events_validated
    ) AS physical_validated_records,

    (
        SELECT COUNT(DISTINCT event_id)
        FROM payments_dev.silver.payment_events_validated
    ) AS distinct_business_events,

    (
        SELECT COUNT(*)
        FROM payments_dev.silver.payment_events_trusted
    ) AS trusted_business_events;


-- ============================================================================
-- 5. STREAMING EXCEPTION SUMMARY
-- ============================================================================

SELECT
    CASE
        WHEN is_duplicate_event THEN 'DUPLICATE'
        ELSE 'NON_DUPLICATE'
    END AS duplicate_status,

    CASE
        WHEN is_late_arrival THEN 'LATE'
        ELSE 'ON_TIME'
    END AS lateness_status,

    CASE
        WHEN is_out_of_order THEN 'OUT_OF_ORDER'
        ELSE 'ORDERED'
    END AS ordering_status,

    COUNT(*) AS exception_occurrences

FROM payments_dev.silver.payment_event_exceptions

GROUP BY
    is_duplicate_event,
    is_late_arrival,
    is_out_of_order

ORDER BY exception_occurrences DESC;


-- ============================================================================
-- 6. SPECIFIC 4-HOUR LATE SCENARIO
-- ============================================================================

SELECT
    event_id,
    transaction_id,
    delivery_scenario,
    simulated_delivery_delay_seconds,
    is_late_arrival,
    exception_types,

    CASE
        WHEN is_late_arrival = true
             AND simulated_delivery_delay_seconds >= 14400
        THEN 'PASS'
        ELSE 'CHECK'
    END AS validation_status

FROM payments_dev.silver.payment_event_exceptions

WHERE delivery_scenario = 'LATE';


-- ============================================================================
-- 7. OUT-OF-ORDER SCENARIO
-- ============================================================================

SELECT
    transaction_id,
    event_id,
    event_type,
    sequence_number,
    previous_max_sequence_number,
    delivery_scenario,
    is_out_of_order,
    exception_types

FROM payments_dev.silver.payment_event_exceptions

WHERE is_out_of_order = true

ORDER BY
    transaction_id,
    delivery_order_timestamp;


-- ============================================================================
-- 8. CUSTOMER DELETE MUST WIN OVER LATE VERSION 2
--
-- Synthetic physical arrival:
--
--     version 1
--     version 3 DELETE
--     version 2 UPDATE
--
-- Logical result:
--
--     version 1 -> version 2 -> version 3 DELETE
--
-- cust-000001 therefore must NOT exist in customers_current.
-- ============================================================================

SELECT
    'DELETED_CUSTOMER_NOT_RESURRECTED' AS validation,

    COUNT(*) AS current_record_count,

    CASE
        WHEN COUNT(*) = 0
        THEN 'PASS'
        ELSE 'FAIL'
    END AS status

FROM payments_dev.silver.customers_current

WHERE customer_id = 'cust-000001';


-- ============================================================================
-- 9. CUSTOMER SCD2 HISTORY
-- ============================================================================

SELECT
    customer_id,
    record_version,
    city,
    state,
    source_updated_at,
    __START_AT,
    __END_AT

FROM payments_dev.silver.customer_history

WHERE customer_id = 'cust-000001'

ORDER BY __START_AT;


-- ============================================================================
-- 10. ACCOUNT SCD1 CURRENT STATE
-- ============================================================================

SELECT
    'ACCOUNT_CDC_CURRENT_STATE' AS validation,

    account_id,
    account_status,
    record_version,

    CASE
        WHEN account_status = 'BLOCKED'
             AND record_version = 2
        THEN 'PASS'
        ELSE 'FAIL'
    END AS status

FROM payments_dev.silver.accounts_current

WHERE account_id = 'acct-000001';


-- ============================================================================
-- 11. ACCOUNT SCD2 HISTORY
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
-- 12. MERCHANT SCD1 CURRENT STATE
-- ============================================================================

SELECT
    'MERCHANT_CDC_CURRENT_STATE' AS validation,

    merchant_id,
    merchant_risk_rating,
    merchant_status,
    record_version,

    CASE
        WHEN merchant_risk_rating = 'HIGH'
             AND merchant_status = 'SUSPENDED'
             AND record_version = 2
        THEN 'PASS'
        ELSE 'FAIL'
    END AS status

FROM payments_dev.silver.merchants_current

WHERE merchant_id = 'merchant-000001';


-- ============================================================================
-- 13. MERCHANT SCD2 HISTORY
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
-- 14. SCD1 CURRENT VS ACTIVE SCD2
-- ============================================================================

SELECT
    'CUSTOMER_CURRENT_VS_HISTORY' AS validation,

    current_records,
    active_history_records,

    CASE
        WHEN current_records = active_history_records
        THEN 'PASS'
        ELSE 'FAIL'
    END AS status

FROM (
    SELECT
        (
            SELECT COUNT(*)
            FROM payments_dev.silver.customers_current
        ) AS current_records,

        (
            SELECT COUNT(*)
            FROM payments_dev.silver.customer_history
            WHERE __END_AT IS NULL
        ) AS active_history_records
);


SELECT
    'ACCOUNT_CURRENT_VS_HISTORY' AS validation,

    current_records,
    active_history_records,

    CASE
        WHEN current_records = active_history_records
        THEN 'PASS'
        ELSE 'FAIL'
    END AS status

FROM (
    SELECT
        (
            SELECT COUNT(*)
            FROM payments_dev.silver.accounts_current
        ) AS current_records,

        (
            SELECT COUNT(*)
            FROM payments_dev.silver.account_history
            WHERE __END_AT IS NULL
        ) AS active_history_records
);


SELECT
    'MERCHANT_CURRENT_VS_HISTORY' AS validation,

    current_records,
    active_history_records,

    CASE
        WHEN current_records = active_history_records
        THEN 'PASS'
        ELSE 'FAIL'
    END AS status

FROM (
    SELECT
        (
            SELECT COUNT(*)
            FROM payments_dev.silver.merchants_current
        ) AS current_records,

        (
            SELECT COUNT(*)
            FROM payments_dev.silver.merchant_history
            WHERE __END_AT IS NULL
        ) AS active_history_records
);


-- ============================================================================
-- 15. VALIDATED TRANSACTIONS -> ENRICHED TRANSACTIONS
-- ============================================================================

SELECT
    'VALIDATED_TO_ENRICHED_COUNT' AS validation,

    validated_count,
    enriched_count,

    CASE
        WHEN validated_count = enriched_count
        THEN 'PASS'
        ELSE 'FAIL'
    END AS status

FROM (
    SELECT
        (
            SELECT COUNT(*)
            FROM payments_dev.silver.payment_transactions_validated
        ) AS validated_count,

        (
            SELECT COUNT(*)
            FROM payments_dev.silver.payment_transactions_enriched
        ) AS enriched_count
);


-- ============================================================================
-- 16. DIMENSION MATCH OBSERVABILITY
--
-- Missing customers are not automatically errors after CDC.
-- A legitimately deleted current-state customer can make historical
-- transactions unmatched against the current-state customer dimension.
-- ============================================================================

SELECT
    COUNT(*) AS enriched_transactions,

    SUM(
        CASE
            WHEN account_dimension_match = false
            THEN 1
            ELSE 0
        END
    ) AS missing_account_matches,

    SUM(
        CASE
            WHEN customer_dimension_match = false
            THEN 1
            ELSE 0
        END
    ) AS missing_customer_matches,

    SUM(
        CASE
            WHEN merchant_dimension_match = false
            THEN 1
            ELSE 0
        END
    ) AS missing_merchant_matches

FROM payments_dev.silver.payment_transactions_enriched;


-- ============================================================================
-- 17. GOLD DAILY TRANSACTION COUNT RECONCILIATION
-- ============================================================================

SELECT
    'SILVER_TO_GOLD_TRANSACTION_COUNT' AS validation,

    silver_count,
    gold_count,

    CASE
        WHEN silver_count = gold_count
        THEN 'PASS'
        ELSE 'FAIL'
    END AS status

FROM (
    SELECT
        (
            SELECT COUNT(*)
            FROM payments_dev.silver.payment_transactions_enriched
        ) AS silver_count,

        (
            SELECT COALESCE(
                SUM(transaction_count),
                0
            )
            FROM payments_dev.gold.daily_payment_metrics
        ) AS gold_count
);


-- ============================================================================
-- 18. GOLD PAYMENT AMOUNT RECONCILIATION
-- ============================================================================

SELECT
    'SILVER_TO_GOLD_PAYMENT_AMOUNT' AS validation,

    silver_amount,
    gold_amount,

    CASE
        WHEN silver_amount = gold_amount
        THEN 'PASS'
        ELSE 'FAIL'
    END AS status

FROM (
    SELECT
        (
            SELECT ROUND(
                COALESCE(SUM(amount), 0),
                2
            )
            FROM payments_dev.silver.payment_transactions_enriched
        ) AS silver_amount,

        (
            SELECT ROUND(
                COALESCE(SUM(total_payment_amount), 0),
                2
            )
            FROM payments_dev.gold.daily_payment_metrics
        ) AS gold_amount
);


-- ============================================================================
-- 19. GOLD FRAUD COUNT RECONCILIATION
-- ============================================================================

SELECT
    'SILVER_TO_GOLD_FRAUD_CASE_COUNT' AS validation,

    silver_fraud_cases,
    gold_fraud_cases,

    CASE
        WHEN silver_fraud_cases = gold_fraud_cases
        THEN 'PASS'
        ELSE 'FAIL'
    END AS status

FROM (
    SELECT
        (
            SELECT COUNT(*)
            FROM payments_dev.silver.payment_transactions_enriched
            WHERE has_fraud_case = true
        ) AS silver_fraud_cases,

        (
            SELECT COALESCE(
                SUM(fraud_case_transactions),
                0
            )
            FROM payments_dev.gold.fraud_operations_metrics
        ) AS gold_fraud_cases
);