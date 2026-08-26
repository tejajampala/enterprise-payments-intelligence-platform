"""Silver transformation for streaming payment events."""

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
    name="payment_events_standardized",
    comment=(
        "Standardized payment-event stream derived incrementally from the "
        "raw Bronze Amazon MSK event table."
    ),
    table_properties={
        "quality": "silver",
    },
)
def payment_events_standardized():
    """Standardize Bronze payment events without deduplicating them."""

    spark = _spark()

    bronze = spark.readStream.table("payments_dev.bronze.payment_events")

    return bronze.select(
        # -----------------------------------------------------------
        # Business identifiers
        # -----------------------------------------------------------
        F.col("event_id"),
        F.col("transaction_id"),
        F.col("account_id"),
        F.col("merchant_id"),
        # -----------------------------------------------------------
        # Event lifecycle
        # -----------------------------------------------------------
        F.upper(F.trim(F.col("event_type"))).alias("event_type"),
        F.col("sequence_number"),
        F.col("event_timestamp"),
        F.to_date(F.col("event_timestamp")).alias("event_date"),
        F.date_trunc(
            "hour",
            F.col("event_timestamp"),
        ).alias("event_hour"),
        # -----------------------------------------------------------
        # Transaction
        # -----------------------------------------------------------
        F.col("transaction_event_timestamp"),
        F.col("amount"),
        F.upper(F.trim(F.col("currency"))).alias("currency"),
        F.upper(F.trim(F.col("channel"))).alias("channel"),
        F.upper(F.trim(F.col("payment_method"))).alias("payment_method"),
        F.upper(F.trim(F.col("transaction_status"))).alias("transaction_status"),
        F.col("card_present"),
        F.col("device_id"),
        F.col("ip_address"),
        F.upper(F.trim(F.col("country"))).alias("country"),
        # -----------------------------------------------------------
        # Delivery semantics
        # -----------------------------------------------------------
        F.upper(F.trim(F.col("delivery_scenario"))).alias("delivery_scenario"),
        F.col("simulated_arrival_at"),
        (F.unix_timestamp("simulated_arrival_at") - F.unix_timestamp("event_timestamp")).alias(
            "simulated_delivery_delay_seconds"
        ),
        # -----------------------------------------------------------
        # Kafka physical lineage
        # -----------------------------------------------------------
        F.col("kafka_key"),
        F.col("kafka_topic"),
        F.col("kafka_partition"),
        F.col("kafka_offset"),
        F.col("kafka_timestamp"),
        F.col("kafka_timestamp_type"),
        (F.unix_timestamp("ingested_at") - F.unix_timestamp("kafka_timestamp")).alias(
            "ingestion_lag_seconds"
        ),
        # -----------------------------------------------------------
        # Bronze traceability
        # -----------------------------------------------------------
        F.col("raw_payload"),
        F.col("parse_status"),
        F.col("ingested_at").alias("bronze_ingested_at"),
        F.current_timestamp().alias("silver_processed_at"),
    )
