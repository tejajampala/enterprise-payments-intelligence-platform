-- ============================================================================
-- EPIP M17D — FINAL M17 VALIDATION
-- ============================================================================
--
-- M17 is the final EPIP milestone.
--
-- Validation philosophy:
--   * views must exist and query successfully
--   * zero-row histories are valid when no qualifying activity exists
--   * NEVER_RUN / NO_DATA / zero-quarantine are explicit operational states
--   * cost is Databricks estimated list cost, not the complete AWS invoice
-- ============================================================================


-- ============================================================================
-- 1. MONITORING OBJECT INVENTORY
-- ============================================================================

SHOW VIEWS IN payments_dev.monitoring;


-- ============================================================================
-- 2. PIPELINE AND DATA QUALITY HEALTH — M17B / M17C
-- ============================================================================

SELECT
    pipeline_name,
    latest_result_state,
    operational_status,
    latest_update_end_time,
    hours_since_last_update

FROM payments_dev.monitoring.pipeline_operational_health

ORDER BY pipeline_name;


SELECT
    dataset_name,
    valid_records,
    quarantined_records,
    evaluated_records,
    quarantine_rate,
    dq_status

FROM payments_dev.monitoring.dq_current_health

ORDER BY dataset_name;


SELECT
    dataset_name,
    latest_business_time,
    latest_observed_at,
    record_count,
    freshness_status

FROM payments_dev.monitoring.data_freshness_health

ORDER BY dataset_name;


-- ============================================================================
-- 3. JOB AND TASK HEALTH
-- ============================================================================

SELECT
    job_name,
    latest_run_id,
    latest_result_state,
    operational_status,
    latest_run_end_time,
    hours_since_last_run

FROM payments_dev.monitoring.job_operational_health

ORDER BY job_name;


SELECT
    job_name,
    task_key,
    task_run_id,
    result_state,
    task_health_status,
    duration_seconds,
    task_end_time

FROM payments_dev.monitoring.epip_job_task_run_health

ORDER BY task_start_time DESC

LIMIT 100;


-- ============================================================================
-- 4. QUERY AND WAREHOUSE HEALTH
-- ============================================================================

SELECT
    statement_id,
    execution_status,
    statement_type,
    job_name,
    attribution_method,
    total_duration_ms,
    total_queue_wait_ms,
    read_gb,
    file_pruning_rate,
    spilled_local_gb,
    shuffle_read_gb,
    from_result_cache,
    performance_status,
    start_time

FROM payments_dev.monitoring.epip_query_performance

ORDER BY start_time DESC

LIMIT 100;


SELECT
    warehouse_name,
    warehouse_type,
    warehouse_size,
    min_clusters,
    max_clusters,
    auto_stop_minutes,
    latest_event_type,
    latest_cluster_count,
    latest_event_time,
    warehouse_status

FROM payments_dev.monitoring.warehouse_operational_health

ORDER BY warehouse_name;


-- ============================================================================
-- 5. OPERATIONAL SECURITY
-- ============================================================================

SELECT
    event_time,
    service_name,
    action_name,
    event_severity,
    event_category,
    initiating_identity,
    initiating_subject,
    run_by_identity,
    run_as_identity,
    response_status_code,
    response_error_message

FROM payments_dev.monitoring.epip_security_events

ORDER BY event_time DESC

LIMIT 100;


-- ============================================================================
-- 6. FRAUD MODEL + AGENT HEALTH
-- ============================================================================

SELECT *
FROM payments_dev.monitoring.fraud_model_current_health;


SELECT
    evaluation_run_id,
    agent_version,
    pass_rate,
    avg_groundedness_score,
    avg_evidence_completeness_score,
    avg_citation_score,
    human_review_rate,
    safety_rate,
    avg_duration_seconds,
    overall_pass,
    failed_gates,
    agent_health_status,
    evidence_age_hours,
    created_at

FROM payments_dev.monitoring.agent_latest_health;


SELECT
    evaluation_run_id,
    case_id,
    scenario_type,
    trace_id,
    overall_score,
    failure_reasons,
    created_at

FROM payments_dev.monitoring.agent_failed_case_diagnostics

ORDER BY created_at DESC

LIMIT 100;


-- ============================================================================
-- 7. DATABRICKS COST + OPTIMISATION
-- ============================================================================

SELECT
    usage_date,
    currency_code,
    usage_quantity,
    estimated_list_cost,
    billing_record_count,
    sku_count,
    workload_count

FROM payments_dev.monitoring.databricks_cost_daily

ORDER BY usage_date DESC

LIMIT 90;


SELECT
    workload_type,
    workload_name,
    attribution_quality,
    currency_code,
    usage_quantity,
    estimated_list_cost,
    first_usage_date,
    latest_usage_date

FROM payments_dev.monitoring.databricks_cost_by_workload

ORDER BY estimated_list_cost DESC

LIMIT 100;


SELECT *
FROM payments_dev.monitoring.cost_optimisation_candidates

ORDER BY
    estimated_list_cost DESC NULLS LAST,
    candidate_type,
    resource_name;


-- ============================================================================
-- 8. CONSOLIDATED OPERATIONS
-- ============================================================================

SELECT *
FROM payments_dev.monitoring.platform_operations_summary;


SELECT *
FROM payments_dev.monitoring.operations_alert_candidates

ORDER BY severity DESC, alert_type;


-- ============================================================================
-- 9. FINAL SEMANTIC CHECKS
-- ============================================================================

-- Current pipeline definitions must not disappear just because they have not run.
SELECT
    COUNT(*) AS current_pipeline_count,

    SUM(
        CASE
            WHEN operational_status = 'NEVER_RUN'
            THEN 1 ELSE 0
        END
    ) AS never_run_pipeline_count

FROM payments_dev.monitoring.pipeline_operational_health;


-- Current job definitions must not disappear just because they have not run.
SELECT
    COUNT(*) AS current_job_count,

    SUM(
        CASE
            WHEN operational_status = 'NEVER_RUN'
            THEN 1 ELSE 0
        END
    ) AS never_run_job_count

FROM payments_dev.monitoring.job_operational_health;


-- Quarantine-free datasets are represented explicitly rather than as missing rows.
SELECT
    COUNT(*) AS monitored_dq_dataset_count,

    SUM(
        CASE
            WHEN dq_status = 'HEALTHY'
            THEN 1 ELSE 0
        END
    ) AS healthy_dq_dataset_count

FROM payments_dev.monitoring.dq_current_health;


-- The cost layer remains Databricks-specific.
SELECT
    COUNT(*) AS cost_rows,

    COALESCE(
        SUM(estimated_list_cost),
        0
    ) AS total_estimated_databricks_list_cost

FROM payments_dev.monitoring.databricks_cost_daily;
