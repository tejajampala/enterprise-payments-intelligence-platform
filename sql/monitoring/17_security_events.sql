-- ============================================================================
-- EPIP M17D — OPERATIONAL SECURITY AND AUDIT MONITORING
-- ============================================================================
--
-- Scope:
--   * selected EPIP-related audit events
--   * operational failures
--   * Unity Catalog governance changes
--   * deployment/job/pipeline changes where request metadata identifies EPIP
--
-- Security design:
--   * source IP addresses are intentionally NOT surfaced in the curated view
--   * request_params are used only for EPIP attribution and are not exposed
--   * raw system.access.audit access should remain restricted
-- ============================================================================


CREATE OR REPLACE VIEW payments_dev.monitoring.epip_security_events
COMMENT 'Curated EPIP security and governance audit events without exposing raw request parameters or source IP addresses.'
AS

WITH epip_workspaces AS (
    SELECT DISTINCT workspace_id
    FROM payments_dev.monitoring.current_epip_pipelines

    UNION

    SELECT DISTINCT workspace_id
    FROM payments_dev.monitoring.current_epip_jobs
),

audit_base AS (
    SELECT
        audit.account_id,
        audit.workspace_id,
        audit.event_time,
        audit.event_date,

        audit.service_name,
        audit.action_name,
        audit.request_id,
        audit.audit_level,
        audit.event_id,

        COALESCE(
            GET_JSON_OBJECT(TO_JSON(audit.user_identity), '$.email'),
            GET_JSON_OBJECT(TO_JSON(audit.user_identity), '$.userName')
        ) AS initiating_identity,

        COALESCE(
            GET_JSON_OBJECT(TO_JSON(audit.user_identity), '$.subject_name'),
            GET_JSON_OBJECT(TO_JSON(audit.user_identity), '$.subjectName')
        ) AS initiating_subject,

        COALESCE(
            GET_JSON_OBJECT(TO_JSON(audit.identity_metadata), '$.run_by'),
            GET_JSON_OBJECT(TO_JSON(audit.identity_metadata), '$.runBy')
        ) AS run_by_identity,

        COALESCE(
            GET_JSON_OBJECT(TO_JSON(audit.identity_metadata), '$.run_as'),
            GET_JSON_OBJECT(TO_JSON(audit.identity_metadata), '$.runAs')
        ) AS run_as_identity,

        TRY_CAST(
            COALESCE(
                GET_JSON_OBJECT(TO_JSON(audit.response), '$.status_code'),
                GET_JSON_OBJECT(TO_JSON(audit.response), '$.statusCode')
            )
            AS INT
        ) AS response_status_code,

        COALESCE(
            GET_JSON_OBJECT(TO_JSON(audit.response), '$.error_message'),
            GET_JSON_OBJECT(TO_JSON(audit.response), '$.errorMessage')
        ) AS response_error_message,

        LOWER(
            COALESCE(
                TO_JSON(audit.request_params),
                ''
            )
        ) AS request_context

    FROM system.access.audit AS audit

    LEFT JOIN epip_workspaces AS workspace_scope
        ON audit.workspace_id = workspace_scope.workspace_id

    WHERE audit.event_date >= CURRENT_DATE() - INTERVAL 30 DAYS

      AND (
          workspace_scope.workspace_id IS NOT NULL

          OR audit.workspace_id = '0'
      )
),

epip_attributed AS (
    SELECT
        *,

        CASE
            WHEN request_context RLIKE
                 '(payments_dev|payments_ci|payments_prod|epip)'
                THEN true

            WHEN LOWER(COALESCE(initiating_subject, '')) LIKE 'epip-%'
                THEN true

            WHEN LOWER(COALESCE(run_by_identity, '')) LIKE 'epip-%'
                THEN true

            WHEN LOWER(COALESCE(run_as_identity, '')) LIKE 'epip-%'
                THEN true

            ELSE false
        END AS epip_related

    FROM audit_base
)

SELECT
    account_id,
    workspace_id,
    event_time,
    event_date,

    service_name,
    action_name,
    request_id,
    audit_level,
    event_id,

    initiating_identity,
    initiating_subject,
    run_by_identity,
    run_as_identity,

    response_status_code,
    response_error_message,

    CASE
        WHEN response_status_code >= 500
            THEN 'CRITICAL'

        WHEN response_status_code >= 400
            THEN 'HIGH'

        WHEN LOWER(COALESCE(action_name, '')) RLIKE
             '(grant|revoke|permission|privilege|policy|tag|mask|rowfilter)'
            THEN 'MEDIUM'

        WHEN LOWER(COALESCE(action_name, '')) RLIKE
             '(create|update|delete|edit)'
            THEN 'MEDIUM'

        ELSE 'INFO'
    END AS event_severity,

    CASE
        WHEN response_status_code >= 400
            THEN 'OPERATION_FAILURE'

        WHEN LOWER(COALESCE(service_name, '')) = 'unitycatalog'
         AND LOWER(COALESCE(action_name, '')) RLIKE
             '(grant|revoke|permission|privilege|policy|tag|mask|rowfilter)'
            THEN 'GOVERNANCE_CHANGE'

        WHEN LOWER(COALESCE(action_name, '')) RLIKE
             '(create|update|delete|edit)'
            THEN 'RESOURCE_CHANGE'

        ELSE 'EPIP_ACTIVITY'
    END AS event_category

FROM epip_attributed

WHERE epip_related = true;


CREATE OR REPLACE VIEW payments_dev.monitoring.security_event_daily
COMMENT 'Daily EPIP security event counts by severity and category.'
AS

SELECT
    event_date,
    event_severity,
    event_category,

    COUNT(*) AS event_count,

    COUNT(
        DISTINCT COALESCE(
            initiating_identity,
            initiating_subject,
            run_by_identity,
            run_as_identity
        )
    ) AS distinct_actor_count

FROM payments_dev.monitoring.epip_security_events

GROUP BY
    event_date,
    event_severity,
    event_category;
