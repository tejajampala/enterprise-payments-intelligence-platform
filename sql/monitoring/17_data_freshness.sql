-- ============================================================================
-- EPIP M17C — DATA FRESHNESS MONITORING
-- ============================================================================
--
-- EPIP uses synthetic historical business timestamps. Operational freshness
-- therefore must not be derived only from event_timestamp/event_date.
--
-- We expose:
--
-- latest_business_time
--   newest business/event timestamp in the dataset
--
-- latest_observed_at
--   newest processing/quality/trust timestamp
--
-- Demo thresholds:
--   <= 24 hours  → RECENT
--   <= 7 days    → AGING
--   > 7 days     → STALE
--
-- These are portfolio defaults, not production banking SLAs.
-- ============================================================================

CREATE OR REPLACE VIEW payments_dev.monitoring.data_freshness_health
COMMENT 'Operational and business-time freshness for core EPIP Silver and Gold data products.'
AS

WITH freshness_sources AS (

    SELECT
        'payments_dev.silver.payment_events_trusted' AS dataset_name,
        'SILVER_STREAMING' AS dataset_type,

        MAX(event_timestamp) AS latest_business_time,
        MAX(bronze_ingested_at) AS latest_source_ingested_at,
        MAX(trusted_at) AS latest_observed_at,

        COUNT(*) AS record_count

    FROM payments_dev.silver.payment_events_trusted

    UNION ALL

    SELECT
        'payments_dev.silver.payment_transactions_validated',
        'SILVER_BATCH',

        MAX(event_timestamp),
        MAX(bronze_ingested_at),
        MAX(dq_checked_at),

        COUNT(*)

    FROM payments_dev.silver.payment_transactions_validated

    UNION ALL

    SELECT
        'payments_dev.gold.daily_payment_metrics',
        'GOLD_MATERIALIZED_VIEW',

        MAX(CAST(event_date AS TIMESTAMP)),
        MAX(latest_silver_processed_at),
        MAX(latest_silver_processed_at),

        COALESCE(SUM(transaction_count), 0)

    FROM payments_dev.gold.daily_payment_metrics
)

SELECT
    dataset_name,
    dataset_type,

    latest_business_time,
    latest_source_ingested_at,
    latest_observed_at,

    record_count,

    CASE
        WHEN latest_observed_at IS NULL THEN NULL
        ELSE TIMESTAMPDIFF(
            MINUTE,
            latest_observed_at,
            CURRENT_TIMESTAMP()
        )
    END AS processing_age_minutes,

    CASE
        WHEN latest_business_time IS NULL THEN NULL
        ELSE TIMESTAMPDIFF(
            HOUR,
            latest_business_time,
            CURRENT_TIMESTAMP()
        )
    END AS business_time_age_hours,

    CASE
        WHEN record_count = 0 OR latest_observed_at IS NULL
            THEN 'NO_DATA'

        WHEN latest_observed_at >= CURRENT_TIMESTAMP() - INTERVAL 24 HOURS
            THEN 'RECENT'

        WHEN latest_observed_at >= CURRENT_TIMESTAMP() - INTERVAL 7 DAYS
            THEN 'AGING'

        ELSE 'STALE'
    END AS freshness_status

FROM freshness_sources;
