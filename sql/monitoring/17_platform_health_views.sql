-- ============================================================================
-- EPIP M17B — PLATFORM OBSERVABILITY FOUNDATION VIEWS
-- ============================================================================
--
-- Scope:
--   1. current EPIP Lakeflow pipeline definitions
--   2. normalized EPIP pipeline update history
--   3. current EPIP job definitions
--   4. normalized EPIP job-run history
--   5. system-table source freshness/readiness
--
-- Detailed DQ, query tuning, security events, ML/agent health and cost
-- calculation are intentionally deferred to M17C-M17F.
--
-- Databricks system-table semantics used here:
--   - system.lakeflow.pipelines and jobs are SCD2 tables.
--   - latest state must be selected BEFORE filtering delete_time.
--   - pipeline/job timeline tables can split long runs into hourly slices.
--     We aggregate slices back to one logical update/run.
-- ============================================================================


CREATE SCHEMA IF NOT EXISTS payments_dev.monitoring
COMMENT 'Governed EPIP platform observability, reliability, performance and cost monitoring.';


-- ============================================================================
-- VIEW 1 — CURRENT EPIP PIPELINES
-- ============================================================================

CREATE OR REPLACE VIEW payments_dev.monitoring.current_epip_pipelines
COMMENT 'Current non-deleted EPIP Lakeflow pipeline definitions from the regional system table.'
AS

WITH ranked_pipelines AS (
    SELECT
        account_id,
        workspace_id,
        pipeline_id,
        pipeline_type,
        name,
        created_by,
        run_as,
        tags,
        settings,
        configuration,
        create_time,
        change_time,
        delete_time,

        ROW_NUMBER() OVER (
            PARTITION BY workspace_id, pipeline_id
            ORDER BY change_time DESC
        ) AS version_rank

    FROM system.lakeflow.pipelines
)

SELECT
    account_id,
    workspace_id,
    pipeline_id,
    pipeline_type,
    name AS pipeline_name,

    created_by,
    run_as,

    CAST(settings.serverless AS BOOLEAN) AS serverless,
    CAST(settings.development AS BOOLEAN) AS development_mode,
    CAST(settings.continuous AS BOOLEAN) AS continuous,
    settings.edition AS edition,
    settings.channel AS channel,

    tags,
    configuration,

    create_time,
    change_time

FROM ranked_pipelines

WHERE version_rank = 1
  AND delete_time IS NULL
  AND LOWER(name) LIKE '%epip%';


-- ============================================================================
-- VIEW 2 — EPIP PIPELINE UPDATE HEALTH
-- ============================================================================
--
-- pipeline_update_timeline is immutable, but long updates can be represented by
-- multiple hourly slices. This view returns one row per logical update.
-- ============================================================================

CREATE OR REPLACE VIEW payments_dev.monitoring.epip_pipeline_update_health
COMMENT 'One row per EPIP Lakeflow pipeline update with normalized duration and health status.'
AS

WITH current_pipelines AS (
    SELECT
        workspace_id,
        pipeline_id,
        pipeline_name

    FROM payments_dev.monitoring.current_epip_pipelines
),

logical_updates AS (
    SELECT
        timeline.account_id,
        timeline.workspace_id,
        timeline.pipeline_id,
        pipeline.pipeline_name,

        timeline.update_id,

        MAX(timeline.update_type) AS update_type,
        MAX(timeline.trigger_type) AS trigger_type,
        MAX(timeline.run_as_user_name) AS run_as_user_name,

        MIN(timeline.period_start_time) AS update_start_time,
        MAX(timeline.period_end_time) AS update_end_time,

        CAST(
            SUM(timeline.period_end_time - timeline.period_start_time)
            AS BIGINT
        ) AS duration_seconds,

        MAX(timeline.result_state) AS result_state,

        COUNT(DISTINCT timeline.request_id) AS request_count,

        MAX(SIZE(timeline.refresh_selection)) AS refresh_selection_count,
        MAX(SIZE(timeline.full_refresh_selection)) AS full_refresh_selection_count,
        MAX(SIZE(timeline.reset_checkpoint_selection)) AS reset_checkpoint_selection_count

    FROM system.lakeflow.pipeline_update_timeline AS timeline

    INNER JOIN current_pipelines AS pipeline
        ON timeline.workspace_id = pipeline.workspace_id
       AND timeline.pipeline_id = pipeline.pipeline_id

    WHERE timeline.period_start_time >= CURRENT_TIMESTAMP() - INTERVAL 30 DAYS

    GROUP BY
        timeline.account_id,
        timeline.workspace_id,
        timeline.pipeline_id,
        pipeline.pipeline_name,
        timeline.update_id
)

SELECT
    *,

    CASE
        WHEN result_state = 'COMPLETED' THEN 'HEALTHY'
        WHEN result_state IN ('FAILED', 'CANCELED') THEN 'ATTENTION'
        WHEN result_state IS NULL THEN 'IN_PROGRESS_OR_INCOMPLETE'
        ELSE 'UNKNOWN'
    END AS health_status

FROM logical_updates;


-- ============================================================================
-- VIEW 3 — CURRENT EPIP JOBS
-- ============================================================================

CREATE OR REPLACE VIEW payments_dev.monitoring.current_epip_jobs
COMMENT 'Current non-deleted EPIP jobs from the regional Lakeflow jobs system table.'
AS

