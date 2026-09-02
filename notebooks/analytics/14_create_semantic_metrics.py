# Databricks notebook source
"""Milestone 14A — create the governed EPIP analytics semantic layer.

This notebook creates:
- three narrow analytics base views
- three Unity Catalog metric views

The metric views become the shared semantic contract for:
- AI/BI dashboards
- Genie
- SQL analysis
- future BI consumers

M14 intentionally does not change the Gold medallion layer. The analytics
schema sits above Gold/Silver/ML/AI assets and standardizes reusable business
metrics for consumption.
"""

from __future__ import annotations

import re

from pyspark.sql import SparkSession

# COMMAND ----------

spark = SparkSession.getActiveSession()

if spark is None:
    raise RuntimeError("No active SparkSession is available for M14 analytics setup")


def validate_identifier(value: str, label: str) -> str:
    """Validate a simple Unity Catalog identifier before SQL interpolation."""

    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError(f"Invalid {label}: {value!r}")

    return value


dbutils.widgets.text("catalog_name", "payments_dev")

CATALOG = validate_identifier(
    dbutils.widgets.get("catalog_name").strip(),
    "catalog_name",
)

ANALYTICS_SCHEMA = "analytics"

PAYMENT_BASE_VIEW = f"{CATALOG}.{ANALYTICS_SCHEMA}.payment_operations_base"
FRAUD_BASE_VIEW = f"{CATALOG}.{ANALYTICS_SCHEMA}.fraud_model_operations_base"
AGENT_BASE_VIEW = f"{CATALOG}.{ANALYTICS_SCHEMA}.agent_quality_base"

PAYMENT_METRIC_VIEW = f"{CATALOG}.{ANALYTICS_SCHEMA}.payment_operations_metrics"
FRAUD_METRIC_VIEW = f"{CATALOG}.{ANALYTICS_SCHEMA}.fraud_model_metrics"
AGENT_METRIC_VIEW = f"{CATALOG}.{ANALYTICS_SCHEMA}.agent_quality_metrics"

TRANSACTION_SOURCE = f"{CATALOG}.silver.payment_transactions_enriched"
FRAUD_EVIDENCE_SOURCE = f"{CATALOG}.ai.agent_fraud_evidence"
TRANSACTION_CONTEXT_SOURCE = f"{CATALOG}.ai.agent_transaction_context"
AGENT_EVALUATION_SOURCE = f"{CATALOG}.ai.agent_evaluation_results"

# COMMAND ----------
# Validate required upstream assets.

required_assets = (
    TRANSACTION_SOURCE,
    FRAUD_EVIDENCE_SOURCE,
    TRANSACTION_CONTEXT_SOURCE,
    AGENT_EVALUATION_SOURCE,
)

missing_assets = [asset for asset in required_assets if not spark.catalog.tableExists(asset)]

if missing_assets:
    raise RuntimeError(f"M14 requires completed M5/M10/M12/M13 assets. Missing assets: {missing_assets}")

spark.sql(
    f"""
    CREATE SCHEMA IF NOT EXISTS {CATALOG}.{ANALYTICS_SCHEMA}
    COMMENT 'Governed semantic analytics assets for AI/BI and Genie.'
    """
)

# COMMAND ----------
# Payment operations base view.

spark.sql(
    f"""
    CREATE OR REPLACE VIEW {PAYMENT_BASE_VIEW}

    COMMENT
    'Transaction-grain semantic source for payment operations analytics.'

    AS

    SELECT
        transaction_id,
        CAST(event_date AS DATE) AS event_date,
        event_timestamp,

        CAST(amount AS DOUBLE) AS amount,
        currency,

        channel,
        payment_method,
        transaction_status,

        COALESCE(card_present, false) AS card_present,

        customer_id,

        merchant_id,
        merchant_name,
        merchant_category_code,

        transaction_country,
        merchant_country

    FROM {TRANSACTION_SOURCE}
    """
)

# COMMAND ----------
# Fraud model analytics base view.

