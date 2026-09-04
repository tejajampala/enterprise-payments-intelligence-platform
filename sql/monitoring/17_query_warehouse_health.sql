-- ============================================================================
-- EPIP M17D — QUERY PERFORMANCE AND SQL WAREHOUSE HEALTH
-- ============================================================================
--
-- system.query.history is regional and can contain account-wide data.
-- This implementation scopes queries to workspaces that host current EPIP
-- resources, then applies an EPIP attribution rule.
--
-- EPIP attribution:
--   1. query was launched by a current EPIP job, OR
--   2. statement text references EPIP/payments catalogs.
--
-- Statement text may be redacted for principals without PII-access privileges.
-- In that case job-based attribution still works.
-- ============================================================================


-- ============================================================================
-- VIEW 1 — EPIP QUERY PERFORMANCE
-- ============================================================================

CREATE OR REPLACE VIEW payments_dev.monitoring.epip_query_performance
COMMENT 'EPIP-attributed query performance and efficiency signals from system.query.history.'
AS

WITH epip_workspaces AS (
    SELECT DISTINCT workspace_id
    FROM payments_dev.monitoring.current_epip_pipelines

    UNION

    SELECT DISTINCT workspace_id
    FROM payments_dev.monitoring.current_epip_jobs
),

query_base AS (
    SELECT
        history.account_id,
        history.workspace_id,
        history.statement_id,
        history.session_id,

        history.execution_status,

        history.compute.type AS compute_type,
        history.compute.warehouse_id AS warehouse_id,
        history.compute.cluster_id AS cluster_id,

        history.executed_by,
        history.executed_as,

        history.statement_type,
        history.client_application,
        history.client_driver,

        history.total_duration_ms,
        history.waiting_for_compute_duration_ms,
        history.waiting_at_capacity_duration_ms,
        history.execution_duration_ms,
        history.compilation_duration_ms,
        history.total_task_duration_ms,
        history.result_fetch_duration_ms,

        history.start_time,
        history.end_time,
        history.update_time,

        history.read_partitions,
        history.pruned_files,
        history.read_files,
        history.read_rows,
        history.produced_rows,
        history.read_bytes,
        history.read_io_cache_percent,
        history.from_result_cache,

        history.spilled_local_bytes,
        history.written_bytes,
        history.written_rows,
        history.written_files,
        history.shuffle_read_bytes,

        history.query_source,
        history.query_tags,

        CAST(history.query_source.job_info.job_id AS STRING)
            AS source_job_id,

        history.query_source.job_info.job_run_id
            AS source_job_run_id,

        history.query_source.job_info.job_task_run_id
            AS source_job_task_run_id,

        history.query_source.dashboard_id
            AS source_dashboard_id,

        history.query_source.notebook_id
            AS source_notebook_id,

        history.statement_text,

        job.job_name

    FROM system.query.history AS history

    INNER JOIN epip_workspaces AS workspace_scope
        ON history.workspace_id = workspace_scope.workspace_id

    LEFT JOIN payments_dev.monitoring.current_epip_jobs AS job
        ON history.workspace_id = job.workspace_id
       AND CAST(history.query_source.job_info.job_id AS STRING) = job.job_id

    WHERE history.start_time >= CURRENT_TIMESTAMP() - INTERVAL 30 DAYS
),

epip_attributed AS (
    SELECT
        *,

        CASE
            WHEN job_name IS NOT NULL THEN 'EPIP_JOB'
            WHEN LOWER(COALESCE(statement_text, '')) RLIKE
                 '(payments_dev|payments_ci|payments_prod|epip)'
                THEN 'EPIP_SQL_TEXT'
            ELSE 'UNATTRIBUTED'
        END AS attribution_method

    FROM query_base
)

SELECT
    account_id,
    workspace_id,
    statement_id,
    session_id,

    execution_status,

    compute_type,
    warehouse_id,
    cluster_id,

    executed_by,
    executed_as,

    statement_type,
    client_application,
    client_driver,

    source_job_id,
    job_name,
    source_job_run_id,
    source_job_task_run_id,
    source_dashboard_id,
    source_notebook_id,

    attribution_method,

    start_time,
    end_time,
    update_time,

    total_duration_ms,
    execution_duration_ms,
    compilation_duration_ms,

    COALESCE(waiting_for_compute_duration_ms, 0)
      + COALESCE(waiting_at_capacity_duration_ms, 0)
        AS total_queue_wait_ms,

    waiting_for_compute_duration_ms,
    waiting_at_capacity_duration_ms,

    total_task_duration_ms,
    result_fetch_duration_ms,

    read_partitions,
    pruned_files,
    read_files,
    read_rows,
    produced_rows,

    read_bytes,
    read_bytes / POWER(1024.0, 3) AS read_gb,

    read_io_cache_percent,
    from_result_cache,

    spilled_local_bytes,
    spilled_local_bytes / POWER(1024.0, 3) AS spilled_local_gb,

    shuffle_read_bytes,
    shuffle_read_bytes / POWER(1024.0, 3) AS shuffle_read_gb,

    written_bytes,
    written_rows,
    written_files,

    CASE
        WHEN COALESCE(pruned_files, 0) + COALESCE(read_files, 0) = 0
            THEN NULL

        ELSE
            1.0 * COALESCE(pruned_files, 0)
            / (
                COALESCE(pruned_files, 0)
                + COALESCE(read_files, 0)
            )
    END AS file_pruning_rate,

    CASE
        WHEN execution_status IN ('FAILED', 'CANCELED')
            THEN 'FAILED'

        WHEN COALESCE(spilled_local_bytes, 0) > 0
            THEN 'SPILLING'

        WHEN (
            COALESCE(waiting_for_compute_duration_ms, 0)
            + COALESCE(waiting_at_capacity_duration_ms, 0)
        ) >= 30000
            THEN 'QUEUE_DELAY'

        WHEN COALESCE(total_duration_ms, 0) >= 60000
            THEN 'LONG_RUNNING'

        WHEN COALESCE(read_bytes, 0) >= POWER(1024, 3)
            THEN 'HIGH_SCAN'

        ELSE 'HEALTHY'
    END AS performance_status,

    query_tags

