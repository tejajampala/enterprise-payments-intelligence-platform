-- ============================================================================
-- EPIP M17D — CONSOLIDATED OPERATIONS SUMMARY AND ALERT CANDIDATES
-- ============================================================================


-- ============================================================================
-- VIEW 1 — CURRENT DQ HEALTH WITH ZERO-FAILURE STATES
-- ============================================================================

CREATE OR REPLACE VIEW payments_dev.monitoring.dq_current_health
COMMENT 'Current EPIP DQ summary that returns explicit HEALTHY zero-quarantine states.'
AS

WITH dataset_health AS (

    SELECT
        'payment_events' AS dataset_name,

        (
            SELECT COUNT(*)
            FROM payments_dev.silver.payment_events_validated
        ) AS valid_records,

        (
            SELECT COUNT(*)
            FROM payments_dev.silver.payment_events_quarantine
        ) AS quarantined_records,

        (
            SELECT MAX(dq_checked_at)
            FROM payments_dev.silver.payment_events_quarantine
        ) AS latest_quarantine_at

    UNION ALL

    SELECT
        'payment_transactions',

        (
            SELECT COUNT(*)
            FROM payments_dev.silver.payment_transactions_validated
        ),

        (
            SELECT COUNT(*)
            FROM payments_dev.silver.payment_transactions_quarantine
        ),

        (
            SELECT MAX(dq_checked_at)
            FROM payments_dev.silver.payment_transactions_quarantine
        )
)

SELECT
    dataset_name,
    valid_records,
    quarantined_records,

    valid_records + quarantined_records
        AS evaluated_records,

    CASE
        WHEN valid_records + quarantined_records = 0
            THEN NULL

        ELSE
            1.0 * quarantined_records
            / (valid_records + quarantined_records)
    END AS quarantine_rate,

    latest_quarantine_at,

    CASE
        WHEN valid_records + quarantined_records = 0
            THEN 'NO_DATA'

        WHEN quarantined_records = 0
            THEN 'HEALTHY'

        ELSE 'ATTENTION'
    END AS dq_status

FROM dataset_health;


-- ============================================================================
-- VIEW 2 — PLATFORM OPERATIONS SUMMARY
-- ============================================================================

CREATE OR REPLACE VIEW payments_dev.monitoring.platform_operations_summary
COMMENT 'Single-row EPIP operational summary for the Platform Operations & Cost dashboard.'
AS

SELECT
    (
        SELECT COUNT(*)
        FROM payments_dev.monitoring.pipeline_operational_health
    ) AS total_pipelines,

    (
        SELECT COUNT(*)
        FROM payments_dev.monitoring.pipeline_operational_health
        WHERE operational_status = 'HEALTHY'
    ) AS healthy_pipelines,

    (
        SELECT COUNT(*)
        FROM payments_dev.monitoring.pipeline_operational_health
        WHERE operational_status = 'FAILED'
    ) AS failed_pipelines,

    (
        SELECT COUNT(*)
        FROM payments_dev.monitoring.pipeline_operational_health
        WHERE operational_status = 'NEVER_RUN'
    ) AS never_run_pipelines,

    (
        SELECT COUNT(*)
        FROM payments_dev.monitoring.job_operational_health
    ) AS total_jobs,

    (
        SELECT COUNT(*)
        FROM payments_dev.monitoring.epip_job_run_health
        WHERE run_start_time >= CURRENT_TIMESTAMP() - INTERVAL 24 HOURS
          AND result_state IN (
              'FAILED',
              'CANCELLED',
              'TIMED_OUT',
              'ERROR',
              'BLOCKED'
          )
    ) AS failed_jobs_24h,

    (
        SELECT COUNT(*)
        FROM payments_dev.monitoring.epip_job_task_run_health
        WHERE task_start_time >= CURRENT_TIMESTAMP() - INTERVAL 24 HOURS
          AND result_state IN (
              'FAILED',
              'CANCELLED',
              'TIMED_OUT',
              'ERROR',
              'BLOCKED'
          )
    ) AS failed_tasks_24h,

    (
        SELECT COUNT(*)
        FROM payments_dev.monitoring.epip_query_performance
        WHERE start_time >= CURRENT_TIMESTAMP() - INTERVAL 24 HOURS
          AND execution_status IN ('FAILED', 'CANCELED')
    ) AS failed_queries_24h,

    (
        SELECT COUNT(*)
        FROM payments_dev.monitoring.data_freshness_health
        WHERE freshness_status IN ('STALE', 'NO_DATA')
    ) AS stale_or_missing_datasets,

    (
        SELECT COUNT(*)
        FROM payments_dev.monitoring.dq_current_health
        WHERE dq_status = 'ATTENTION'
    ) AS dq_attention_datasets,

    (
        SELECT COUNT(*)
        FROM payments_dev.monitoring.epip_security_events
        WHERE event_time >= CURRENT_TIMESTAMP() - INTERVAL 24 HOURS
          AND event_severity IN ('HIGH', 'CRITICAL')
    ) AS high_security_events_24h,

    (
        SELECT overall_pass
        FROM payments_dev.monitoring.agent_latest_health
        LIMIT 1
    ) AS latest_agent_overall_pass,

    (
        SELECT pass_rate
        FROM payments_dev.monitoring.agent_latest_health
        LIMIT 1
    ) AS latest_agent_pass_rate,

    (
        SELECT safety_rate
        FROM payments_dev.monitoring.agent_latest_health
        LIMIT 1
    ) AS latest_agent_safety_rate,

    (
        SELECT scoring_age_hours
        FROM payments_dev.monitoring.fraud_model_current_health
        LIMIT 1
    ) AS fraud_scoring_age_hours,

    (
        SELECT COALESCE(SUM(estimated_list_cost), 0)
        FROM payments_dev.monitoring.databricks_cost_daily
        WHERE usage_date = CURRENT_DATE()
    ) AS databricks_list_cost_today,

    (
        SELECT COALESCE(SUM(estimated_list_cost), 0)
        FROM payments_dev.monitoring.databricks_cost_daily
        WHERE usage_date >= CURRENT_DATE() - INTERVAL 6 DAYS
    ) AS databricks_list_cost_7d;