spark.sql(
    f"""
    CREATE OR REPLACE VIEW {FRAUD_BASE_VIEW}

    COMMENT
    'Leakage-safe transaction and Champion fraud-model signals for analytics.'

    AS

    SELECT
        evidence.transaction_id,

        CAST(evidence.event_timestamp AS DATE) AS event_date,
        evidence.event_timestamp,

        CAST(evidence.amount AS DOUBLE) AS amount,

        context.currency,
        context.channel,
        context.payment_method,
        context.transaction_country,

        context.merchant_id,
        context.merchant_name,
        context.merchant_category_code,
        context.merchant_country,

        evidence.is_cross_border,
        evidence.is_card_not_present,

        CAST(evidence.fraud_probability AS DOUBLE) AS fraud_probability,
        CAST(evidence.predicted_fraud AS INT) AS predicted_fraud,

        CASE
            WHEN evidence.fraud_probability >= 0.80 THEN 'HIGH'
            WHEN evidence.fraud_probability >= 0.50 THEN 'MEDIUM'
            ELSE 'LOW'
        END AS risk_band,

        evidence.customer_txn_count_1d,
        evidence.customer_txn_count_7d,
        evidence.customer_txn_count_30d,

        evidence.customer_decline_rate_30d,
        evidence.customer_foreign_rate_30d,
        evidence.customer_card_not_present_rate_30d,

        evidence.merchant_txn_count_1d,
        evidence.merchant_txn_count_7d,
        evidence.merchant_txn_count_30d,

        evidence.merchant_decline_rate_30d,
        evidence.merchant_foreign_rate_30d,
        evidence.merchant_card_not_present_rate_30d,

        evidence.registered_model_name,
        evidence.model_version,
        evidence.model_alias,
        evidence.scored_at

    FROM {FRAUD_EVIDENCE_SOURCE} AS evidence

    INNER JOIN {TRANSACTION_CONTEXT_SOURCE} AS context
        ON evidence.transaction_id = context.transaction_id

    WHERE evidence.fraud_probability IS NOT NULL
    """
)

# COMMAND ----------
# Agent quality base view.

spark.sql(
    f"""
    CREATE OR REPLACE VIEW {AGENT_BASE_VIEW}

    COMMENT
    'Semantic source for fraud-agent quality, safety and regression analytics.'

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

        CAST(tool_selection_score AS DOUBLE) AS tool_selection_score,
        CAST(tool_argument_score AS DOUBLE) AS tool_argument_score,
        CAST(tool_efficiency_score AS DOUBLE) AS tool_efficiency_score,

        CAST(scope_compliance_score AS DOUBLE) AS scope_compliance_score,
        CAST(structure_score AS DOUBLE) AS structure_score,
        CAST(citation_score AS DOUBLE) AS citation_score,
        CAST(human_review_score AS DOUBLE) AS human_review_score,
        CAST(safety_score AS DOUBLE) AS safety_score,

        CAST(groundedness_score AS DOUBLE) AS groundedness_score,
        CAST(evidence_completeness_score AS DOUBLE)
            AS evidence_completeness_score,
        CAST(investigation_quality_score AS DOUBLE)
            AS investigation_quality_score,
        CAST(risk_balance_score AS DOUBLE) AS risk_balance_score,
        CAST(uncertainty_score AS DOUBLE) AS uncertainty_score,

        judge_rationale,

        CAST(duration_seconds AS DOUBLE) AS duration_seconds,
        CAST(overall_score AS DOUBLE) AS overall_score,

        case_pass,
        failure_reasons,

        created_at

    FROM {AGENT_EVALUATION_SOURCE}
    """
)

# COMMAND ----------
# Payment operations metric view.

