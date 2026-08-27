"""Gold business metrics for the Enterprise Payments Intelligence Platform."""

from pyspark import pipelines as dp
from pyspark.sql import SparkSession
from pyspark.sql import functions as F


def _spark() -> SparkSession:
    """Return the active Spark session managed by Lakeflow."""

    session = SparkSession.getActiveSession()

    if session is None:
        raise RuntimeError("No active Spark session is available")

    return session


def _enriched_transactions():
    """Read the trusted Silver payment transaction dataset."""

    return _spark().read.table("payments_dev.silver.payment_transactions_enriched")


@dp.materialized_view(
    name="daily_payment_metrics",
    comment=(
        "Daily payment KPIs by transaction date and currency for "
        "business reporting and executive analytics."
    ),
    table_properties={
        "quality": "gold",
        "domain": "payments",
        "grain": "event_date_currency",
    },
)
def daily_payment_metrics():
    """Aggregate daily enterprise payment KPIs."""

    transactions = _enriched_transactions()

    return transactions.groupBy(
        "event_date",
        "currency",
    ).agg(
        F.count("*").alias("transaction_count"),
        F.round(
            F.sum("amount"),
            2,
        ).alias("total_payment_amount"),
        F.round(
            F.avg("amount"),
            2,
        ).alias("average_payment_amount"),
        F.min("amount").alias("minimum_payment_amount"),
        F.max("amount").alias("maximum_payment_amount"),
        F.sum(
            F.when(
                F.col("transaction_status") == "AUTHORIZED",
                1,
            ).otherwise(0)
        ).alias("authorized_transactions"),
        F.sum(
            F.when(
                F.col("transaction_status") == "DECLINED",
                1,
            ).otherwise(0)
        ).alias("declined_transactions"),
        F.sum(
            F.when(
                F.col("transaction_status") == "SETTLED",
                1,
            ).otherwise(0)
        ).alias("settled_transactions"),
        F.sum(
            F.when(
                F.col("transaction_status") == "REVERSED",
                1,
            ).otherwise(0)
        ).alias("reversed_transactions"),
        F.sum(
            F.when(
                F.col("transaction_status") == "REFUNDED",
                1,
            ).otherwise(0)
        ).alias("refunded_transactions"),
        F.sum(
            F.when(
                F.col("has_fraud_case"),
                1,
            ).otherwise(0)
        ).alias("transactions_with_fraud_case"),
        F.sum(
            F.when(
                F.col("fraud_outcome") == "CONFIRMED_FRAUD",
                1,
            ).otherwise(0)
        ).alias("confirmed_fraud_transactions"),
        F.sum(
            F.when(
                F.col("customer_risk_rating") == "HIGH",
                1,
            ).otherwise(0)
        ).alias("high_risk_customer_transactions"),
        F.sum(
            F.when(
                F.col("merchant_risk_rating") == "HIGH",
                1,
            ).otherwise(0)
        ).alias("high_risk_merchant_transactions"),
        F.max("silver_processed_at").alias("latest_silver_processed_at"),
    )


@dp.materialized_view(
    name="merchant_payment_metrics",
    comment=(
        "Merchant-level payment performance and fraud metrics for "
        "merchant monitoring and risk analytics."
    ),
    table_properties={
        "quality": "gold",
        "domain": "merchant",
        "grain": "merchant_currency",
    },
)
def merchant_payment_metrics():
    """Aggregate payment and fraud metrics by merchant."""

    transactions = _enriched_transactions()

    return transactions.groupBy(
        "merchant_id",
        "merchant_name",
        "merchant_category_code",
        "merchant_risk_rating",
        "merchant_status",
        "merchant_country",
        "currency",
    ).agg(
        F.count("*").alias("transaction_count"),
        F.countDistinct("customer_id").alias("distinct_customers"),
        F.round(
            F.sum("amount"),
            2,
        ).alias("total_payment_amount"),
        F.round(
            F.avg("amount"),
            2,
        ).alias("average_payment_amount"),
        F.max("amount").alias("maximum_payment_amount"),
        F.sum(
            F.when(
                F.col("transaction_status") == "DECLINED",
                1,
            ).otherwise(0)
        ).alias("declined_transactions"),
        F.sum(
            F.when(
                F.col("has_fraud_case"),
                1,
            ).otherwise(0)
        ).alias("transactions_with_fraud_case"),
        F.sum(
            F.when(
                F.col("fraud_outcome") == "CONFIRMED_FRAUD",
                1,
            ).otherwise(0)
        ).alias("confirmed_fraud_transactions"),
        F.round(
            F.sum(
                F.when(
                    F.col("fraud_outcome") == "CONFIRMED_FRAUD",
                    F.col("amount"),
                ).otherwise(F.lit(0))
            ),
            2,
        ).alias("confirmed_fraud_amount"),
        F.max("silver_processed_at").alias("latest_silver_processed_at"),
    )


