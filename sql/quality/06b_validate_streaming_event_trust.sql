-- ============================================================================
-- EPIP Milestone 6 / Step 6B
-- Streaming Event Trust Validation
-- ============================================================================


-- ============================================================================
-- 1. Physical -> validated -> trusted reconciliation
-- ============================================================================

SELECT
    (
        SELECT COUNT(*)
        FROM payments_dev.silver.payment_events_validated
    ) AS validated_physical_records,

    (
        SELECT COUNT(DISTINCT event_id)
        FROM payments_dev.silver.payment_events_validated
    ) AS distinct_business_events,

    (
        SELECT COUNT(*)
        FROM payments_dev.silver.payment_events_trusted
    ) AS trusted_records;


-- ============================================================================
-- 2. Trusted table must contain at most one row per event_id
-- ============================================================================

SELECT
    event_id,
    COUNT(*) AS trusted_count

FROM payments_dev.silver.payment_events_trusted

GROUP BY event_id

HAVING COUNT(*) > 1;


-- Expected:
-- zero rows


-- ============================================================================
-- 3. Duplicate delivery audit
-- ============================================================================

SELECT
    event_id,
    transaction_id,
    physical_delivery_count,
    observed_delivery_scenarios,
    observed_kafka_offsets,
    exception_types

FROM payments_dev.silver.payment_event_exceptions

WHERE is_duplicate_event = true

ORDER BY physical_delivery_count DESC;


-- ============================================================================
-- 4. Late event audit
-- ============================================================================

SELECT
    event_id,
    transaction_id,

    event_timestamp,
    simulated_arrival_at,

    simulated_delivery_delay_seconds,

    is_late_arrival,
    exception_types

FROM payments_dev.silver.payment_event_exceptions

WHERE is_late_arrival = true

ORDER BY simulated_delivery_delay_seconds DESC;


-- ============================================================================
-- 5. Out-of-order lifecycle audit
-- ============================================================================

SELECT
    transaction_id,

    event_id,
    event_type,

    sequence_number,
    previous_max_sequence_number,

    event_timestamp,
    delivery_order_timestamp,

    exception_types

FROM payments_dev.silver.payment_event_exceptions

WHERE is_out_of_order = true

ORDER BY
    transaction_id,
    delivery_order_timestamp;


-- ============================================================================
-- 6. Exception summary
-- ============================================================================

SELECT
    is_duplicate_event,
    is_late_arrival,
    is_out_of_order,

    COUNT(*) AS business_events

FROM payments_dev.silver.payment_event_exceptions

GROUP BY
    is_duplicate_event,
    is_late_arrival,
    is_out_of_order

ORDER BY business_events DESC;


-- ============================================================================
-- 7. Trusted arrival classification
-- ============================================================================

SELECT
    event_arrival_classification,
    COUNT(*) AS event_count

FROM payments_dev.silver.payment_events_trusted

GROUP BY event_arrival_classification

ORDER BY event_arrival_classification;


-- ============================================================================
-- 8. Logical transaction lifecycle
-- ============================================================================

SELECT
    transaction_id,
    event_id,
    event_type,
    sequence_number,
    event_timestamp,
    event_arrival_classification

FROM payments_dev.silver.payment_events_trusted

ORDER BY
    transaction_id,
    sequence_number,
    event_timestamp;