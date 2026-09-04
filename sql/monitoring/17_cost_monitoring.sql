-- ============================================================================
-- EPIP M17D — DATABRICKS COST ATTRIBUTION AND OPTIMISATION
-- ============================================================================
--
-- Cost semantics:
--   * system.billing.usage includes ORIGINAL / RETRACTION / RESTATEMENT rows.
--   * Do NOT filter only ORIGINAL rows. Summing usage/cost allows retractions
--     and restatements to produce the corrected total.
--   * list price uses pricing.effective_list.default when available.
--
-- Scope:
--   Databricks platform list-price estimation for EPIP workspaces.
--
-- Explicitly NOT included:
--   Amazon MSK cost
--   Amazon S3 cost
--   AWS data transfer / networking bill
--   taxes, negotiated discounts, credits or complete cloud invoice
-- ============================================================================


-- ============================================================================
-- VIEW 1 — USAGE + LIST-PRICE DETAIL
-- ============================================================================

CREATE OR REPLACE VIEW payments_dev.monitoring.databricks_usage_cost_detail
COMMENT 'Databricks usage records for EPIP workspaces enriched with effective list price and workload attribution.'
AS

WITH epip_workspaces AS (
    SELECT DISTINCT workspace_id
    FROM payments_dev.monitoring.current_epip_pipelines

    UNION

    SELECT DISTINCT workspace_id
    FROM payments_dev.monitoring.current_epip_jobs
),

priced_usage AS (
    SELECT
        usage.record_id,
        usage.account_id,
        usage.workspace_id,

        usage.sku_name,
        usage.cloud,

        usage.usage_start_time,
        usage.usage_end_time,
        usage.usage_date,

        usage.usage_unit,
        usage.usage_quantity,

        usage.record_type,
        usage.billing_origin_product,
        usage.usage_type,

        usage.custom_tags,

        usage.usage_metadata.job_id AS job_id,
        usage.usage_metadata.job_run_id AS job_run_id,
        usage.usage_metadata.job_name AS billing_job_name,

        usage.usage_metadata.dlt_pipeline_id AS pipeline_id,
        usage.usage_metadata.dlt_update_id AS pipeline_update_id,

        usage.usage_metadata.warehouse_id AS warehouse_id,
        usage.usage_metadata.cluster_id AS cluster_id,
        usage.usage_metadata.notebook_id AS notebook_id,
        usage.usage_metadata.notebook_path AS notebook_path,

        usage.usage_metadata.endpoint_id AS endpoint_id,
        usage.usage_metadata.endpoint_name AS endpoint_name,

        usage.identity_metadata.run_as AS run_as_identity,

        price.currency_code,

        CAST(
            price.pricing.effective_list.default
            AS DOUBLE
        ) AS effective_list_unit_price,

        ROW_NUMBER() OVER (
            PARTITION BY usage.record_id
            ORDER BY price.price_start_time DESC
        ) AS price_rank

    FROM system.billing.usage AS usage

    INNER JOIN epip_workspaces AS workspace_scope
        ON usage.workspace_id = workspace_scope.workspace_id

    LEFT JOIN system.billing.list_prices AS price
        ON usage.account_id = price.account_id
       AND usage.sku_name = price.sku_name
       AND usage.cloud = price.cloud
       AND usage.usage_unit = price.usage_unit
       AND usage.usage_start_time >= price.price_start_time
       AND (
            price.price_end_time IS NULL
            OR usage.usage_start_time < price.price_end_time
       )

    WHERE usage.usage_date >= CURRENT_DATE() - INTERVAL 90 DAYS
)

