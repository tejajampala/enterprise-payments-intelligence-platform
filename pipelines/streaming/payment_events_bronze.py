"""Bronze streaming ingestion for Amazon MSK payment events."""

from pyspark import pipelines as dp
from pyspark.sql import functions as F
from pyspark.sql.types import (
    BooleanType,
    LongType,
    StringType,
    StructField,
    StructType,
)


TRANSACTION_SCHEMA = StructType(
    [
        StructField("transaction_id", StringType(), True),
        StructField("account_id", StringType(), True),
        StructField("merchant_id", StringType(), True),
        StructField("event_timestamp", StringType(), True),
        StructField("amount", StringType(), True),
        StructField("currency", StringType(), True),
        StructField("channel", StringType(), True),
        StructField("payment_method", StringType(), True),
        StructField("status", StringType(), True),
        StructField("card_present", BooleanType(), True),
        StructField("device_id", StringType(), True),
        StructField("ip_address", StringType(), True),
        StructField("country", StringType(), True),
    ]
)


PAYLOAD_SCHEMA = StructType(
    [
        StructField("event_id", StringType(), True),
        StructField("event_type", StringType(), True),
        StructField("event_timestamp", StringType(), True),
        StructField("sequence_number", LongType(), True),
        StructField("transaction", TRANSACTION_SCHEMA, True),
    ]
)


KAFKA_VALUE_SCHEMA = StructType(
    [
        StructField("simulated_arrival_at", StringType(), True),
        StructField("scenario", StringType(), True),
        StructField("payload", PAYLOAD_SCHEMA, True),
    ]
)


def _read_payment_events_from_kafka():
    """Create the raw Amazon MSK streaming DataFrame."""

    bootstrap_servers = spark.conf.get(
        "payments.msk.bootstrapServers"
    )

    topic = spark.conf.get(
        "payments.msk.topic"
    )

    service_credential = spark.conf.get(
        "payments.msk.serviceCredential"
    )

    return (
        spark.readStream
        .format("kafka")
        .option(
            "kafka.bootstrap.servers",
            bootstrap_servers,
        )
        .option(
            "subscribe",
            topic,
        )
        .option(
            "databricks.serviceCredential",
            service_credential,
        )
        .option(
            "startingOffsets",
            "earliest",
        )
        .option(
            "failOnDataLoss",
            "true",
        )
        .load()
    )


@dp.table(
    name="payment_events",
    comment=(
        "Raw Amazon MSK payment events preserving business payload, "
        "delivery metadata and Kafka operational metadata."
    ),
    table_properties={
        "quality": "bronze",
    },
)
def payment_events():
    """Ingest payment events from Amazon MSK."""

    kafka_df = _read_payment_events_from_kafka()

    raw_df = kafka_df.select(
        F.col("key")
        .cast("string")
        .alias("kafka_key"),

        F.col("value")
        .cast("string")
        .alias("raw_payload"),

        F.col("topic")
        .alias("kafka_topic"),

        F.col("partition")
        .alias("kafka_partition"),

        F.col("offset")
        .alias("kafka_offset"),

        F.col("timestamp")
        .alias("kafka_timestamp"),

        F.col("timestampType")
        .alias("kafka_timestamp_type"),
    )

    parsed_df = raw_df.withColumn(
        "parsed",
        F.from_json(
            F.col("raw_payload"),
            KAFKA_VALUE_SCHEMA,
        ),
    )

    return parsed_df.select(
        # -----------------------------------------------------------
        # Payment event
        # -----------------------------------------------------------
        F.col("parsed.payload.event_id")
        .alias("event_id"),

        F.col("parsed.payload.event_type")
        .alias("event_type"),

        F.to_timestamp(
            F.col("parsed.payload.event_timestamp")
        ).alias("event_timestamp"),

        F.col("parsed.payload.sequence_number")
        .alias("sequence_number"),

        # -----------------------------------------------------------
        # Transaction
        # -----------------------------------------------------------
        F.col(
            "parsed.payload.transaction.transaction_id"
        ).alias("transaction_id"),

        F.col(
            "parsed.payload.transaction.account_id"
        ).alias("account_id"),

        F.col(
            "parsed.payload.transaction.merchant_id"
        ).alias("merchant_id"),

        F.to_timestamp(
            F.col(
                "parsed.payload.transaction.event_timestamp"
            )
        ).alias("transaction_event_timestamp"),

        F.col(
            "parsed.payload.transaction.amount"
        )
        .cast("decimal(18,2)")
        .alias("amount"),

        F.col(
            "parsed.payload.transaction.currency"
        ).alias("currency"),

        F.col(
            "parsed.payload.transaction.channel"
        ).alias("channel"),

        F.col(
            "parsed.payload.transaction.payment_method"
        ).alias("payment_method"),

        F.col(
            "parsed.payload.transaction.status"
        ).alias("transaction_status"),

        F.col(
            "parsed.payload.transaction.card_present"
        ).alias("card_present"),

        F.col(
            "parsed.payload.transaction.device_id"
        ).alias("device_id"),

        F.col(
            "parsed.payload.transaction.ip_address"
        ).alias("ip_address"),

        F.col(
            "parsed.payload.transaction.country"
        ).alias("country"),

        # -----------------------------------------------------------
        # Synthetic delivery metadata
        # -----------------------------------------------------------
        F.col("parsed.scenario")
        .alias("delivery_scenario"),

        F.to_timestamp(
            F.col("parsed.simulated_arrival_at")
        ).alias("simulated_arrival_at"),

        # -----------------------------------------------------------
        # Kafka physical-delivery metadata
        # -----------------------------------------------------------
        F.col("kafka_key"),
        F.col("kafka_topic"),
        F.col("kafka_partition"),
        F.col("kafka_offset"),
        F.col("kafka_timestamp"),
        F.col("kafka_timestamp_type"),

        # -----------------------------------------------------------
        # Raw Bronze fidelity
        # -----------------------------------------------------------
        F.col("raw_payload"),

        F.when(
            F.col("parsed").isNull(),
            F.lit("INVALID_JSON"),
        )
        .otherwise(
            F.lit("PARSED"),
        )
        .alias("parse_status"),

        F.current_timestamp()
        .alias("ingested_at"),
    )