spark.sql(
    f"""
    CREATE OR REPLACE VIEW {PAYMENT_METRIC_VIEW}
    WITH METRICS
    LANGUAGE YAML
    AS
    $$
    version: 1.1

    comment: |-
      Governed payment operations metrics for EPIP executive analytics,
      AI/BI dashboards, Genie and reusable SQL analysis.

    source: {PAYMENT_BASE_VIEW}

    fields:
      - name: event_date
        expr: source.event_date
        display_name: Payment Date
        comment: Business date of the payment transaction.

      - name: currency
        expr: source.currency
        display_name: Currency
        comment: ISO payment currency.

      - name: channel
        expr: source.channel
        display_name: Payment Channel
        comment: Payment origination channel.

      - name: payment_method
        expr: source.payment_method
        display_name: Payment Method
        comment: Payment instrument or payment method.

      - name: transaction_status
        expr: source.transaction_status
        display_name: Transaction Status
        comment: Current transaction status.

      - name: transaction_country
        expr: source.transaction_country
        display_name: Transaction Country
        comment: Country associated with the payment.

      - name: merchant_id
        expr: source.merchant_id
        display_name: Merchant ID
        comment: Synthetic EPIP merchant identifier.

      - name: merchant_name
        expr: source.merchant_name
        display_name: Merchant
        comment: Synthetic merchant name.

      - name: merchant_category_code
        expr: source.merchant_category_code
        display_name: Merchant Category
        comment: Merchant category code.

      - name: merchant_country
        expr: source.merchant_country
        display_name: Merchant Country
        comment: Merchant country.

    measures:
      - name: transaction_count
        expr: COUNT(1)
        display_name: Transaction Count
        comment: Total logical payment transactions.

      - name: total_payment_value
        expr: SUM(source.amount)
        display_name: Total Payment Value
        comment: Sum of payment transaction amounts.

      - name: average_transaction_value
        expr: AVG(source.amount)
        display_name: Average Transaction Value
        comment: Average payment transaction amount.

      - name: unique_customers
        expr: COUNT(DISTINCT source.customer_id)
        display_name: Unique Customers
        comment: Number of unique customers transacting.

      - name: unique_merchants
        expr: COUNT(DISTINCT source.merchant_id)
        display_name: Unique Merchants
        comment: Number of unique merchants receiving payments.

      - name: authorized_transaction_count
        expr: SUM(CASE WHEN source.transaction_status = 'AUTHORIZED' THEN 1 ELSE 0 END)
        display_name: Authorized Transactions
        comment: Transactions in AUTHORIZED status.

      - name: declined_transaction_count
        expr: SUM(CASE WHEN source.transaction_status = 'DECLINED' THEN 1 ELSE 0 END)
        display_name: Declined Transactions
        comment: Transactions in DECLINED status.

      - name: authorization_rate
        expr: 1.0 * SUM(CASE WHEN source.transaction_status = 'AUTHORIZED' THEN 1 ELSE 0 END) / NULLIF(COUNT(1), 0)
        display_name: Authorization Rate
        comment: Authorized transaction count divided by all transactions.

      - name: decline_rate
        expr: 1.0 * SUM(CASE WHEN source.transaction_status = 'DECLINED' THEN 1 ELSE 0 END) / NULLIF(COUNT(1), 0)
        display_name: Decline Rate
        comment: Declined transaction count divided by all transactions.

      - name: card_not_present_rate
        expr: 1.0 * SUM(CASE WHEN source.card_present = false THEN 1 ELSE 0 END) / NULLIF(COUNT(1), 0)
        display_name: Card Not Present Rate
        comment: Share of transactions where the physical card was not present.
    $$
    """
)

# COMMAND ----------
# Fraud model metric view.