SELECT
    usage.record_id,
    usage.account_id,
    usage.workspace_id,

    usage.usage_date,
    usage.usage_start_time,
    usage.usage_end_time,

    usage.sku_name,
    usage.cloud,
    usage.usage_unit,
    usage.usage_quantity,

    usage.record_type,
    usage.billing_origin_product,
    usage.usage_type,

    usage.currency_code,
    usage.effective_list_unit_price,

    usage.usage_quantity
      * COALESCE(usage.effective_list_unit_price, 0)
        AS estimated_list_cost,

    usage.job_id,
    usage.job_run_id,

    usage.pipeline_id,
    usage.pipeline_update_id,

    usage.warehouse_id,
    usage.cluster_id,

    usage.notebook_id,
    usage.notebook_path,

    usage.endpoint_id,
    usage.endpoint_name,

    usage.run_as_identity,
    usage.custom_tags,

    CASE
        WHEN usage.job_id IS NOT NULL
            THEN 'JOB'

        WHEN usage.pipeline_id IS NOT NULL
            THEN 'LAKEFLOW_PIPELINE'

        WHEN usage.warehouse_id IS NOT NULL
            THEN 'SQL_WAREHOUSE'

        WHEN usage.endpoint_name IS NOT NULL
            THEN 'ENDPOINT'

        WHEN usage.notebook_id IS NOT NULL
            THEN 'NOTEBOOK'

        ELSE COALESCE(
            usage.billing_origin_product,
            'OTHER'
        )
    END AS workload_type,

    CASE
        WHEN usage.job_id IS NOT NULL
            THEN COALESCE(
                job.job_name,
                usage.billing_job_name,
                CONCAT('job:', usage.job_id)
            )

        WHEN usage.pipeline_id IS NOT NULL
            THEN COALESCE(
                pipeline.pipeline_name,
                CONCAT('pipeline:', usage.pipeline_id)
            )

        WHEN usage.warehouse_id IS NOT NULL
            THEN COALESCE(
                warehouse.warehouse_name,
                CONCAT('warehouse:', usage.warehouse_id)
            )

        WHEN usage.endpoint_name IS NOT NULL
            THEN usage.endpoint_name

        WHEN usage.notebook_path IS NOT NULL
            THEN usage.notebook_path

        ELSE COALESCE(
            usage.billing_origin_product,
            usage.sku_name
        )
    END AS workload_name,

    CASE
        WHEN job.job_id IS NOT NULL
          OR pipeline.pipeline_id IS NOT NULL
            THEN 'DIRECT_EPIP_RESOURCE'

        WHEN usage.workspace_id IS NOT NULL
            THEN 'EPIP_WORKSPACE'

        ELSE 'UNATTRIBUTED'
    END AS attribution_quality

FROM priced_usage AS usage

LEFT JOIN payments_dev.monitoring.current_epip_jobs AS job
    ON usage.workspace_id = job.workspace_id
   AND CAST(usage.job_id AS STRING) = job.job_id

LEFT JOIN payments_dev.monitoring.current_epip_pipelines AS pipeline
    ON usage.workspace_id = pipeline.workspace_id
   AND CAST(usage.pipeline_id AS STRING) = pipeline.pipeline_id

LEFT JOIN payments_dev.monitoring.warehouse_operational_health AS warehouse
    ON usage.workspace_id = warehouse.workspace_id
   AND usage.warehouse_id = warehouse.warehouse_id

WHERE usage.price_rank = 1;


-- ============================================================================
-- VIEW 2 — DAILY DATABRICKS COST
-- ============================================================================

CREATE OR REPLACE VIEW payments_dev.monitoring.databricks_cost_daily
COMMENT 'Corrected daily Databricks usage and estimated list cost for EPIP workspaces.'
AS

SELECT
    usage_date,
    currency_code,

    SUM(usage_quantity) AS usage_quantity,

    SUM(estimated_list_cost) AS estimated_list_cost,

    COUNT(*) AS billing_record_count,

    COUNT(
        DISTINCT sku_name
    ) AS sku_count,

    COUNT(
        DISTINCT workload_name
    ) AS workload_count

FROM payments_dev.monitoring.databricks_usage_cost_detail

GROUP BY
    usage_date,
    currency_code

HAVING ABS(SUM(usage_quantity)) > 0
    OR ABS(SUM(estimated_list_cost)) > 0;


-- ============================================================================
-- VIEW 3 — COST BY SKU
-- ============================================================================

CREATE OR REPLACE VIEW payments_dev.monitoring.databricks_cost_by_sku
COMMENT 'Databricks estimated list cost by SKU for the last 30 days.'
AS

SELECT
    sku_name,
    billing_origin_product,
    usage_type,
    currency_code,

    SUM(usage_quantity) AS usage_quantity,
    SUM(estimated_list_cost) AS estimated_list_cost

FROM payments_dev.monitoring.databricks_usage_cost_detail

WHERE usage_date >= CURRENT_DATE() - INTERVAL 30 DAYS

