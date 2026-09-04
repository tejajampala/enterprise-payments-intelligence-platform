-- ============================================================================
-- EPIP M17C — PIPELINE + DATA QUALITY MONITORING VALIDATION
-- ============================================================================

SHOW VIEWS IN payments_dev.monitoring;


-- ---------------------------------------------------------------------------
-- 1. Pipeline operational status.
-- ---------------------------------------------------------------------------

SELECT
    pipeline_name,
    pipeline_type,
    serverless,
    development_mode,
    continuous,
    latest_update_id,
    latest_update_type,
    latest_update_start_time,
    latest_update_end_time,
    latest_update_duration_seconds,
    latest_result_state,
    operational_status,
    hours_since_last_update

FROM payments_dev.monitoring.pipeline_operational_health

ORDER BY pipeline_name;


-- ---------------------------------------------------------------------------
-- 2. Lakeflow expectation metrics.
-- ---------------------------------------------------------------------------

SELECT
    metric_date,
    update_id,
    dataset_name,
    expectation_name,
    passed_records,
    failed_records,
    evaluated_records,
    pass_rate,
    failure_rate,
    expectation_status,
    latest_metric_at

FROM payments_dev.monitoring.lakeflow_expectation_metrics

ORDER BY
    metric_date DESC,
    dataset_name,
    expectation_name

LIMIT 250;


-- ---------------------------------------------------------------------------
-- 3. Quarantine daily summary.
-- ---------------------------------------------------------------------------

SELECT *
FROM payments_dev.monitoring.dq_quarantine_daily
ORDER BY quality_date DESC, dataset_name;


-- ---------------------------------------------------------------------------
-- 4. Quarantine rule breakdown.
-- ---------------------------------------------------------------------------

SELECT *
FROM payments_dev.monitoring.dq_quarantine_rule_metrics
ORDER BY
    quality_date DESC,
    dataset_name,
    failed_record_count DESC,
    failed_rule;


-- ---------------------------------------------------------------------------
-- 5. Streaming event trust exceptions.
-- ---------------------------------------------------------------------------

SELECT *
FROM payments_dev.monitoring.payment_event_exception_health
ORDER BY event_date DESC;


-- ---------------------------------------------------------------------------
-- 6. Data freshness.
-- ---------------------------------------------------------------------------

SELECT
    dataset_name,
    dataset_type,
    latest_business_time,
    latest_source_ingested_at,
    latest_observed_at,
    record_count,
    processing_age_minutes,
    business_time_age_hours,
    freshness_status

FROM payments_dev.monitoring.data_freshness_health

ORDER BY dataset_name;


-- ---------------------------------------------------------------------------
-- 7. Compact health snapshot.
-- ---------------------------------------------------------------------------

SELECT
    'PIPELINE' AS health_domain,
    pipeline_name AS entity_name,
    operational_status AS health_status,
    latest_update_end_time AS latest_observed_at

FROM payments_dev.monitoring.pipeline_operational_health

UNION ALL

SELECT
    'DATASET',
    dataset_name,
    freshness_status,
    latest_observed_at

FROM payments_dev.monitoring.data_freshness_health

ORDER BY health_domain, entity_name;
