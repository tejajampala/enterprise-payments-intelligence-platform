-- ============================================================================
-- EPIP M17B — OBSERVABILITY FOUNDATION VALIDATION
-- ============================================================================


-- ---------------------------------------------------------------------------
-- 1. Monitoring schema exists.
-- ---------------------------------------------------------------------------

DESCRIBE SCHEMA EXTENDED payments_dev.monitoring;


-- ---------------------------------------------------------------------------
-- 2. Monitoring views exist.
-- ---------------------------------------------------------------------------

SHOW VIEWS IN payments_dev.monitoring;


-- Expected M17B views:
--
-- current_epip_pipelines
-- epip_pipeline_update_health
-- current_epip_jobs
-- epip_job_run_health
-- system_source_readiness


-- ---------------------------------------------------------------------------
-- 3. Current EPIP pipelines.
-- ---------------------------------------------------------------------------

SELECT
    pipeline_name,
    pipeline_type,
    serverless,
    development_mode,
    continuous,
    create_time,
    change_time

FROM payments_dev.monitoring.current_epip_pipelines

ORDER BY pipeline_name;


-- Expected EPIP pipeline family includes:
--
-- epip-<target>-payment-events-bronze
-- epip-<target>-silver-transformations
-- epip-<target>-gold-analytics
--
-- Additional EPIP Lakeflow-created resources may also appear if they use
-- epip-* names.


-- ---------------------------------------------------------------------------
-- 4. Pipeline update history.
-- ---------------------------------------------------------------------------

SELECT
    pipeline_name,
    update_id,
    update_type,
    trigger_type,
    update_start_time,
    update_end_time,
    duration_seconds,
    result_state,
    request_count,
    health_status

FROM payments_dev.monitoring.epip_pipeline_update_health

ORDER BY update_start_time DESC

LIMIT 100;


-- ---------------------------------------------------------------------------
-- 5. Current EPIP jobs.
-- ---------------------------------------------------------------------------

SELECT
    job_name,
    paused,
    trigger_type,
    run_as_user_name,
    create_time,
    change_time

FROM payments_dev.monitoring.current_epip_jobs

ORDER BY job_name;


-- ---------------------------------------------------------------------------
-- 6. Job run history.
-- ---------------------------------------------------------------------------

SELECT
    job_name,
    run_id,
    trigger_type,
    run_type,
    run_start_time,
    run_end_time,
    duration_seconds,
    result_state,
    termination_code,
    health_status

FROM payments_dev.monitoring.epip_job_run_health

ORDER BY run_start_time DESC

LIMIT 100;


-- ---------------------------------------------------------------------------
-- 7. System-table source readiness.
-- ---------------------------------------------------------------------------

SELECT
    source_table,
    monitoring_domain,
    latest_event_time,
    observed_rows,

    CASE
        WHEN observed_rows = 0 THEN 'NO_RECENT_ROWS'
        WHEN latest_event_time IS NULL THEN 'NO_TIMESTAMP'
        ELSE 'AVAILABLE'
    END AS source_status

FROM payments_dev.monitoring.system_source_readiness

ORDER BY monitoring_domain;


-- ---------------------------------------------------------------------------
-- 8. Basic health summary.
-- ---------------------------------------------------------------------------

SELECT
    'PIPELINE_UPDATE' AS entity_type,
    health_status,
    COUNT(*) AS entity_count

FROM payments_dev.monitoring.epip_pipeline_update_health

GROUP BY health_status

UNION ALL

SELECT
    'JOB_RUN',
    health_status,
    COUNT(*)

FROM payments_dev.monitoring.epip_job_run_health

GROUP BY health_status

ORDER BY entity_type, health_status;