WITH ranked_jobs AS (
    SELECT
        account_id,
        workspace_id,
        job_id,
        name,
        description,
        creator_id,
        creator_user_name,
        run_as,
        run_as_user_name,
        paused,
        trigger_type,
        tags,
        timeout_seconds,
        health_rules,
        deployment,
        create_time,
        change_time,
        delete_time,

        ROW_NUMBER() OVER (
            PARTITION BY workspace_id, job_id
            ORDER BY change_time DESC
        ) AS version_rank

    FROM system.lakeflow.jobs
)

SELECT
    account_id,
    workspace_id,
    job_id,
    name AS job_name,
    description,

    creator_id,
    creator_user_name,

    run_as,
    run_as_user_name,

    paused,
    trigger_type,

    timeout_seconds,
    health_rules,
    deployment,
    tags,

    create_time,
    change_time

FROM ranked_jobs

WHERE version_rank = 1
  AND delete_time IS NULL
  AND LOWER(name) LIKE '%epip%';


-- ============================================================================
-- VIEW 4 — EPIP JOB RUN HEALTH
-- ============================================================================
--
-- Long runs can be split into hourly slices. We normalize them back to one
-- logical run using job_id + run_id.
-- ============================================================================

CREATE OR REPLACE VIEW payments_dev.monitoring.epip_job_run_health
COMMENT 'One row per logical EPIP job run with normalized run duration and result state.'
AS

WITH current_jobs AS (
    SELECT
        workspace_id,
        job_id,
        job_name

    FROM payments_dev.monitoring.current_epip_jobs
),

logical_job_runs AS (
    SELECT
        timeline.account_id,
        timeline.workspace_id,
        timeline.job_id,
        job.job_name,

        timeline.run_id,

        MAX(timeline.run_name) AS run_name,
        MAX(timeline.trigger_type) AS trigger_type,
        MAX(timeline.run_type) AS run_type,

        MIN(timeline.period_start_time) AS run_start_time,
        MAX(timeline.period_end_time) AS run_end_time,

        CAST(
            SUM(timeline.period_end_time - timeline.period_start_time)
            AS BIGINT
        ) AS duration_seconds,

        MAX(timeline.result_state) AS result_state,
        MAX(timeline.termination_code) AS termination_code,
        MAX(timeline.termination_type) AS termination_type

    FROM system.lakeflow.job_run_timeline AS timeline

    INNER JOIN current_jobs AS job
        ON timeline.workspace_id = job.workspace_id
       AND timeline.job_id = job.job_id

    WHERE timeline.period_start_time >= CURRENT_TIMESTAMP() - INTERVAL 30 DAYS

    GROUP BY
        timeline.account_id,
        timeline.workspace_id,
        timeline.job_id,
        job.job_name,
        timeline.run_id
)

SELECT
    *,

    CASE
        WHEN result_state = 'SUCCEEDED' THEN 'HEALTHY'
        WHEN result_state IN (
            'FAILED',
            'CANCELLED',
            'TIMED_OUT',
            'ERROR',
            'BLOCKED'
        ) THEN 'ATTENTION'
        WHEN result_state = 'SKIPPED' THEN 'SKIPPED'
        WHEN result_state IS NULL THEN 'IN_PROGRESS_OR_INCOMPLETE'
        ELSE 'UNKNOWN'
    END AS health_status

FROM logical_job_runs;


-- ============================================================================
-- VIEW 5 — SYSTEM SOURCE READINESS
-- ============================================================================
--
-- Provides a compact operational check of the system-table sources required by
-- later M17 stages.
--
-- Important availability differences:
--   billing.usage is global account data and may arrive with billing latency.
--   Lakeflow/query/audit data is regional and has its own delivery latency.
-- Therefore "latest_event_time" is informational, not a universal SLA.
-- ============================================================================

CREATE OR REPLACE VIEW payments_dev.monitoring.system_source_readiness
COMMENT 'Readiness and recent-data presence for the Databricks system-table sources used by EPIP M17.'
AS

SELECT
    'system.lakeflow.pipelines' AS source_table,
    'PIPELINE_DEFINITIONS' AS monitoring_domain,
    MAX(change_time) AS latest_event_time,
    COUNT(*) AS observed_rows

FROM system.lakeflow.pipelines

UNION ALL

SELECT
    'system.lakeflow.pipeline_update_timeline',
    'PIPELINE_UPDATES',
    MAX(period_end_time),
    COUNT(*)

FROM system.lakeflow.pipeline_update_timeline

WHERE period_start_time >= CURRENT_TIMESTAMP() - INTERVAL 30 DAYS

UNION ALL

SELECT
    'system.lakeflow.jobs',
    'JOB_DEFINITIONS',
    MAX(change_time),
    COUNT(*)

FROM system.lakeflow.jobs

UNION ALL

SELECT
    'system.lakeflow.job_run_timeline',
    'JOB_RUNS',
    MAX(period_end_time),
    COUNT(*)

FROM system.lakeflow.job_run_timeline

WHERE period_start_time >= CURRENT_TIMESTAMP() - INTERVAL 30 DAYS

UNION ALL

SELECT
    'system.query.history',
    'QUERY_HISTORY',
    MAX(update_time),
    COUNT(*)

FROM system.query.history

WHERE start_time >= CURRENT_TIMESTAMP() - INTERVAL 30 DAYS

UNION ALL

SELECT
    'system.billing.usage',
    'BILLING_USAGE',
    MAX(usage_end_time),
    COUNT(*)

FROM system.billing.usage

WHERE usage_date >= CURRENT_DATE() - INTERVAL 30 DAYS

UNION ALL

SELECT
    'system.access.audit',
    'AUDIT_EVENTS',
    MAX(event_time),
    COUNT(*)

FROM system.access.audit

WHERE event_date >= CURRENT_DATE() - INTERVAL 30 DAYS;
