-- ============================================================================
-- EPIP M17C — PIPELINE OPERATIONAL HEALTH
-- ============================================================================

CREATE OR REPLACE VIEW payments_dev.monitoring.pipeline_operational_health
COMMENT 'Current EPIP Lakeflow pipelines with latest logical update and explicit NEVER_RUN state.'
AS

WITH current_pipelines AS (
    SELECT
        account_id,
        workspace_id,
        pipeline_id,
        pipeline_name,
        pipeline_type,
        serverless,
        development_mode,
        continuous,
        edition,
        channel,
        create_time,
        change_time
    FROM payments_dev.monitoring.current_epip_pipelines
),

logical_updates AS (
    SELECT
        t.workspace_id,
        t.pipeline_id,
        t.update_id,
        MAX(t.update_type) AS update_type,
        MAX(t.trigger_type) AS trigger_type,
        MAX(t.run_as_user_name) AS run_as_user_name,
        MIN(t.period_start_time) AS update_start_time,
        MAX(t.period_end_time) AS update_end_time,
        SUM(
            TIMESTAMPDIFF(
                SECOND,
                t.period_start_time,
                t.period_end_time
            )
        ) AS duration_seconds,
        MAX(t.result_state) AS result_state,
        COUNT(DISTINCT t.request_id) AS request_count,
        MAX(SIZE(t.refresh_selection)) AS refresh_selection_count,
        MAX(SIZE(t.full_refresh_selection)) AS full_refresh_selection_count,
        MAX(SIZE(t.reset_checkpoint_selection)) AS reset_checkpoint_selection_count
    FROM system.lakeflow.pipeline_update_timeline AS t
    INNER JOIN current_pipelines AS p
        ON t.workspace_id = p.workspace_id
       AND t.pipeline_id = p.pipeline_id
    GROUP BY
        t.workspace_id,
        t.pipeline_id,
        t.update_id
),

ranked_updates AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY workspace_id, pipeline_id
            ORDER BY
                update_end_time DESC,
                update_start_time DESC,
                update_id DESC
        ) AS update_rank
    FROM logical_updates
),

latest_update AS (
    SELECT *
    FROM ranked_updates
    WHERE update_rank = 1
)

SELECT
    p.account_id,
    p.workspace_id,
    p.pipeline_id,
    p.pipeline_name,
    p.pipeline_type,
    p.serverless,
    p.development_mode,
    p.continuous,
    p.edition,
    p.channel,
    p.create_time AS pipeline_created_at,
    p.change_time AS pipeline_last_changed_at,

    u.update_id AS latest_update_id,
    u.update_type AS latest_update_type,
    u.trigger_type AS latest_trigger_type,
    u.run_as_user_name AS latest_run_as_user_name,
    u.update_start_time AS latest_update_start_time,
    u.update_end_time AS latest_update_end_time,
    u.duration_seconds AS latest_update_duration_seconds,
    u.result_state AS latest_result_state,
    u.request_count,
    u.refresh_selection_count,
    u.full_refresh_selection_count,
    u.reset_checkpoint_selection_count,

    CASE
        WHEN u.update_id IS NULL THEN 'NEVER_RUN'
        WHEN u.result_state = 'COMPLETED' THEN 'HEALTHY'
        WHEN u.result_state IN ('FAILED', 'CANCELED') THEN 'FAILED'
        WHEN u.result_state IS NULL THEN 'IN_PROGRESS'
        ELSE 'UNKNOWN'
    END AS operational_status,

    CASE
        WHEN u.update_end_time IS NULL THEN NULL
        ELSE TIMESTAMPDIFF(
            HOUR,
            u.update_end_time,
            CURRENT_TIMESTAMP()
        )
    END AS hours_since_last_update

FROM current_pipelines AS p
LEFT JOIN latest_update AS u
    ON p.workspace_id = u.workspace_id
   AND p.pipeline_id = u.pipeline_id;
