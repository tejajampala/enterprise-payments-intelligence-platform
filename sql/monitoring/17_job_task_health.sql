-- ============================================================================
-- EPIP M17D — JOB AND TASK OPERATIONAL HEALTH
-- ============================================================================
--
-- Purpose:
--   * expose current EPIP job-task definitions
--   * normalize Lakeflow task-run timeline slices into logical task runs
--   * retain current jobs that have never executed
--   * provide dashboard-ready daily job health
--
-- Databricks behavior:
--   system.lakeflow.job_tasks is SCD2.
--   system.lakeflow.job_run_timeline and job_task_run_timeline are immutable
--   timeline tables and can split long executions into hourly slices.
-- ============================================================================


-- ============================================================================
-- VIEW 1 — CURRENT EPIP JOB TASK DEFINITIONS
-- ============================================================================

CREATE OR REPLACE VIEW payments_dev.monitoring.current_epip_job_tasks
COMMENT 'Current non-deleted task definitions for current EPIP jobs.'
AS

WITH ranked_tasks AS (
    SELECT
        account_id,
        workspace_id,
        job_id,
        task_key,
        depends_on_keys,
        timeout_seconds,
        health_rules,
        change_time,
        delete_time,

        ROW_NUMBER() OVER (
            PARTITION BY workspace_id, job_id, task_key
            ORDER BY change_time DESC
        ) AS version_rank

    FROM system.lakeflow.job_tasks
)

SELECT
    task.account_id,
    task.workspace_id,
    task.job_id,
    job.job_name,
    task.task_key,
    task.depends_on_keys,
    task.timeout_seconds,
    task.health_rules,
    task.change_time

FROM ranked_tasks AS task

INNER JOIN payments_dev.monitoring.current_epip_jobs AS job
    ON task.workspace_id = job.workspace_id
   AND task.job_id = job.job_id

WHERE task.version_rank = 1
  AND task.delete_time IS NULL;


-- ============================================================================
-- VIEW 2 — LOGICAL EPIP TASK RUN HEALTH
-- ============================================================================

CREATE OR REPLACE VIEW payments_dev.monitoring.epip_job_task_run_health
COMMENT 'One row per logical EPIP task run with hourly timeline slices normalized.'
AS

WITH logical_task_runs AS (
    SELECT
        timeline.account_id,
        timeline.workspace_id,
        timeline.job_id,
        job.job_name,

        timeline.job_run_id,
        timeline.run_id AS task_run_id,
        timeline.parent_run_id,
        timeline.task_key,

        MIN(timeline.period_start_time) AS task_start_time,
        MAX(timeline.period_end_time) AS task_end_time,

        SUM(
            TIMESTAMPDIFF(
                SECOND,
                timeline.period_start_time,
                timeline.period_end_time
            )
        ) AS duration_seconds,

        MAX_BY(
            timeline.result_state,
            timeline.period_end_time
        ) AS result_state,

        MAX_BY(
            timeline.termination_code,
            timeline.period_end_time
        ) AS termination_code,

        MAX_BY(
            timeline.termination_type,
            timeline.period_end_time
        ) AS termination_type,

        MAX_BY(
            timeline.compute_ids,
            timeline.period_end_time
        ) AS compute_ids,

        MAX_BY(
            timeline.task_parameters,
            timeline.period_end_time
        ) AS task_parameters,

        MAX_BY(
            timeline.setup_duration_seconds,
            timeline.period_end_time
        ) AS setup_duration_seconds,

        MAX_BY(
            timeline.execution_duration_seconds,
            timeline.period_end_time
        ) AS execution_duration_seconds,

        MAX_BY(
            timeline.cleanup_duration_seconds,
            timeline.period_end_time
        ) AS cleanup_duration_seconds

    FROM system.lakeflow.job_task_run_timeline AS timeline

    INNER JOIN payments_dev.monitoring.current_epip_jobs AS job
        ON timeline.workspace_id = job.workspace_id
       AND timeline.job_id = job.job_id

    GROUP BY
        timeline.account_id,
        timeline.workspace_id,
        timeline.job_id,
        job.job_name,
        timeline.job_run_id,
        timeline.run_id,
        timeline.parent_run_id,
        timeline.task_key
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
        ) THEN 'FAILED'
        WHEN result_state = 'SKIPPED' THEN 'SKIPPED'
        WHEN result_state IS NULL THEN 'IN_PROGRESS'
        ELSE 'UNKNOWN'
    END AS task_health_status

FROM logical_task_runs;


-- ============================================================================
-- VIEW 3 — CURRENT JOB OPERATIONAL HEALTH
-- ============================================================================

CREATE OR REPLACE VIEW payments_dev.monitoring.job_operational_health
COMMENT 'Current EPIP jobs with latest logical run and explicit NEVER_RUN state.'
AS

WITH logical_job_runs AS (
    SELECT
        timeline.account_id,
        timeline.workspace_id,
        timeline.job_id,
        timeline.run_id,

        MAX(timeline.run_name) AS run_name,
        MAX(timeline.trigger_type) AS trigger_type,
        MAX(timeline.run_type) AS run_type,

        MIN(timeline.period_start_time) AS run_start_time,
        MAX(timeline.period_end_time) AS run_end_time,

        SUM(
            TIMESTAMPDIFF(
                SECOND,
                timeline.period_start_time,
                timeline.period_end_time
            )
        ) AS duration_seconds,

        MAX_BY(
            timeline.result_state,
            timeline.period_end_time
        ) AS result_state,

        MAX_BY(
            timeline.termination_code,
            timeline.period_end_time
        ) AS termination_code,

        MAX_BY(
            timeline.termination_type,
            timeline.period_end_time
        ) AS termination_type

    FROM system.lakeflow.job_run_timeline AS timeline

    INNER JOIN payments_dev.monitoring.current_epip_jobs AS job
        ON timeline.workspace_id = job.workspace_id
       AND timeline.job_id = job.job_id

    GROUP BY
        timeline.account_id,
        timeline.workspace_id,
        timeline.job_id,
        timeline.run_id
),

