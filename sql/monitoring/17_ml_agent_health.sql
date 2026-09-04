-- ============================================================================
-- EPIP M17D — ML AND AGENT OPERATIONAL HEALTH
-- ============================================================================
--
-- ML boundary:
-- EPIP persists current Champion scoring evidence in governed tables/views.
-- Historical AP/F2 training metrics remain in MLflow tracking and are not
-- invented as SQL history here.
--
-- Agent boundary:
-- M13 persists both run-level evaluation summaries and case-level results,
-- including MLflow trace IDs for failed-case diagnostics.
-- ============================================================================


-- ============================================================================
-- VIEW 1 — CURRENT FRAUD MODEL SCORING HEALTH
-- ============================================================================

CREATE OR REPLACE VIEW payments_dev.monitoring.fraud_model_current_health
COMMENT 'Current Champion fraud-scoring evidence, distribution and freshness from governed EPIP scoring outputs.'
AS

SELECT
    MAX(scored_at) AS latest_scored_at,

    MAX_BY(
        registered_model_name,
        scored_at
    ) AS registered_model_name,

    MAX_BY(
        model_version,
        scored_at
    ) AS model_version,

    MAX_BY(
        model_alias,
        scored_at
    ) AS model_alias,

    COUNT(*) AS transactions_scored,

    AVG(fraud_probability)
        AS avg_fraud_probability,

    SUM(
        CASE
            WHEN predicted_fraud = 1
            THEN 1 ELSE 0
        END
    ) AS predicted_fraud_count,

    AVG(
        CASE
            WHEN predicted_fraud = 1
            THEN 1.0 ELSE 0.0
        END
    ) AS predicted_fraud_rate,

    SUM(
        CASE
            WHEN fraud_probability >= 0.80
            THEN 1 ELSE 0
        END
    ) AS high_risk_transaction_count,

    AVG(
        CASE
            WHEN fraud_probability >= 0.80
            THEN 1.0 ELSE 0.0
        END
    ) AS high_risk_rate,

    CASE
        WHEN MAX(scored_at) IS NULL
            THEN 'NO_SCORING_EVIDENCE'

        WHEN MAX(scored_at) >= CURRENT_TIMESTAMP() - INTERVAL 7 DAYS
            THEN 'RECENT'

        ELSE 'STALE'
    END AS scoring_freshness_status,

    CASE
        WHEN MAX(scored_at) IS NULL THEN NULL
        ELSE TIMESTAMPDIFF(
            HOUR,
            MAX(scored_at),
            CURRENT_TIMESTAMP()
        )
    END AS scoring_age_hours

FROM payments_dev.analytics.fraud_model_operations_base;


-- ============================================================================
-- VIEW 2 — AGENT EVALUATION HEALTH HISTORY
-- ============================================================================

CREATE OR REPLACE VIEW payments_dev.monitoring.agent_evaluation_health
COMMENT 'Persisted EPIP fraud-agent evaluation and regression-gate history.'
AS

SELECT
    evaluation_run_id,
    agent_version,
    generation_model,
    judge_model,

    case_count,
    passed_cases,
    failed_cases,
    pass_rate,

    avg_tool_selection_score,
    avg_tool_argument_score,
    avg_tool_efficiency_score,

    avg_groundedness_score,
    avg_evidence_completeness_score,
    avg_investigation_quality_score,
    avg_citation_score,

    scope_compliance_rate,
    human_review_rate,
    safety_rate,
    structure_compliance_rate,

    avg_duration_seconds,

    overall_pass,
    failed_gates,
    created_at,

    CASE
        WHEN overall_pass THEN 'HEALTHY'
        ELSE 'REGRESSION_FAILED'
    END AS agent_health_status,

    TIMESTAMPDIFF(
        HOUR,
        created_at,
        CURRENT_TIMESTAMP()
    ) AS evidence_age_hours

FROM payments_dev.ai.agent_evaluation_summary;


-- ============================================================================
-- VIEW 3 — LATEST AGENT HEALTH
-- ============================================================================

CREATE OR REPLACE VIEW payments_dev.monitoring.agent_latest_health
COMMENT 'Latest formal EPIP fraud-agent evaluation evidence used for operational monitoring.'
AS

SELECT *
FROM payments_dev.monitoring.agent_evaluation_health

QUALIFY
    ROW_NUMBER() OVER (
        ORDER BY created_at DESC, evaluation_run_id DESC
    ) = 1;


-- ============================================================================
-- VIEW 4 — FAILED AGENT CASE DIAGNOSTICS
-- ============================================================================

CREATE OR REPLACE VIEW payments_dev.monitoring.agent_failed_case_diagnostics
COMMENT 'Failed M13 fraud-agent evaluation cases with MLflow trace linkage for diagnosis.'
AS

SELECT
    evaluation_run_id,
    case_id,
    scenario_type,
    transaction_id,

    agent_version,
    generation_model,
    judge_model,

    trace_id,

    tools_used,
    tool_call_count,

    tool_selection_score,
    tool_argument_score,
    tool_efficiency_score,

    scope_compliance_score,
    structure_score,
    citation_score,
    human_review_score,
    safety_score,

    groundedness_score,
    evidence_completeness_score,
    investigation_quality_score,
    risk_balance_score,
    uncertainty_score,

    overall_score,
    failure_reasons,
    judge_rationale,

    duration_seconds,
    created_at

FROM payments_dev.ai.agent_evaluation_results

WHERE case_pass = false;
