-- ============================================================================
-- EPIP M17C — DATA QUALITY AND EVENT TRUST MONITORING
-- ============================================================================

-- ============================================================================
-- VIEW 1 — LAKEFLOW EXPECTATION METRICS
-- ============================================================================

CREATE OR REPLACE VIEW payments_dev.monitoring.lakeflow_expectation_metrics
COMMENT 'Lakeflow expectation pass/fail metrics parsed from the Silver pipeline event log.'
AS

WITH expectation_events AS (
    SELECT
        timestamp AS event_timestamp,
        origin.update_id AS update_id,
        origin.flow_name AS flow_name,

        EXPLODE(
            FROM_JSON(
                details:flow_progress.data_quality.expectations,
                'array<struct<
                    name:string,
                    dataset:string,
                    passed_records:bigint,
                    failed_records:bigint
                >>'
            )
        ) AS expectation

    FROM event_log(
        TABLE(payments_dev.silver.payment_events_validated)
    )

    WHERE event_type = 'flow_progress'
      AND details:flow_progress.data_quality.expectations IS NOT NULL
),

aggregated AS (
    SELECT
        CAST(event_timestamp AS DATE) AS metric_date,
        update_id,
        flow_name,
        expectation.dataset AS dataset_name,
        expectation.name AS expectation_name,
        SUM(COALESCE(expectation.passed_records, 0)) AS passed_records,
        SUM(COALESCE(expectation.failed_records, 0)) AS failed_records,
        MIN(event_timestamp) AS first_metric_at,
        MAX(event_timestamp) AS latest_metric_at

    FROM expectation_events

    GROUP BY
        CAST(event_timestamp AS DATE),
        update_id,
        flow_name,
        expectation.dataset,
        expectation.name
)

SELECT
    metric_date,
    update_id,
    flow_name,
    dataset_name,
    expectation_name,
    passed_records,
    failed_records,
    passed_records + failed_records AS evaluated_records,

    CASE
        WHEN passed_records + failed_records = 0 THEN 1.0
        ELSE 1.0 * passed_records / (passed_records + failed_records)
    END AS pass_rate,

    CASE
        WHEN passed_records + failed_records = 0 THEN 0.0
        ELSE 1.0 * failed_records / (passed_records + failed_records)
    END AS failure_rate,

    CASE
        WHEN failed_records > 0 THEN 'FAILED_RECORDS_PRESENT'
        ELSE 'PASS'
    END AS expectation_status,

    first_metric_at,
    latest_metric_at

FROM aggregated;


-- ============================================================================
-- VIEW 2 — DAILY QUARANTINE SUMMARY
-- ============================================================================

CREATE OR REPLACE VIEW payments_dev.monitoring.dq_quarantine_daily
COMMENT 'Daily EPIP Silver quarantine volumes and failed-rule counts.'
AS

SELECT
    'payment_events' AS dataset_name,
    CAST(dq_checked_at AS DATE) AS quality_date,
    COUNT(*) AS quarantined_records,
    SUM(SIZE(dq_failed_rules)) AS failed_rule_occurrences,
    MIN(dq_checked_at) AS first_quarantine_at,
    MAX(dq_checked_at) AS latest_quarantine_at

FROM payments_dev.silver.payment_events_quarantine

GROUP BY CAST(dq_checked_at AS DATE)

UNION ALL

SELECT
    'payment_transactions' AS dataset_name,
    CAST(dq_checked_at AS DATE) AS quality_date,
    COUNT(*) AS quarantined_records,
    SUM(SIZE(dq_failed_rules)) AS failed_rule_occurrences,
    MIN(dq_checked_at) AS first_quarantine_at,
    MAX(dq_checked_at) AS latest_quarantine_at

FROM payments_dev.silver.payment_transactions_quarantine

GROUP BY CAST(dq_checked_at AS DATE);


-- ============================================================================
-- VIEW 3 — QUARANTINE RULE BREAKDOWN
-- ============================================================================

CREATE OR REPLACE VIEW payments_dev.monitoring.dq_quarantine_rule_metrics
COMMENT 'Daily count of individual EPIP DQ rules causing Silver quarantine.'
AS