spark.sql(
    f"""
    CREATE OR REPLACE VIEW {FRAUD_METRIC_VIEW}
    WITH METRICS
    LANGUAGE YAML
    AS
    $$
    version: 1.1

    comment: |-
      Leakage-safe Champion fraud-model monitoring metrics for EPIP.
      Model probability and predicted_fraud are analytical signals, not
      confirmed fraud outcomes.

    source: {FRAUD_BASE_VIEW}

    fields:
      - name: event_date
        expr: source.event_date
        display_name: Payment Date
        comment: Business date of the scored payment.

      - name: channel
        expr: source.channel
        display_name: Payment Channel
        comment: Payment origination channel.

      - name: payment_method
        expr: source.payment_method
        display_name: Payment Method
        comment: Payment instrument or payment method.

      - name: transaction_country
        expr: source.transaction_country
        display_name: Transaction Country
        comment: Country associated with the payment.

      - name: merchant_id
        expr: source.merchant_id
        display_name: Merchant ID
        comment: Synthetic merchant identifier.

      - name: merchant_name
        expr: source.merchant_name
        display_name: Merchant
        comment: Synthetic merchant name.

      - name: risk_band
        expr: source.risk_band
        display_name: Model Risk Band
        comment: Analytics-only band derived from fraud probability.

      - name: predicted_fraud
        expr: source.predicted_fraud
        display_name: Predicted Fraud
        comment: Champion model binary prediction; not a confirmed fraud outcome.

      - name: is_cross_border
        expr: source.is_cross_border
        display_name: Cross Border
        comment: Point-in-time cross-border feature used by the fraud model.

      - name: is_card_not_present
        expr: source.is_card_not_present
        display_name: Card Not Present
        comment: Point-in-time card-not-present feature.

      - name: model_alias
        expr: source.model_alias
        display_name: Model Alias
        comment: Unity Catalog model alias used for scoring.

    measures:
      - name: transactions_scored
        expr: COUNT(1)
        display_name: Transactions Scored
        comment: Number of transactions with a Champion fraud probability.

      - name: predicted_fraud_count
        expr: SUM(CASE WHEN source.predicted_fraud = 1 THEN 1 ELSE 0 END)
        display_name: Predicted Fraud Count
        comment: Number of transactions predicted as fraud by the model.

      - name: predicted_fraud_rate
        expr: 1.0 * SUM(CASE WHEN source.predicted_fraud = 1 THEN 1 ELSE 0 END) / NULLIF(COUNT(1), 0)
        display_name: Predicted Fraud Rate
        comment: Share of scored transactions predicted as fraud.

      - name: average_fraud_probability
        expr: AVG(source.fraud_probability)
        display_name: Average Fraud Probability
        comment: Average Champion model fraud probability.

      - name: high_risk_transaction_count
        expr: SUM(CASE WHEN source.risk_band = 'HIGH' THEN 1 ELSE 0 END)
        display_name: High Risk Transactions
        comment: Transactions with fraud probability at least 0.80.

      - name: cross_border_high_risk_count
        expr: SUM(CASE WHEN source.risk_band = 'HIGH' AND source.is_cross_border THEN 1 ELSE 0 END)
        display_name: Cross Border High Risk
        comment: High-risk model signals on cross-border transactions.

      - name: card_not_present_high_risk_count
        expr: SUM(CASE WHEN source.risk_band = 'HIGH' AND source.is_card_not_present THEN 1 ELSE 0 END)
        display_name: Card Not Present High Risk
        comment: High-risk model signals on card-not-present transactions.
    $$
    """
)

# COMMAND ----------
# Agent quality metric view.

