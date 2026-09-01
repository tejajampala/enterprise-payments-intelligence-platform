"""Silver data-quality classification, validation, and quarantine flows."""

from dq_rules import (
    PAYMENT_EVENT_RULES,
    PAYMENT_TRANSACTION_RULES,
    add_quality_columns,
)
from pyspark import pipelines as dp
from pyspark.sql import SparkSession
from pyspark.sql import functions as F


def _spark() -> SparkSession:
    """Return the active Spark session managed by Lakeflow."""

    session = SparkSession.getActiveSession()

    if session is None:
        raise RuntimeError("No active Spark session is available")

    return session


# ============================================================================
# PAYMENT EVENTS
# ============================================================================


@dp.table(
    name="payment_events_dq_classified",
    private=True,
    comment=("Private streaming table that evaluates row-level data-quality rules for standardized payment events."),
)
@dp.expect_all(PAYMENT_EVENT_RULES)
def payment_events_dq_classified():
    """Evaluate payment-event quality rules without losing source rows."""

    spark = _spark()

    standardized = spark.readStream.table("payment_events_standardized")

    return add_quality_columns(
        standardized,
        PAYMENT_EVENT_RULES,
    )


@dp.table(
    name="payment_events_validated",
    comment=(
        "Validated payment events that passed Silver row-level "
        "data-quality rules. Duplicate, late and out-of-order event "
        "handling is intentionally deferred to Milestone 6B."
    ),
    table_properties={
        "quality": "silver",
        "domain": "payments",
        "trust_level": "validated",
    },
)
def payment_events_validated():
    """Publish valid payment events for downstream trust processing."""

    spark = _spark()

    return spark.readStream.table("payment_events_dq_classified").filter(F.col("is_quarantined") == F.lit(False))


@dp.table(
    name="payment_events_quarantine",
    comment=("Payment events that failed one or more Silver row-level data-quality expectations."),
    table_properties={
        "quality": "quarantine",
        "domain": "payments",
    },
)
def payment_events_quarantine():
    """Preserve invalid payment events for investigation and reprocessing."""

    spark = _spark()

    return spark.readStream.table("payment_events_dq_classified").filter(F.col("is_quarantined") == F.lit(True))


# ============================================================================
# PAYMENT TRANSACTIONS
# ============================================================================


@dp.table(
    name="payment_transactions_dq_classified",
    private=True,
    comment=(
        "Private streaming table that evaluates row-level data-quality "
        "rules for standardized historical payment transactions."
    ),
)
@dp.expect_all(PAYMENT_TRANSACTION_RULES)
def payment_transactions_dq_classified():
    """Evaluate payment-transaction quality rules."""

    spark = _spark()

    standardized = spark.readStream.table("payment_transactions")

    return add_quality_columns(
        standardized,
        PAYMENT_TRANSACTION_RULES,
    )


@dp.table(
    name="payment_transactions_validated",
    comment=("Validated historical payment transactions that passed Silver row-level data-quality rules."),
    table_properties={
        "quality": "silver",
        "domain": "payments",
        "trust_level": "validated",
        "delta.enableRowTracking": "true",
        "delta.enableChangeDataFeed": "true",
    },
)
def payment_transactions_validated():
    """Publish valid transactions for enrichment and Gold processing."""

    spark = _spark()

    return spark.readStream.table("payment_transactions_dq_classified").filter(F.col("is_quarantined") == F.lit(False))


@dp.table(
    name="payment_transactions_quarantine",
    comment=("Historical payment transactions that failed one or more Silver row-level data-quality expectations."),
    table_properties={
        "quality": "quarantine",
        "domain": "payments",
    },
)
def payment_transactions_quarantine():
    """Preserve invalid transactions for investigation and reprocessing."""

    spark = _spark()

    return spark.readStream.table("payment_transactions_dq_classified").filter(F.col("is_quarantined") == F.lit(True))