@dp.materialized_view(
    name="channel_payment_metrics",
    comment=(
        "Daily payment KPIs by channel, payment method and currency "
        "for channel performance analytics."
    ),
    table_properties={
        "quality": "gold",
        "domain": "payments",
        "grain": "event_date_channel_payment_method_currency",
    },
)
def channel_payment_metrics():
    """Aggregate payment KPIs by channel and payment method."""

    transactions = _enriched_transactions()

    return transactions.groupBy(
        "event_date",
        "channel",
        "payment_method",
        "currency",
    ).agg(
        F.count("*").alias("transaction_count"),
        F.round(
            F.sum("amount"),
            2,
        ).alias("total_payment_amount"),
        F.round(
            F.avg("amount"),
            2,
        ).alias("average_payment_amount"),
        F.sum(
            F.when(
                F.col("card_present"),
                1,
            ).otherwise(0)
        ).alias("card_present_transactions"),
        F.sum(
            F.when(
                ~F.coalesce(
                    F.col("card_present"),
                    F.lit(False),
                ),
                1,
            ).otherwise(0)
        ).alias("card_not_present_transactions"),
        F.sum(
            F.when(
                F.col("transaction_status") == "DECLINED",
                1,
            ).otherwise(0)
        ).alias("declined_transactions"),
        F.sum(
            F.when(
                F.col("has_fraud_case"),
                1,
            ).otherwise(0)
        ).alias("transactions_with_fraud_case"),
        F.sum(
            F.when(
                F.col("fraud_outcome") == "CONFIRMED_FRAUD",
                1,
            ).otherwise(0)
        ).alias("confirmed_fraud_transactions"),
        F.max("silver_processed_at").alias("latest_silver_processed_at"),
    )


@dp.materialized_view(
    name="fraud_operations_metrics",
    comment=("Daily fraud investigation and confirmed-fraud KPIs for fraud operations monitoring."),
    table_properties={
        "quality": "gold",
        "domain": "fraud",
        "grain": "event_date_currency",
    },
)
def fraud_operations_metrics():
    """Aggregate fraud investigation metrics by day and currency."""

    transactions = _enriched_transactions()

    return transactions.groupBy(
        "event_date",
        "currency",
    ).agg(
        F.count("*").alias("transaction_count"),
        F.sum(
            F.when(
                F.col("has_fraud_case"),
                1,
            ).otherwise(0)
        ).alias("fraud_case_transactions"),
        F.sum(
            F.when(
                F.col("fraud_case_status") == "OPEN",
                1,
            ).otherwise(0)
        ).alias("open_fraud_cases"),
        F.sum(
            F.when(
                F.col("fraud_case_status") == "INVESTIGATING",
                1,
            ).otherwise(0)
        ).alias("investigating_fraud_cases"),
        F.sum(
            F.when(
                F.col("fraud_case_status") == "CLOSED",
                1,
            ).otherwise(0)
        ).alias("closed_fraud_cases"),
        F.sum(
            F.when(
                F.col("fraud_outcome") == "CONFIRMED_FRAUD",
                1,
            ).otherwise(0)
        ).alias("confirmed_fraud_transactions"),
        F.sum(
            F.when(
                F.col("fraud_outcome") == "LEGITIMATE",
                1,
            ).otherwise(0)
        ).alias("legitimate_transactions"),
        F.sum(
            F.when(
                F.col("fraud_outcome") == "UNDETERMINED",
                1,
            ).otherwise(0)
        ).alias("undetermined_transactions"),
        F.round(
            F.sum(
                F.when(
                    F.col("has_fraud_case"),
                    F.col("amount"),
                ).otherwise(F.lit(0))
            ),
            2,
        ).alias("payment_amount_under_investigation"),
        F.round(
            F.sum(
                F.when(
                    F.col("fraud_outcome") == "CONFIRMED_FRAUD",
                    F.col("amount"),
                ).otherwise(F.lit(0))
            ),
            2,
        ).alias("confirmed_fraud_amount"),
        F.max("silver_processed_at").alias("latest_silver_processed_at"),
    )