FROM epip_attributed

WHERE attribution_method <> 'UNATTRIBUTED';


-- ============================================================================
-- VIEW 2 — DAILY QUERY PERFORMANCE
-- ============================================================================

CREATE OR REPLACE VIEW payments_dev.monitoring.query_performance_daily
COMMENT 'Daily EPIP query reliability, latency, scan, spill and cache metrics.'
AS

SELECT
    CAST(start_time AS DATE) AS query_date,

    COUNT(*) AS query_count,

    SUM(
        CASE
            WHEN execution_status IN ('FAILED', 'CANCELED')
            THEN 1 ELSE 0
        END
    ) AS failed_query_count,

    SUM(
        CASE
            WHEN performance_status = 'LONG_RUNNING'
            THEN 1 ELSE 0
        END
    ) AS long_running_query_count,

    SUM(
        CASE
            WHEN performance_status = 'SPILLING'
            THEN 1 ELSE 0
        END
    ) AS spilling_query_count,

    SUM(
        CASE
            WHEN performance_status = 'QUEUE_DELAY'
            THEN 1 ELSE 0
        END
    ) AS queue_delayed_query_count,

    AVG(total_duration_ms) / 1000.0
        AS avg_total_duration_seconds,

    PERCENTILE_APPROX(
        total_duration_ms,
        0.95
    ) / 1000.0
        AS p95_total_duration_seconds,

    SUM(COALESCE(read_gb, 0))
        AS total_read_gb,

    SUM(COALESCE(spilled_local_gb, 0))
        AS total_spilled_local_gb,

    SUM(COALESCE(shuffle_read_gb, 0))
        AS total_shuffle_read_gb,

    AVG(file_pruning_rate)
        AS avg_file_pruning_rate,

    AVG(
        CASE
            WHEN from_result_cache THEN 1.0
            ELSE 0.0
        END
    ) AS result_cache_hit_rate

FROM payments_dev.monitoring.epip_query_performance

GROUP BY CAST(start_time AS DATE);


-- ============================================================================
-- VIEW 3 — CURRENT WAREHOUSE OPERATIONAL HEALTH
-- ============================================================================

CREATE OR REPLACE VIEW payments_dev.monitoring.warehouse_operational_health
COMMENT 'Current SQL warehouses in EPIP workspaces with latest lifecycle event and cost-relevant settings.'
AS

WITH epip_workspaces AS (
    SELECT DISTINCT workspace_id
    FROM payments_dev.monitoring.current_epip_pipelines

    UNION

    SELECT DISTINCT workspace_id
    FROM payments_dev.monitoring.current_epip_jobs
),

ranked_warehouses AS (
    SELECT
        warehouse.*,

        ROW_NUMBER() OVER (
            PARTITION BY warehouse.workspace_id, warehouse.warehouse_id
            ORDER BY warehouse.change_time DESC
        ) AS warehouse_rank

    FROM system.compute.warehouses AS warehouse

    INNER JOIN epip_workspaces AS workspace_scope
        ON warehouse.workspace_id = workspace_scope.workspace_id
),

current_warehouses AS (
    SELECT *
    FROM ranked_warehouses
    WHERE warehouse_rank = 1
      AND delete_time IS NULL
),

ranked_events AS (
    SELECT
        event.*,

        ROW_NUMBER() OVER (
            PARTITION BY event.workspace_id, event.warehouse_id
            ORDER BY event.event_time DESC
        ) AS event_rank

    FROM system.compute.warehouse_events AS event

    INNER JOIN epip_workspaces AS workspace_scope
        ON event.workspace_id = workspace_scope.workspace_id
),

latest_events AS (
    SELECT *
    FROM ranked_events
    WHERE event_rank = 1
)

SELECT
    warehouse.account_id,
    warehouse.workspace_id,
    warehouse.warehouse_id,

    warehouse.warehouse_name,
    warehouse.warehouse_type,
    warehouse.warehouse_channel,
    warehouse.warehouse_size,

    warehouse.min_clusters,
    warehouse.max_clusters,
    warehouse.auto_stop_minutes,

    warehouse.tags,

    warehouse.change_time AS warehouse_last_changed_at,

    event.event_type AS latest_event_type,
    event.cluster_count AS latest_cluster_count,
    event.event_time AS latest_event_time,

    CASE
        WHEN event.event_type IS NULL THEN 'NO_EVENT_HISTORY'
        WHEN event.event_type IN ('RUNNING', 'STARTING', 'SCALED_UP')
            THEN 'ACTIVE'
        WHEN event.event_type IN ('STOPPING', 'STOPPED', 'SCALED_DOWN')
            THEN 'INACTIVE_OR_SCALING_DOWN'
        ELSE 'UNKNOWN'
    END AS warehouse_status,

    CASE
        WHEN event.event_time IS NULL THEN NULL
        ELSE TIMESTAMPDIFF(
            HOUR,
            event.event_time,
            CURRENT_TIMESTAMP()
        )
    END AS hours_since_last_event

FROM current_warehouses AS warehouse

LEFT JOIN latest_events AS event
    ON warehouse.workspace_id = event.workspace_id
   AND warehouse.warehouse_id = event.warehouse_id;
