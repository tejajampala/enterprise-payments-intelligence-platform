# Databricks notebook source
"""Milestone 12A — Build governed fraud-investigation evidence and UC tools.

This notebook creates two read-only, investigation-safe views and two governed
Unity Catalog table functions:

- ai.agent_transaction_context
- ai.agent_fraud_evidence
- ai.get_transaction_context(transaction_id)
- ai.get_fraud_evidence(transaction_id)

The evidence layer deliberately excludes investigation outcomes and training
labels. The future M12 agent must investigate from evidence available at or
near transaction time rather than reading the known fraud outcome.
"""

# COMMAND ----------

import json
import re

from pyspark.sql import SparkSession

# COMMAND ----------
# Spark and runtime configuration.

spark_session = SparkSession.getActiveSession()

if spark_session is None:
    raise RuntimeError("No active SparkSession is available for M12 agent evidence setup")


def validate_identifier(
    value: str,
    label: str,
) -> str:
    """Validate a simple Unity Catalog identifier before interpolating it into SQL."""

    if not re.fullmatch(
        r"[A-Za-z_][A-Za-z0-9_]*",
        value,
    ):
        raise ValueError(f"Invalid {label}: {value!r}")

    return value


dbutils.widgets.text(
    "catalog_name",
    "payments_dev",
)

CATALOG = validate_identifier(
    dbutils.widgets.get("catalog_name"),
    "catalog_name",
)

AI_SCHEMA = "ai"

TRANSACTION_SOURCE = f"{CATALOG}.silver.payment_transactions_enriched"

TRANSACTION_FEATURE_TABLE = f"{CATALOG}.features.transaction_fraud_features"

CUSTOMER_FEATURE_TABLE = f"{CATALOG}.features.customer_behavior_features"

MERCHANT_FEATURE_TABLE = f"{CATALOG}.features.merchant_behavior_features"

FRAUD_PREDICTION_TABLE = f"{CATALOG}.ml.fraud_batch_predictions"

TRANSACTION_CONTEXT_VIEW = f"{CATALOG}.{AI_SCHEMA}.agent_transaction_context"

FRAUD_EVIDENCE_VIEW = f"{CATALOG}.{AI_SCHEMA}.agent_fraud_evidence"

TRANSACTION_CONTEXT_FUNCTION = f"{CATALOG}.{AI_SCHEMA}.get_transaction_context"

FRAUD_EVIDENCE_FUNCTION = f"{CATALOG}.{AI_SCHEMA}.get_fraud_evidence"

# Fields that must never appear in the agent-facing evidence views.
FORBIDDEN_AGENT_COLUMNS = {
    "analyst_notes",
    "fraud_case_closed_at",
    "fraud_outcome",
    "has_fraud_case",
    "is_confirmed_fraud",
}

# COMMAND ----------
# Validate upstream assets from earlier EPIP milestones.

required_source_tables = (
    TRANSACTION_SOURCE,
    TRANSACTION_FEATURE_TABLE,
    CUSTOMER_FEATURE_TABLE,
    MERCHANT_FEATURE_TABLE,
    FRAUD_PREDICTION_TABLE,
)

missing_source_tables = [
    table_name for table_name in required_source_tables if not spark_session.catalog.tableExists(table_name)
]

if missing_source_tables:
    raise RuntimeError(f"M12 requires completed M5/M7/M10 assets. Missing tables: {missing_source_tables}")

spark_session.sql(
    f"""
    CREATE SCHEMA IF NOT EXISTS
    {CATALOG}.{AI_SCHEMA}

    COMMENT
    'Governed AI, RAG, and fraud-investigation agent assets.'
    """
)

# COMMAND ----------
# Agent transaction context view.
#
# This exposes only investigation-time-safe transaction/account/customer/
# merchant context. Post-investigation fraud outcome fields are intentionally
# excluded. Customer names are also omitted because they are unnecessary for
# this analytical agent and data minimisation is preferable even for synthetic
# portfolio data.

spark_session.sql(
    f"""
    CREATE OR REPLACE VIEW
    {TRANSACTION_CONTEXT_VIEW}

    COMMENT
    'Investigation-safe transaction, account, customer, and merchant context
     for the fraud agent.'

    AS

    SELECT

        source.transaction_id,
        source.account_id,
        source.customer_id,
        source.merchant_id,

        source.event_timestamp,

        CAST(
            source.amount AS DOUBLE
        ) AS amount,

        source.currency,
        source.channel,
        source.payment_method,
        source.transaction_status,
        source.card_present,
        source.device_id,
        source.ip_address,
        source.transaction_country,

        source.account_type,
        source.account_currency,
        source.account_status,
        source.opened_date,

        CAST(
            source.current_balance AS DOUBLE
        ) AS current_balance,

        source.customer_country,
        source.customer_risk_rating,
        source.kyc_status,
        source.customer_status,

        source.merchant_name,
        source.merchant_category_code,
        source.merchant_city,
        source.merchant_country,
        source.merchant_risk_rating,
        source.merchant_status

    FROM
        {TRANSACTION_SOURCE} AS source
    """
)

