# Databricks notebook source
"""Milestone 12C — Create the governed fraud-agent investigation history table.

The table stores successful investigation outputs and trace linkage for audit,
analytics, later agent evaluation, and portfolio demonstrations.

It intentionally does NOT store an autonomous fraud decision or hidden fraud
training label. The agent remains an investigation assistant and consequential
decisions remain with a human investigator.
"""

# COMMAND ----------

import json
import re

from pyspark.sql import SparkSession

# COMMAND ----------
# Spark and runtime configuration.

spark_session = SparkSession.getActiveSession()

if spark_session is None:
    raise RuntimeError("No active SparkSession is available for the M12 investigation store setup")


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

INVESTIGATION_TABLE = f"{CATALOG}.{AI_SCHEMA}.fraud_agent_investigations"

# COMMAND ----------
# Keep the schema creation idempotent.

spark_session.sql(
    f"""
    CREATE SCHEMA IF NOT EXISTS
    {CATALOG}.{AI_SCHEMA}

    COMMENT
    'Governed AI, RAG, and fraud-investigation agent assets.'
    """
)

# COMMAND ----------
# Investigation history.

spark_session.sql(
    f"""
    CREATE TABLE IF NOT EXISTS
    {INVESTIGATION_TABLE} (

        investigation_id STRING NOT NULL,
        transaction_id STRING NOT NULL,

        agent_version STRING NOT NULL,
        generation_provider STRING NOT NULL,
        generation_model STRING NOT NULL,

        tools_used ARRAY<STRING> NOT NULL,
        tool_call_count INT NOT NULL,

        assessment STRING,

        risk_indicators ARRAY<STRING> NOT NULL,

        counter_indicators ARRAY<STRING> NOT NULL,

        model_signal STRING,

        evidence_reviewed ARRAY<STRING> NOT NULL,

        knowledge_sources ARRAY<STRING> NOT NULL,

        limitations STRING,

        recommended_next_steps ARRAY<STRING> NOT NULL,

        final_response STRING NOT NULL,

        tool_execution_json STRING NOT NULL,

        trace_id STRING,

        duration_seconds DOUBLE NOT NULL,

        created_at TIMESTAMP NOT NULL,

        CONSTRAINT fraud_agent_investigations_pk
            PRIMARY KEY (investigation_id)
    )
    USING DELTA

    COMMENT
    'Successful human-review-oriented fraud-agent investigations
     with MLflow trace linkage.'

    TBLPROPERTIES (
        'delta.enableChangeDataFeed' = 'true',
        'delta.enableRowTracking' = 'true'
    )
    """
)

# COMMAND ----------
# Validate prohibited fields are absent.

FORBIDDEN_COLUMNS = {
    "block_card",
    "decline_transaction",
    "fraud_decision",
    "fraud_outcome",
    "freeze_account",
    "is_confirmed_fraud",
}

actual_columns = {column.lower() for column in spark_session.table(INVESTIGATION_TABLE).columns}

leaked_columns = FORBIDDEN_COLUMNS.intersection(actual_columns)

if leaked_columns:
    raise RuntimeError(f"Investigation history table exposes prohibited columns: {sorted(leaked_columns)}")

properties = {
    row["key"]: row["value"]
    for row in spark_session.sql(
        f"""
        SHOW TBLPROPERTIES
        {INVESTIGATION_TABLE}
        """
    ).collect()
}

if properties.get("delta.enableChangeDataFeed") != "true":
    raise RuntimeError("fraud_agent_investigations must have Delta Change Data Feed enabled")

if properties.get("delta.enableRowTracking") != "true":
    raise RuntimeError("fraud_agent_investigations must have Delta Row Tracking enabled")

# COMMAND ----------
# Final setup summary.

print(
    json.dumps(
        {
            "investigation_table": INVESTIGATION_TABLE,
            "columns": sorted(actual_columns),
            "forbidden_columns": sorted(FORBIDDEN_COLUMNS),
            "change_data_feed": properties.get("delta.enableChangeDataFeed"),
            "row_tracking": properties.get("delta.enableRowTracking"),
        },
        indent=2,
    )
)