WITH event_rule_failures AS (
    SELECT
        CAST(q.dq_checked_at AS DATE) AS quality_date,
        'payment_events' AS dataset_name,
        failed_rule

    FROM payments_dev.silver.payment_events_quarantine AS q
    LATERAL VIEW EXPLODE(q.dq_failed_rules) exploded AS failed_rule
),

transaction_rule_failures AS (
    SELECT
        CAST(q.dq_checked_at AS DATE) AS quality_date,
        'payment_transactions' AS dataset_name,
        failed_rule

    FROM payments_dev.silver.payment_transactions_quarantine AS q
    LATERAL VIEW EXPLODE(q.dq_failed_rules) exploded AS failed_rule
),

all_failures AS (
    SELECT * FROM event_rule_failures
    UNION ALL
    SELECT * FROM transaction_rule_failures
)

SELECT
    quality_date,
    dataset_name,
    failed_rule,
    COUNT(*) AS failed_record_count

FROM all_failures

GROUP BY
    quality_date,
    dataset_name,
    failed_rule;


-- ============================================================================
-- VIEW 4 — PAYMENT EVENT EXCEPTION HEALTH
-- ============================================================================

CREATE OR REPLACE VIEW payments_dev.monitoring.payment_event_exception_health
COMMENT 'Daily duplicate, late and out-of-order event-delivery anomaly metrics.'
AS

SELECT
    CAST(event_timestamp AS DATE) AS event_date,

    COUNT(*) AS exception_occurrence_count,
    COUNT(DISTINCT event_id) AS distinct_exception_event_count,
    COUNT(DISTINCT transaction_id) AS affected_transaction_count,

    SUM(CASE WHEN is_duplicate_event THEN 1 ELSE 0 END)
        AS duplicate_occurrence_count,

    COUNT(
        DISTINCT CASE
            WHEN is_duplicate_event THEN event_id
            ELSE NULL
        END
    ) AS duplicate_event_count,

    SUM(CASE WHEN is_late_arrival THEN 1 ELSE 0 END)
        AS late_occurrence_count,

    COUNT(
        DISTINCT CASE
            WHEN is_late_arrival THEN event_id
            ELSE NULL
        END
    ) AS late_event_count,

    SUM(CASE WHEN is_out_of_order THEN 1 ELSE 0 END)
        AS out_of_order_occurrence_count,

    COUNT(
        DISTINCT CASE
            WHEN is_out_of_order THEN event_id
            ELSE NULL
        END
    ) AS out_of_order_event_count,

    MAX(exception_evaluated_at) AS latest_exception_evaluated_at

FROM payments_dev.silver.payment_event_exceptions

GROUP BY CAST(event_timestamp AS DATE);

CREATE OR REPLACE VIEW payments_dev.monitoring.dq_current_health
COMMENT 'Current EPIP DQ health summary including explicit zero-quarantine states.'
AS

WITH monitored_datasets AS (

    SELECT 'payment_events' AS dataset_name

    UNION ALL

    SELECT 'payment_transactions'
),

quarantine_counts AS (

    SELECT
        'payment_events' AS dataset_name,
        COUNT(*) AS quarantined_records,
        MAX(dq_checked_at) AS latest_quarantine_at

    FROM payments_dev.silver.payment_events_quarantine

    UNION ALL

    SELECT
        'payment_transactions' AS dataset_name,
        COUNT(*) AS quarantined_records,
        MAX(dq_checked_at) AS latest_quarantine_at

    FROM payments_dev.silver.payment_transactions_quarantine
)

SELECT
    monitored.dataset_name,

    COALESCE(
        quarantine.quarantined_records,
        0
    ) AS quarantined_records,

    quarantine.latest_quarantine_at,

    CASE
        WHEN COALESCE(
            quarantine.quarantined_records,
            0
        ) = 0
        THEN 'HEALTHY'

        ELSE 'ATTENTION'
    END AS dq_status

FROM monitored_datasets AS monitored

LEFT JOIN quarantine_counts AS quarantine
    ON monitored.dataset_name = quarantine.dataset_name;
