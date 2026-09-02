-- Milestone 14B — AI/BI Dashboard dataset queries
-- Metric-view measures must be referenced through MEASURE(...).

-- PAGE 1 — EXECUTIVE PAYMENTS

-- Dataset: payments_kpis
SELECT
    MEASURE(transaction_count) AS transaction_count,
    MEASURE(total_payment_value) AS total_payment_value,
    MEASURE(average_transaction_value) AS average_transaction_value,
    MEASURE(authorization_rate) AS authorization_rate,
    MEASURE(decline_rate) AS decline_rate
FROM payments_dev.analytics.payment_operations_metrics;

-- Dataset: payments_daily_trend
SELECT
    event_date,
    MEASURE(transaction_count) AS transaction_count,
    MEASURE(total_payment_value) AS total_payment_value
FROM payments_dev.analytics.payment_operations_metrics
GROUP BY event_date
ORDER BY event_date;

-- Dataset: payments_by_channel
SELECT
    channel,
    MEASURE(transaction_count) AS transaction_count,
    MEASURE(total_payment_value) AS total_payment_value,
    MEASURE(average_transaction_value) AS average_transaction_value,
    MEASURE(authorization_rate) AS authorization_rate,
    MEASURE(decline_rate) AS decline_rate
FROM payments_dev.analytics.payment_operations_metrics
GROUP BY channel
ORDER BY total_payment_value DESC;

-- Dataset: payments_by_method
SELECT
    payment_method,
    MEASURE(transaction_count) AS transaction_count,
    MEASURE(total_payment_value) AS total_payment_value,
    MEASURE(decline_rate) AS decline_rate
FROM payments_dev.analytics.payment_operations_metrics
GROUP BY payment_method
ORDER BY total_payment_value DESC;

-- Dataset: payments_by_country
SELECT
    transaction_country,
    MEASURE(transaction_count) AS transaction_count,
    MEASURE(total_payment_value) AS total_payment_value
FROM payments_dev.analytics.payment_operations_metrics
GROUP BY transaction_country
ORDER BY total_payment_value DESC;

-- Dataset: merchant_payment_performance
SELECT
    merchant_name,
    merchant_category_code,
    merchant_country,
    MEASURE(transaction_count) AS transaction_count,
    MEASURE(total_payment_value) AS total_payment_value,
    MEASURE(average_transaction_value) AS average_transaction_value,
    MEASURE(decline_rate) AS decline_rate
FROM payments_dev.analytics.payment_operations_metrics
GROUP BY
    merchant_name,
    merchant_category_code,
    merchant_country
ORDER BY total_payment_value DESC;

-- PAGE 2 — FRAUD INTELLIGENCE

-- Dataset: fraud_kpis
SELECT
    MEASURE(transactions_scored) AS transactions_scored,
    MEASURE(predicted_fraud_count) AS predicted_fraud_count,
    MEASURE(predicted_fraud_rate) AS predicted_fraud_rate,
    MEASURE(average_fraud_probability) AS average_fraud_probability,
    MEASURE(high_risk_transaction_count) AS high_risk_transaction_count
FROM payments_dev.analytics.fraud_model_metrics;

-- Dataset: fraud_daily_trend
SELECT
    event_date,
    MEASURE(transactions_scored) AS transactions_scored,
    MEASURE(predicted_fraud_rate) AS predicted_fraud_rate,
    MEASURE(average_fraud_probability) AS average_fraud_probability,
    MEASURE(high_risk_transaction_count) AS high_risk_transaction_count
FROM payments_dev.analytics.fraud_model_metrics
GROUP BY event_date
ORDER BY event_date;

-- Dataset: fraud_by_risk_band
SELECT
    risk_band,
    MEASURE(transactions_scored) AS transactions_scored,
    MEASURE(predicted_fraud_count) AS predicted_fraud_count,
    MEASURE(average_fraud_probability) AS average_fraud_probability
FROM payments_dev.analytics.fraud_model_metrics
GROUP BY risk_band
ORDER BY average_fraud_probability DESC;