-- ============================================================================
-- VIEW 3 — ALERT CANDIDATES
-- ============================================================================
--
-- These rows are consumed by paused SQL alerts in the bundle.
--
-- The cost rule is a demo anomaly heuristic:
-- today's list cost > 2x the previous 7-day daily average AND > 1 currency unit.
-- It is not a production financial budget policy.
-- ============================================================================

CREATE OR REPLACE VIEW payments_dev.monitoring.operations_alert_candidates
COMMENT 'EPIP operational alert conditions used by paused SQL alert resources.'
AS

WITH cost_stats AS (
    SELECT
        (
            SELECT COALESCE(SUM(estimated_list_cost), 0)
            FROM payments_dev.monitoring.databricks_cost_daily
            WHERE usage_date = CURRENT_DATE()
        ) AS today_cost,

        (
            SELECT AVG(daily_cost)
            FROM (
                SELECT
                    usage_date,
                    SUM(estimated_list_cost) AS daily_cost

                FROM payments_dev.monitoring.databricks_cost_daily

                WHERE usage_date BETWEEN
                      CURRENT_DATE() - INTERVAL 7 DAYS
                      AND CURRENT_DATE() - INTERVAL 1 DAY

                GROUP BY usage_date
            )
        ) AS prior_7d_avg
)

SELECT
    'PIPELINE_FAILURE' AS alert_type,
    'CRITICAL' AS severity,

    COUNT(*) AS alert_count,

    'One or more current EPIP pipelines have a FAILED latest update.' AS message

FROM payments_dev.monitoring.pipeline_operational_health

WHERE operational_status = 'FAILED'

UNION ALL

SELECT
    'DATA_FRESHNESS',
    'HIGH',

    COUNT(*),

    'One or more monitored EPIP datasets are STALE or have NO_DATA.'

FROM payments_dev.monitoring.data_freshness_health

WHERE freshness_status IN ('STALE', 'NO_DATA')

UNION ALL

SELECT
    'DQ_DEGRADATION',
    'HIGH',

    COUNT(*),

    'One or more monitored EPIP datasets currently contain quarantined records.'

FROM payments_dev.monitoring.dq_current_health

WHERE dq_status = 'ATTENTION'

UNION ALL

SELECT
    'AGENT_REGRESSION',
    'CRITICAL',

    COUNT(*),

    'Latest formal fraud-agent evaluation failed one or more regression gates.'

FROM payments_dev.monitoring.agent_latest_health

WHERE overall_pass = false

UNION ALL

SELECT
    'DATABRICKS_COST_ANOMALY',
    'MEDIUM',

    CASE
        WHEN today_cost > 1
         AND prior_7d_avg IS NOT NULL
         AND today_cost > (2 * prior_7d_avg)
            THEN 1

        ELSE 0
    END,

    'Today''s estimated Databricks list cost exceeds the demo anomaly threshold.'

FROM cost_stats;
