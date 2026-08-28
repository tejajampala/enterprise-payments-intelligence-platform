"""Trusted payment-event processing.

Milestone 6B establishes event-level trust after the row-level data-quality
validation implemented in Milestone 6A.

Responsibilities:
- event-time watermarking
- event-id deduplication
- late-arrival classification
- duplicate-delivery auditing
- out-of-order sequence auditing

Late and out-of-order events remain valid business events when accepted by
the streaming watermark. They are retained in the trusted stream and are
also surfaced through the exception dataset.
"""

from pyspark import pipelines as dp
from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F

DEFAULT_EVENT_WATERMARK = "6 hours"
DEFAULT_LATE_THRESHOLD_SECONDS = 7200


def _spark() -> SparkSession:
    """Return the active Spark session managed by Lakeflow."""

    session = SparkSession.getActiveSession()

    if session is None:
        raise RuntimeError("No active Spark session is available")

    return session


def _event_watermark(
    spark: SparkSession,
) -> str:
    """Return the configured event-time watermark."""

    return spark.conf.get(
        "payments.streaming.eventWatermark",
        DEFAULT_EVENT_WATERMARK,
    )


def _late_threshold_seconds(
    spark: SparkSession,
) -> int:
    """Return the configured business late-arrival threshold."""

    return int(
        spark.conf.get(
            "payments.streaming.lateThresholdSeconds",
            str(DEFAULT_LATE_THRESHOLD_SECONDS),
        )
    )


# ============================================================================
# TRUSTED PAYMENT EVENTS
# ============================================================================


@dp.table(
    name="payment_events_trusted",
    comment=(
        "Trusted payment-event stream after row-level validation, "
        "event-time watermarking and event-id deduplication. "
        "Accepted late events remain available with explicit timing "
        "classification."
    ),
    table_properties={
        "quality": "silver",
        "domain": "payments",
        "trust_level": "trusted",
        "delta.enableRowTracking": "true",
        "delta.enableChangeDataFeed": "true",
    },
)
def payment_events_trusted():
    """Create the trusted deduplicated payment-event stream."""

    spark = _spark()

    watermark_delay = _event_watermark(spark)

    late_threshold_seconds = _late_threshold_seconds(spark)

    validated = spark.readStream.option(
        "withEventTimeOrder",
        "true",
    ).table("payment_events_validated")

    deduplicated = validated.withWatermark(
        "event_timestamp",
        watermark_delay,
    ).dropDuplicatesWithinWatermark(["event_id"])

    return (
        deduplicated.withColumn(
            "is_late_arrival",
            F.coalesce(
                F.col("simulated_delivery_delay_seconds") > F.lit(late_threshold_seconds),
                F.lit(False),
            ),
        )
        .withColumn(
            "event_arrival_classification",
            F.when(
                F.col("is_late_arrival"),
                F.lit("LATE_ACCEPTED"),
            ).otherwise(F.lit("ON_TIME")),
        )
        .withColumn(
            "event_watermark_policy",
            F.lit(watermark_delay),
        )
        .withColumn(
            "late_threshold_seconds",
            F.lit(late_threshold_seconds),
        )
        .withColumn(
            "trusted_at",
            F.current_timestamp(),
        )
    )


# ============================================================================
# PAYMENT EVENT EXCEPTION AUDIT
# ============================================================================