# COMMAND ----------
# Agent fraud evidence view.
#
# Join directly to the governed feature tables rather than the training
# dataset.
#
# This keeps the agent away from is_confirmed_fraud and reuses the same
# point-in-time feature contracts that power the fraud model.

spark_session.sql(
    f"""
    CREATE OR REPLACE VIEW
    {FRAUD_EVIDENCE_VIEW}

    COMMENT
    'Leakage-safe behavioral features and Champion fraud-model signals
     for investigation.'

    AS

    SELECT

        transaction_features.transaction_id,
        transaction_features.customer_id,
        transaction_features.account_id,
        transaction_features.merchant_id,

        transaction_features.transaction_event_timestamp
            AS event_timestamp,

        CAST(
            transaction_features.amount
            AS DOUBLE
        ) AS amount,

        CAST(
            transaction_features.amount_log1p
            AS DOUBLE
        ) AS amount_log1p,

        transaction_features.hour_of_day,
        transaction_features.day_of_week,
        transaction_features.is_weekend,
        transaction_features.is_cross_border,
        transaction_features.is_card_not_present,

        transaction_features.is_pos,
        transaction_features.is_ecommerce,
        transaction_features.is_mobile,
        transaction_features.is_atm,

        transaction_features.is_debit_card,
        transaction_features.is_credit_card,
        transaction_features.is_digital_wallet,
        transaction_features.is_bank_transfer,

        COALESCE(
            customer_features.customer_txn_count_1d,
            0
        ) AS customer_txn_count_1d,

        COALESCE(
            customer_features.customer_txn_count_7d,
            0
        ) AS customer_txn_count_7d,

        COALESCE(
            customer_features.customer_txn_count_30d,
            0
        ) AS customer_txn_count_30d,

        COALESCE(
            customer_features.customer_amount_sum_1d,
            0.0
        ) AS customer_amount_sum_1d,

        COALESCE(
            customer_features.customer_amount_sum_7d,
            0.0
        ) AS customer_amount_sum_7d,

        COALESCE(
            customer_features.customer_avg_amount_30d,
            0.0
        ) AS customer_avg_amount_30d,

        COALESCE(
            customer_features.customer_decline_rate_30d,
            0.0
        ) AS customer_decline_rate_30d,

        COALESCE(
            customer_features.customer_foreign_rate_30d,
            0.0
        ) AS customer_foreign_rate_30d,

        COALESCE(
            customer_features.customer_card_not_present_rate_30d,
            0.0
        ) AS customer_card_not_present_rate_30d,

        COALESCE(
            merchant_features.merchant_txn_count_1d,
            0
        ) AS merchant_txn_count_1d,

        COALESCE(
            merchant_features.merchant_txn_count_7d,
            0
        ) AS merchant_txn_count_7d,

        COALESCE(
            merchant_features.merchant_txn_count_30d,
            0
        ) AS merchant_txn_count_30d,

        COALESCE(
            merchant_features.merchant_amount_sum_1d,
            0.0
        ) AS merchant_amount_sum_1d,

        COALESCE(
            merchant_features.merchant_amount_sum_7d,
            0.0
        ) AS merchant_amount_sum_7d,

        COALESCE(
            merchant_features.merchant_avg_amount_30d,
            0.0
        ) AS merchant_avg_amount_30d,

        COALESCE(
            merchant_features.merchant_decline_rate_30d,
            0.0
        ) AS merchant_decline_rate_30d,

        COALESCE(
            merchant_features.merchant_foreign_rate_30d,
            0.0
        ) AS merchant_foreign_rate_30d,

        COALESCE(
            merchant_features.merchant_card_not_present_rate_30d,
            0.0
        ) AS merchant_card_not_present_rate_30d,

        CAST(
            predictions.fraud_probability
            AS DOUBLE
        ) AS fraud_probability,

        CAST(
            predictions.predicted_fraud
            AS INT
        ) AS predicted_fraud,

        predictions.registered_model_name,
        predictions.model_version,
        predictions.model_alias,
        predictions.scored_at

    FROM
        {TRANSACTION_FEATURE_TABLE}
            AS transaction_features

    LEFT JOIN
        {CUSTOMER_FEATURE_TABLE}
            AS customer_features

        ON
            transaction_features.customer_id =
                customer_features.customer_id

        AND
            transaction_features.transaction_event_timestamp =
                customer_features.feature_timestamp

    LEFT JOIN
        {MERCHANT_FEATURE_TABLE}
            AS merchant_features

        ON
            transaction_features.merchant_id =
                merchant_features.merchant_id

        AND
            transaction_features.transaction_event_timestamp =
                merchant_features.feature_timestamp

    LEFT JOIN
        {FRAUD_PREDICTION_TABLE}
            AS predictions

        ON
            transaction_features.transaction_id =
                predictions.transaction_id
    """
)