GROUP BY
    sku_name,
    billing_origin_product,
    usage_type,
    currency_code

HAVING ABS(SUM(usage_quantity)) > 0
    OR ABS(SUM(estimated_list_cost)) > 0;


-- ============================================================================
-- VIEW 4 — COST BY WORKLOAD
-- ============================================================================

CREATE OR REPLACE VIEW payments_dev.monitoring.databricks_cost_by_workload
COMMENT 'Databricks estimated list cost by attributable workload for the last 30 days.'
AS

SELECT
    workload_type,
    workload_name,
    attribution_quality,
    currency_code,

    SUM(usage_quantity) AS usage_quantity,
    SUM(estimated_list_cost) AS estimated_list_cost,

    MIN(usage_date) AS first_usage_date,
    MAX(usage_date) AS latest_usage_date

FROM payments_dev.monitoring.databricks_usage_cost_detail

WHERE usage_date >= CURRENT_DATE() - INTERVAL 30 DAYS

GROUP BY
    workload_type,
    workload_name,
    attribution_quality,
    currency_code

HAVING ABS(SUM(usage_quantity)) > 0
    OR ABS(SUM(estimated_list_cost)) > 0;


-- ============================================================================
-- VIEW 5 — COST OPTIMISATION CANDIDATES
-- ============================================================================

CREATE OR REPLACE VIEW payments_dev.monitoring.cost_optimisation_candidates
COMMENT 'Evidence-based Databricks cost optimisation candidates without claiming complete AWS cost coverage.'
AS

WITH failed_job_cost AS (
    SELECT
        'FAILED_JOB_COST' AS candidate_type,

        CONCAT(
            cost.workload_name,
            ' / run ',
            COALESCE(CAST(cost.job_run_id AS STRING), 'unknown')
        ) AS resource_name,

        cost.currency_code,

        SUM(cost.estimated_list_cost) AS estimated_list_cost,

        'Review repeated failed/retried jobs before increasing compute.' AS recommendation

    FROM payments_dev.monitoring.databricks_usage_cost_detail AS cost

    INNER JOIN payments_dev.monitoring.epip_job_run_health AS run
        ON cost.workspace_id = run.workspace_id
       AND CAST(cost.job_id AS STRING) = run.job_id
       AND CAST(cost.job_run_id AS STRING) = run.run_id

    WHERE cost.usage_date >= CURRENT_DATE() - INTERVAL 30 DAYS
      AND run.result_state IN (
          'FAILED',
          'CANCELLED',
          'TIMED_OUT',
          'ERROR',
          'BLOCKED'
      )

    GROUP BY
        cost.workload_name,
        cost.job_run_id,
        cost.currency_code

    HAVING SUM(cost.estimated_list_cost) > 0
),

ranked_workloads AS (
    SELECT
        workload_type,
        workload_name,
        currency_code,
        estimated_list_cost,

        ROW_NUMBER() OVER (
            PARTITION BY currency_code
            ORDER BY estimated_list_cost DESC
        ) AS cost_rank

    FROM payments_dev.monitoring.databricks_cost_by_workload

    WHERE estimated_list_cost > 0
),

top_workloads AS (
    SELECT
        'TOP_COST_WORKLOAD' AS candidate_type,
        CONCAT(workload_type, ': ', workload_name) AS resource_name,
        currency_code,
        estimated_list_cost,

        'Validate workload value, runtime, failures and scheduling before optimising.' AS recommendation

    FROM ranked_workloads

    WHERE cost_rank <= 5
),

warehouse_candidates AS (
    SELECT
        'WAREHOUSE_AUTOSTOP_REVIEW' AS candidate_type,
        warehouse_name AS resource_name,
        CAST(NULL AS STRING) AS currency_code,
        CAST(NULL AS DOUBLE) AS estimated_list_cost,

        CONCAT(
            'Warehouse auto-stop is ',
            CAST(auto_stop_minutes AS STRING),
            ' minutes; review against interactive usage.'
        ) AS recommendation

    FROM payments_dev.monitoring.warehouse_operational_health

    WHERE COALESCE(auto_stop_minutes, 0) > 30
)

SELECT * FROM failed_job_cost
UNION ALL
SELECT * FROM top_workloads
UNION ALL
SELECT * FROM warehouse_candidates;