@dp.materialized_view(
    name="payment_event_exceptions",
    comment=(
        "Auditable payment-event delivery anomalies including duplicate "
        "physical deliveries, accepted late arrivals and out-of-order "
        "transaction lifecycle deliveries."
    ),
    table_properties={
        "quality": "silver",
        "domain": "payments",
        "trust_level": "exception_audit",
        "delta.enableRowTracking": "true",
        "delta.enableChangeDataFeed": "true",
    },
)
def payment_event_exceptions():
    """Create a current audit view of event-delivery anomalies."""

    spark = _spark()

    late_threshold_seconds = _late_threshold_seconds(spark)

    physical_events = spark.read.table("payment_events_validated")

    # ========================================================================
    # 1. Physical duplicate summary
    #
    # This deliberately counts every Kafka physical delivery.
    # ========================================================================

    duplicate_summary = physical_events.groupBy("event_id").agg(
        F.count("*").alias("physical_delivery_count"),
        F.sort_array(F.collect_set("delivery_scenario")).alias("observed_delivery_scenarios"),
        F.sort_array(F.collect_set("kafka_offset")).alias("observed_kafka_offsets"),
        F.min("kafka_timestamp").alias("first_kafka_timestamp"),
        F.max("kafka_timestamp").alias("latest_kafka_timestamp"),
    )

    # ========================================================================
    # 2. Build semantic delivery occurrences.
    #
    # During development the same synthetic input has been published multiple
    # times. Kafka therefore contains repeated copies of the exact same
    # synthetic delivery occurrence.
    #
    # We remove those exact replay copies for anomaly analysis but DO NOT
    # collapse all rows to one event_id.
    #
    # For example:
    #
    # event-1 NORMAL    +5 seconds
    # event-1 DUPLICATE +15 seconds
    #
    # remain two distinct delivery occurrences.
    # ========================================================================

    delivery_occurrences = physical_events.dropDuplicates(
        [
            "event_id",
            "delivery_scenario",
            "simulated_arrival_at",
        ]
    ).withColumn(
        "delivery_order_timestamp",
        F.coalesce(
            F.col("simulated_arrival_at"),
            F.col("kafka_timestamp"),
            F.col("bronze_ingested_at"),
        ),
    )

    # ========================================================================
    # 3. Detect out-of-order transaction lifecycle delivery.
    #
    # For each transaction, examine delivery occurrence order.
    #
    # Example:
    #
    # physical arrival:
    #
    # sequence 2
    # sequence 1
    #
    # sequence 1 is out of order because a higher sequence was already seen.
    # ========================================================================

    sequence_history_window = (
        Window.partitionBy("transaction_id")
        .orderBy(
            F.col("delivery_order_timestamp"),
            F.col("sequence_number"),
            F.col("event_id"),
        )
        .rowsBetween(
            Window.unboundedPreceding,
            -1,
        )
    )

    sequenced_occurrences = delivery_occurrences.withColumn(
        "previous_max_sequence_number",
        F.max("sequence_number").over(sequence_history_window),
    ).withColumn(
        "is_out_of_order",
        F.coalesce(
            (
                F.col("previous_max_sequence_number").isNotNull()
                & (F.col("sequence_number") < F.col("previous_max_sequence_number"))
            ),
            F.lit(False),
        ),
    )

    # ========================================================================
    # 4. Join physical duplicate information back to each semantic delivery.
    # ========================================================================

    classified = (
        sequenced_occurrences.join(
            duplicate_summary,
            on="event_id",
            how="left",
        )
        .withColumn(
            "is_duplicate_event",
            F.col("physical_delivery_count") > F.lit(1),
        )
        .withColumn(
            "is_late_arrival",
            F.coalesce(
                F.col("simulated_delivery_delay_seconds") > F.lit(late_threshold_seconds),
                F.lit(False),
            ),
        )
    )

    # ========================================================================
    # 5. Build multi-valued exception classification.
    #
    # One delivery can legitimately have multiple classifications.
    #
    # Example:
    #
    # ["DUPLICATE", "LATE"]
    # ========================================================================

    exception_types = F.filter(
        F.array(
            F.when(
                F.col("is_duplicate_event"),
                F.lit("DUPLICATE"),
            ),
            F.when(
                F.col("is_late_arrival"),
                F.lit("LATE"),
            ),
            F.when(
                F.col("is_out_of_order"),
                F.lit("OUT_OF_ORDER"),
            ),
        ),
        lambda value: value.isNotNull(),
    )

    return (
        classified.withColumn(
            "exception_types",
            exception_types,
        )
        .filter(F.size(F.col("exception_types")) > 0)
        .select(
            F.col("event_id"),
            F.col("transaction_id"),
            F.col("account_id"),
            F.col("merchant_id"),
            F.col("event_type"),
            F.col("sequence_number"),
            F.col("event_timestamp"),
            F.col("delivery_order_timestamp"),
            F.col("amount"),
            F.col("currency"),
            F.col("transaction_status"),
            F.col("delivery_scenario"),
            F.col("simulated_arrival_at"),
            F.col("simulated_delivery_delay_seconds"),
            F.col("physical_delivery_count"),
            F.col("observed_delivery_scenarios"),
            F.col("observed_kafka_offsets"),
            F.col("first_kafka_timestamp"),
            F.col("latest_kafka_timestamp"),
            F.col("is_duplicate_event"),
            F.col("is_late_arrival"),
            F.col("is_out_of_order"),
            F.col("previous_max_sequence_number"),
            F.col("exception_types"),
            F.current_timestamp().alias("exception_evaluated_at"),
        )
    )