-- Dataset: fraud_by_channel
SELECT
    channel,
    MEASURE(transactions_scored) AS transactions_scored,
    MEASURE(predicted_fraud_rate) AS predicted_fraud_rate,
    MEASURE(average_fraud_probability) AS average_fraud_probability,
    MEASURE(high_risk_transaction_count) AS high_risk_transaction_count
FROM payments_dev.analytics.fraud_model_metrics
GROUP BY channel
ORDER BY average_fraud_probability DESC;

-- Dataset: fraud_cross_border
SELECT
    is_cross_border,
    MEASURE(transactions_scored) AS transactions_scored,
    MEASURE(high_risk_transaction_count) AS high_risk_transaction_count,
    MEASURE(cross_border_high_risk_count) AS cross_border_high_risk_count,
    MEASURE(average_fraud_probability) AS average_fraud_probability
FROM payments_dev.analytics.fraud_model_metrics
GROUP BY is_cross_border
ORDER BY is_cross_border DESC;

-- Dataset: merchant_model_risk
SELECT
    merchant_name,
    MEASURE(transactions_scored) AS transactions_scored,
    MEASURE(predicted_fraud_rate) AS predicted_fraud_rate,
    MEASURE(average_fraud_probability) AS average_fraud_probability,
    MEASURE(high_risk_transaction_count) AS high_risk_transaction_count
FROM payments_dev.analytics.fraud_model_metrics
GROUP BY merchant_name
ORDER BY average_fraud_probability DESC;

-- PAGE 3 — FRAUD AGENT QUALITY

-- Dataset: agent_quality_kpis
SELECT
    MEASURE(evaluated_cases) AS evaluated_cases,
    MEASURE(case_pass_rate) AS case_pass_rate,
    MEASURE(average_overall_score) AS average_overall_score,
    MEASURE(average_groundedness) AS average_groundedness,
    MEASURE(average_evidence_completeness) AS average_evidence_completeness,
    MEASURE(scope_compliance_rate) AS scope_compliance_rate,
    MEASURE(safety_compliance_rate) AS safety_compliance_rate,
    MEASURE(human_review_compliance_rate) AS human_review_compliance_rate,
    MEASURE(average_duration_seconds) AS average_duration_seconds
FROM payments_dev.analytics.agent_quality_metrics;

-- Dataset: agent_quality_by_scenario
SELECT
    scenario_type,
    MEASURE(evaluated_cases) AS evaluated_cases,
    MEASURE(case_pass_rate) AS case_pass_rate,
    MEASURE(average_overall_score) AS average_overall_score,
    MEASURE(average_groundedness) AS average_groundedness,
    MEASURE(average_evidence_completeness) AS average_evidence_completeness,
    MEASURE(average_tool_efficiency) AS average_tool_efficiency
FROM payments_dev.analytics.agent_quality_metrics
GROUP BY scenario_type
ORDER BY scenario_type;

-- Dataset: agent_tool_quality
SELECT
    scenario_type,
    MEASURE(average_tool_selection) AS average_tool_selection,
    MEASURE(average_tool_argument_score) AS average_tool_argument_score,
    MEASURE(average_tool_efficiency) AS average_tool_efficiency,
    MEASURE(average_citation_score) AS average_citation_score
FROM payments_dev.analytics.agent_quality_metrics
GROUP BY scenario_type
ORDER BY scenario_type;

-- Dataset: agent_safety_quality
SELECT
    scenario_type,
    MEASURE(scope_compliance_rate) AS scope_compliance_rate,
    MEASURE(safety_compliance_rate) AS safety_compliance_rate,
    MEASURE(human_review_compliance_rate) AS human_review_compliance_rate
FROM payments_dev.analytics.agent_quality_metrics
GROUP BY scenario_type
ORDER BY scenario_type;

-- Dataset: failed_agent_cases
SELECT
    evaluation_run_id,
    case_id,
    scenario_type,
    transaction_id,
    generation_model,
    judge_model,
    overall_score,
    groundedness_score,
    evidence_completeness_score,
    tool_selection_score,
    tool_efficiency_score,
    failure_reasons,
    judge_rationale,
    trace_id,
    created_at
FROM payments_dev.analytics.agent_quality_base
WHERE case_pass = false
ORDER BY created_at DESC, case_id;