# COMMAND ----------
# Runtime leakage validation.

for view_name in (
    TRANSACTION_CONTEXT_VIEW,
    FRAUD_EVIDENCE_VIEW,
):
    view_columns = {column.lower() for column in spark_session.table(view_name).columns}

    leaked_columns = FORBIDDEN_AGENT_COLUMNS.intersection(view_columns)

    if leaked_columns:
        raise RuntimeError(
            f"Agent evidence view {view_name} exposes forbidden outcome columns: {sorted(leaked_columns)}"
        )

# COMMAND ----------
# Governed read-only Unity Catalog table functions.
#
# The agent will be given these deterministic interfaces rather than a tool
# that accepts arbitrary SQL.
#
# A future production deployment can expose the same functions through
# Databricks managed MCP without changing the business contract.

spark_session.sql(
    f"""
    CREATE OR REPLACE FUNCTION
    {TRANSACTION_CONTEXT_FUNCTION}(

        p_transaction_id STRING

        COMMENT
        'Synthetic EPIP transaction identifier,
         for example txn-00000001.'
    )

    RETURNS TABLE

    LANGUAGE SQL

    READS SQL DATA

    COMMENT
    'Read-only investigation context for one
     EPIP payment transaction.'

    RETURN

        SELECT
            context.*

        FROM
            {TRANSACTION_CONTEXT_VIEW}
                AS context

        WHERE
            context.transaction_id =
                get_transaction_context.p_transaction_id

        LIMIT 1
    """
)

spark_session.sql(
    f"""
    CREATE OR REPLACE FUNCTION
    {FRAUD_EVIDENCE_FUNCTION}(

        p_transaction_id STRING

        COMMENT
        'Synthetic EPIP transaction identifier,
         for example txn-00000001.'
    )

    RETURNS TABLE

    LANGUAGE SQL

    READS SQL DATA

    COMMENT
    'Read-only leakage-safe behavioral and
     fraud-model evidence for one transaction.'

    RETURN

        SELECT
            evidence.*

        FROM
            {FRAUD_EVIDENCE_VIEW}
                AS evidence

        WHERE
            evidence.transaction_id =
                get_fraud_evidence.p_transaction_id

        LIMIT 1
    """
)

# COMMAND ----------
# Validate the functions with one real synthetic transaction.

sample_row = (
    spark_session.table(TRANSACTION_CONTEXT_VIEW).select("transaction_id").orderBy("transaction_id").limit(1).first()
)

if sample_row is None:
    raise RuntimeError(f"Agent transaction context view is empty: {TRANSACTION_CONTEXT_VIEW}")

sample_transaction_id = str(sample_row["transaction_id"])

escaped_transaction_id = sample_transaction_id.replace(
    "'",
    "''",
)

context_function_count = spark_session.sql(
    f"""
        SELECT *
        FROM {TRANSACTION_CONTEXT_FUNCTION}(
            '{escaped_transaction_id}'
        )
        """
).count()

evidence_function_count = spark_session.sql(
    f"""
        SELECT *
        FROM {FRAUD_EVIDENCE_FUNCTION}(
            '{escaped_transaction_id}'
        )
        """
).count()

if context_function_count != 1:
    raise RuntimeError(
        "Expected get_transaction_context to return "
        f"one row for {sample_transaction_id}; "
        f"received {context_function_count}"
    )

if evidence_function_count != 1:
    raise RuntimeError(
        f"Expected get_fraud_evidence to return one row for {sample_transaction_id}; received {evidence_function_count}"
    )

# COMMAND ----------
# Final setup summary.

print(
    json.dumps(
        {
            "catalog": CATALOG,
            "transaction_context_view": (TRANSACTION_CONTEXT_VIEW),
            "fraud_evidence_view": (FRAUD_EVIDENCE_VIEW),
            "transaction_context_function": (TRANSACTION_CONTEXT_FUNCTION),
            "fraud_evidence_function": (FRAUD_EVIDENCE_FUNCTION),
            "forbidden_agent_columns": sorted(FORBIDDEN_AGENT_COLUMNS),
            "sample_transaction_id": (sample_transaction_id),
            "context_function_rows": (context_function_count),
            "evidence_function_rows": (evidence_function_count),
        },
        indent=2,
    )
)