ranked_runs AS (
    SELECT
        *,

        ROW_NUMBER() OVER (
            PARTITION BY workspace_id, job_id
            ORDER BY run_end_time DESC, run_start_time DESC, run_id DESC
        ) AS run_rank

    FROM logical_job_runs
),

latest_run AS (
    SELECT *
    FROM ranked_runs
    WHERE run_rank = 1
)

SELECT
    job.account_id,
    job.workspace_id,
    job.job_id,
    job.job_name,

    job.paused,
    job.trigger_type,
    job.run_as_user_name,
    job.timeout_seconds,
    job.create_time,
    job.change_time,

    run.run_id AS latest_run_id,
    run.run_name AS latest_run_name,
    run.run_type AS latest_run_type,
    run.trigger_type AS latest_run_trigger_type,

    run.run_start_time AS latest_run_start_time,
    run.run_end_time AS latest_run_end_time,
    run.duration_seconds AS latest_run_duration_seconds,

    run.result_state AS latest_result_state,
    run.termination_code AS latest_termination_code,
    run.termination_type AS latest_termination_type,

    CASE
        WHEN run.run_id IS NULL THEN 'NEVER_RUN'
        WHEN run.result_state = 'SUCCEEDED' THEN 'HEALTHY'
        WHEN run.result_state IN (
            'FAILED',
            'CANCELLED',
            'TIMED_OUT',
            'ERROR',
            'BLOCKED'
        ) THEN 'FAILED'
        WHEN run.result_state = 'SKIPPED' THEN 'SKIPPED'
        WHEN run.result_state IS NULL THEN 'IN_PROGRESS'
        ELSE 'UNKNOWN'
    END AS operational_status,

    CASE
        WHEN run.run_end_time IS NULL THEN NULL
        ELSE TIMESTAMPDIFF(
            HOUR,
            run.run_end_time,
            CURRENT_TIMESTAMP()
        )
    END AS hours_since_last_run

FROM payments_dev.monitoring.current_epip_jobs AS job

LEFT JOIN latest_run AS run
    ON job.workspace_id = run.workspace_id
   AND job.job_id = run.job_id;


-- ============================================================================
-- VIEW 4 — DAILY EPIP JOB HEALTH
-- ============================================================================

CREATE OR REPLACE VIEW payments_dev.monitoring.job_daily_health
COMMENT 'Daily EPIP job and task reliability metrics for the last 30 days.'
AS

WITH job_runs AS (
    SELECT
        CAST(run_start_time AS DATE) AS run_date,

        COUNT(*) AS job_run_count,

        SUM(
            CASE WHEN result_state = 'SUCCEEDED' THEN 1 ELSE 0 END
        ) AS successful_job_runs,

        SUM(
            CASE
                WHEN result_state IN (
                    'FAILED',
                    'CANCELLED',
                    'TIMED_OUT',
                    'ERROR',
                    'BLOCKED'
                )
                THEN 1 ELSE 0
            END
        ) AS failed_job_runs,

        AVG(duration_seconds) AS avg_job_duration_seconds,

        PERCENTILE_APPROX(
            duration_seconds,
            0.95
        ) AS p95_job_duration_seconds

    FROM payments_dev.monitoring.epip_job_run_health

    WHERE run_start_time >= CURRENT_TIMESTAMP() - INTERVAL 30 DAYS

    GROUP BY CAST(run_start_time AS DATE)
),

task_runs AS (
    SELECT
        CAST(task_start_time AS DATE) AS run_date,

        COUNT(*) AS task_run_count,

        SUM(
            CASE WHEN result_state = 'SUCCEEDED' THEN 1 ELSE 0 END
        ) AS successful_task_runs,

        SUM(
            CASE
                WHEN result_state IN (
                    'FAILED',
                    'CANCELLED',
                    'TIMED_OUT',
                    'ERROR',
                    'BLOCKED'
                )
                THEN 1 ELSE 0
            END
        ) AS failed_task_runs

    FROM payments_dev.monitoring.epip_job_task_run_health

    WHERE task_start_time >= CURRENT_TIMESTAMP() - INTERVAL 30 DAYS

    GROUP BY CAST(task_start_time AS DATE)
)

SELECT
    COALESCE(job.run_date, task.run_date) AS run_date,

    COALESCE(job.job_run_count, 0) AS job_run_count,
    COALESCE(job.successful_job_runs, 0) AS successful_job_runs,
    COALESCE(job.failed_job_runs, 0) AS failed_job_runs,

    COALESCE(task.task_run_count, 0) AS task_run_count,
    COALESCE(task.successful_task_runs, 0) AS successful_task_runs,
    COALESCE(task.failed_task_runs, 0) AS failed_task_runs,

    job.avg_job_duration_seconds,
    job.p95_job_duration_seconds

FROM job_runs AS job

FULL OUTER JOIN task_runs AS task
    ON job.run_date = task.run_date;
