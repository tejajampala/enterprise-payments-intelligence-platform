"""Silver current-state fraud-case reference dimension.

Customer, account, and merchant current-state datasets are maintained through
Lakeflow AUTO CDC in master_data_cdc.py.

Fraud-case CDC is intentionally deferred because the current synthetic source
contains a snapshot rather than a dedicated fraud-case CDC feed.
"""

from dq_rules import FRAUD_CASE_RULES
from pyspark import pipelines as dp
from pyspark.sql import SparkSession
from pyspark.sql import functions as F


def _spark() -> SparkSession:
    """Return the active Spark session managed by Lakeflow."""

    session = SparkSession.getActiveSession()

    if session is None:
        raise RuntimeError("No active Spark session is available")

    return session


@dp.materialized_view(
    name="fraud_cases_current",
    comment=("Current fraud-case snapshot used to enrich payment transactions."),
    table_properties={
        "quality": "silver",
        "domain": "fraud",
        "delta.enableRowTracking": "true",
        "delta.enableChangeDataFeed": "true",
    },
)
@dp.expect_all(FRAUD_CASE_RULES)
def fraud_cases_current():
    """Create the current fraud-case reference dataset."""

    spark = _spark()

    fraud_cases = spark.read.table("payments_dev.ingestion.fraud_cases_snapshot")

    return fraud_cases.select(
        F.col("case_id"),
        F.col("transaction_id"),
        F.col("opened_at"),
        F.upper(F.trim(F.col("status"))).alias("fraud_case_status"),
        F.trim(F.col("suspected_reason")).alias("suspected_reason"),
        F.upper(F.trim(F.col("outcome"))).alias("fraud_outcome"),
        F.trim(F.col("analyst_notes")).alias("analyst_notes"),
        F.col("closed_at"),
        F.col("source_file"),
        F.col("source_file_name"),
        F.col("ingested_at").alias("source_ingested_at"),
    )
