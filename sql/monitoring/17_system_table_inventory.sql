-- ============================================================================
-- EPIP M17B — DATABRICKS SYSTEM TABLE INVENTORY
-- ============================================================================
--
-- Inventory confirmed in the EPIP AWS Databricks workspace during M17B.
--
-- billing:
--   account_prices
--   attributed_usage
--   list_prices
--   usage
--
-- lakeflow:
--   job_run_timeline
--   job_task_run_timeline
--   job_tasks
--   jobs
--   pipeline_update_timeline
--   pipelines
--   zerobus_ingest
--   zerobus_stream
--
-- query:
--   history
--
-- compute:
--   clusters
--   instance_events
--   instance_pools
--   node_timeline
--   node_types
--   warehouse_events
--   warehouses
--
-- access:
--   assistant_events
--   audit
--   clean_room_events
--   column_lineage
--   inbound_network
--   outbound_network
--   table_lineage
--   workspaces_latest
--
-- M17B uses only the minimum foundation set. Later M17 stages intentionally
-- add DQ, query, audit, compute, ML/agent and cost-specific views.
-- ============================================================================


-- ---------------------------------------------------------------------------
-- 1. Re-run schema/table discovery when validating another workspace.
-- ---------------------------------------------------------------------------

SHOW SCHEMAS IN system;

SHOW TABLES IN system.billing;
SHOW TABLES IN system.lakeflow;
SHOW TABLES IN system.query;
SHOW TABLES IN system.compute;
SHOW TABLES IN system.access;


-- ---------------------------------------------------------------------------
-- 2. Foundation source contracts.
-- ---------------------------------------------------------------------------

DESCRIBE TABLE system.lakeflow.pipelines;
DESCRIBE TABLE system.lakeflow.pipeline_update_timeline;

DESCRIBE TABLE system.lakeflow.jobs;
DESCRIBE TABLE system.lakeflow.job_run_timeline;
DESCRIBE TABLE system.lakeflow.job_task_run_timeline;

DESCRIBE TABLE system.query.history;

DESCRIBE TABLE system.billing.usage;
DESCRIBE TABLE system.billing.list_prices;

DESCRIBE TABLE system.access.audit;

DESCRIBE TABLE system.compute.warehouses;
DESCRIBE TABLE system.compute.warehouse_events;


-- ---------------------------------------------------------------------------
-- 3. Lightweight source-readiness checks.
-- These queries do not assume that EPIP generated activity exists today.
-- ---------------------------------------------------------------------------

SELECT
    COUNT(*) AS pipeline_definition_rows,
    MAX(change_time) AS latest_pipeline_change_time
FROM system.lakeflow.pipelines;

SELECT
    COUNT(*) AS pipeline_update_rows,
    MAX(period_end_time) AS latest_pipeline_update_time
FROM system.lakeflow.pipeline_update_timeline
WHERE period_start_time >= CURRENT_TIMESTAMP() - INTERVAL 30 DAYS;

SELECT
    COUNT(*) AS job_definition_rows,
    MAX(change_time) AS latest_job_change_time
FROM system.lakeflow.jobs;

SELECT
    COUNT(*) AS job_run_rows,
    MAX(period_end_time) AS latest_job_run_time
FROM system.lakeflow.job_run_timeline
WHERE period_start_time >= CURRENT_TIMESTAMP() - INTERVAL 30 DAYS;

SELECT
    COUNT(*) AS query_rows,
    MAX(update_time) AS latest_query_update_time
FROM system.query.history
WHERE start_time >= CURRENT_TIMESTAMP() - INTERVAL 30 DAYS;

SELECT
    COUNT(*) AS billing_rows,
    MAX(usage_end_time) AS latest_billing_usage_time
FROM system.billing.usage
WHERE usage_date >= CURRENT_DATE() - INTERVAL 30 DAYS;

SELECT
    COUNT(*) AS audit_rows,
    MAX(event_time) AS latest_audit_event_time
FROM system.access.audit
WHERE event_date >= CURRENT_DATE() - INTERVAL 30 DAYS;