spark.sql(
    f"""
    CREATE OR REPLACE VIEW {AGENT_METRIC_VIEW}
    WITH METRICS
    LANGUAGE YAML
    AS
    $$
    version: 1.1

    comment: |-
      Governed quality and regression metrics for the EPIP fraud-investigation
      agent using persisted M13 golden evaluation results.

    source: {AGENT_BASE_VIEW}

    fields:
      - name: evaluation_run_id
        expr: source.evaluation_run_id
        display_name: Evaluation Run
        comment: Unique M13 evaluation run identifier.

      - name: case_id
        expr: source.case_id
        display_name: Evaluation Case
        comment: Golden evaluation case identifier.

      - name: scenario_type
        expr: source.scenario_type
        display_name: Scenario Type
        comment: Golden fraud-investigation scenario category.

      - name: generation_model
        expr: source.generation_model
        display_name: Generation Model
        comment: Model used by the fraud-investigation agent.

      - name: judge_model
        expr: source.judge_model
        display_name: Judge Model
        comment: Model used for structured M13 judging.

      - name: case_pass
        expr: source.case_pass
        display_name: Case Passed
        comment: Whether the golden evaluation case passed all required gates.

      - name: created_at
        expr: source.created_at
        display_name: Evaluated At
        comment: Evaluation result creation timestamp.

    measures:
      - name: evaluated_cases
        expr: COUNT(1)
        display_name: Evaluated Cases
        comment: Number of golden evaluation cases.

      - name: passed_cases
        expr: SUM(CASE WHEN source.case_pass THEN 1 ELSE 0 END)
        display_name: Passed Cases
        comment: Number of golden cases that passed.

      - name: case_pass_rate
        expr: 1.0 * SUM(CASE WHEN source.case_pass THEN 1 ELSE 0 END) / NULLIF(COUNT(1), 0)
        display_name: Case Pass Rate
        comment: Share of evaluated golden cases that passed.

      - name: average_overall_score
        expr: AVG(source.overall_score)
        display_name: Average Overall Score
        comment: Mean weighted M13 case score.

      - name: average_groundedness
        expr: AVG(source.groundedness_score)
        display_name: Average Groundedness
        comment: Mean groundedness judge score.

      - name: average_evidence_completeness
        expr: AVG(source.evidence_completeness_score)
        display_name: Average Evidence Completeness
        comment: Mean evidence-completeness judge score.

      - name: average_investigation_quality
        expr: AVG(source.investigation_quality_score)
        display_name: Average Investigation Quality
        comment: Mean investigation-quality judge score.

      - name: average_tool_selection
        expr: AVG(source.tool_selection_score)
        display_name: Average Tool Selection
        comment: Mean deterministic required-tool selection score.

      - name: average_tool_argument_score
        expr: AVG(source.tool_argument_score)
        display_name: Average Tool Argument Score
        comment: Mean tool-argument correctness score.

      - name: average_tool_efficiency
        expr: AVG(source.tool_efficiency_score)
        display_name: Average Tool Efficiency
        comment: Mean tool-efficiency score.

      - name: average_citation_score
        expr: AVG(source.citation_score)
        display_name: Average Citation Score
        comment: Mean valid-source-citation score.

      - name: scope_compliance_rate
        expr: AVG(source.scope_compliance_score)
        display_name: Scope Compliance Rate
        comment: Mean transaction-scope compliance score.

      - name: safety_compliance_rate
        expr: AVG(source.safety_score)
        display_name: Safety Compliance Rate
        comment: Mean autonomous-action safety score.

      - name: human_review_compliance_rate
        expr: AVG(source.human_review_score)
        display_name: Human Review Compliance
        comment: Mean human-review compliance score.

      - name: average_duration_seconds
        expr: AVG(source.duration_seconds)
        display_name: Average Agent Duration
        comment: Mean agent execution duration in seconds.
    $$
    """
)

# COMMAND ----------
# Runtime validation.

validation_queries = {
    "payment_operations_metrics": f"""
        SELECT
            MEASURE(transaction_count) AS transaction_count,
            MEASURE(total_payment_value) AS total_payment_value
        FROM {PAYMENT_METRIC_VIEW}
    """,
    "fraud_model_metrics": f"""
        SELECT
            MEASURE(transactions_scored) AS transactions_scored,
            MEASURE(average_fraud_probability) AS average_fraud_probability
        FROM {FRAUD_METRIC_VIEW}
    """,
    "agent_quality_metrics": f"""
        SELECT
            MEASURE(evaluated_cases) AS evaluated_cases,
            MEASURE(case_pass_rate) AS case_pass_rate
        FROM {AGENT_METRIC_VIEW}
    """,
}

for metric_name, query in validation_queries.items():
    row = spark.sql(query).first()

    if row is None:
        raise RuntimeError(f"M14 metric view validation returned no row: {metric_name}")

    print(metric_name, row.asDict(recursive=True))

print("Payment semantic source:", PAYMENT_BASE_VIEW)
print("Fraud-model semantic source:", FRAUD_BASE_VIEW)
print("Agent-quality semantic source:", AGENT_BASE_VIEW)

print("Payment metric view:", PAYMENT_METRIC_VIEW)
print("Fraud-model metric view:", FRAUD_METRIC_VIEW)
print("Agent-quality metric view:", AGENT_METRIC_VIEW)

print("EPIP_M14A_SEMANTIC_LAYER_READY")
