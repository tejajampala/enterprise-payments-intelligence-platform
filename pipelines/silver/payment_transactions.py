"""Silver transformation for historical payment transactions."""

from pyspark import pipelines as dp
from pyspark.sql import SparkSession
from pyspark.sql import functions as F


def _spark() -> SparkSession:
    """Return the active Spark session managed by Lakeflow."""

    session = SparkSession.getActiveSession()

    if session is None:
        raise RuntimeError("No active Spark session is available")

    return session


@dp.table(
    name="payment_transactions",
    comment=(
        "Incrementally standardized historical payment transactions sourced "
        "from the governed append-only S3 ingestion table."
    ),
    table_properties={
        "quality": "silver",
        "domain": "payments",
        "delta.enableRowTracking": "true",
        "delta.enableChangeDataFeed": "true",
    },
)
def payment_transactions():
    """Incrementally standardize newly ingested payment transactions."""

    spark = _spark()

    transactions = spark.readStream.table("payments_dev.ingestion.payment_transactions_batch_s3")

    return transactions.select(
        F.col("transaction_id"),
        F.col("account_id"),
        F.col("merchant_id"),
        F.col("event_timestamp"),
        F.to_date(F.col("event_timestamp")).alias("event_date"),
        F.date_trunc(
            "hour",
            F.col("event_timestamp"),
        ).alias("event_hour"),
        F.col("amount"),
        F.upper(F.trim(F.col("currency"))).alias("currency"),
        F.upper(F.trim(F.col("channel"))).alias("channel"),
        F.upper(F.trim(F.col("payment_method"))).alias("payment_method"),
        F.upper(F.trim(F.col("status"))).alias("transaction_status"),
        F.col("card_present"),
        F.col("device_id"),
        F.col("ip_address"),
        F.upper(F.trim(F.col("country"))).alias("country"),
        F.col("source_file"),
        F.col("source_file_name"),
        F.col("ingested_at").alias("bronze_ingested_at"),
        F.current_timestamp().alias("silver_processed_at"),
    )
