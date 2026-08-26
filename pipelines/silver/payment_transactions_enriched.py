"""Silver enriched payment transaction dataset."""

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
    name="payment_transactions_enriched",
    comment=(
        "Business-enriched payment transactions joined to current account, "
        "customer, merchant and fraud-case reference data."
    ),
    table_properties={
        "quality": "silver",
        "domain": "payments",
    },
)
def payment_transactions_enriched():
    """Enrich standardized payment transactions with reference dimensions."""

    spark = _spark()

    transactions = spark.read.table("payment_transactions").alias("t")

    accounts = spark.read.table("accounts_current").alias("a")

    customers = spark.read.table("customers_current").alias("c")

    merchants = spark.read.table("merchants_current").alias("m")

    fraud_cases = spark.read.table("fraud_cases_current").alias("f")

    enriched = (
        transactions.join(
            accounts,
            F.col("t.account_id") == F.col("a.account_id"),
            "left",
        )
        .join(
            customers,
            F.col("a.customer_id") == F.col("c.customer_id"),
            "left",
        )
        .join(
            merchants,
            F.col("t.merchant_id") == F.col("m.merchant_id"),
            "left",
        )
        .join(
            fraud_cases,
            F.col("t.transaction_id") == F.col("f.transaction_id"),
            "left",
        )
    )

    return enriched.select(
        # -----------------------------------------------------------
        # Transaction identity
        # -----------------------------------------------------------
        F.col("t.transaction_id"),
        F.col("t.account_id"),
        F.col("t.merchant_id"),
        F.col("a.customer_id").alias("customer_id"),
        # -----------------------------------------------------------
        # Transaction measures and timestamps
        # -----------------------------------------------------------
        F.col("t.event_timestamp"),
        F.col("t.event_date"),
        F.col("t.event_hour"),
        F.col("t.amount"),
        F.col("t.currency"),
        F.col("t.channel"),
        F.col("t.payment_method"),
        F.col("t.transaction_status"),
        F.col("t.card_present"),
        F.col("t.device_id"),
        F.col("t.ip_address"),
        F.col("t.country").alias("transaction_country"),
        # -----------------------------------------------------------
        # Account enrichment
        # -----------------------------------------------------------
        F.col("a.account_type"),
        F.col("a.account_currency"),
        F.col("a.account_status"),
        F.col("a.opened_date"),
        F.col("a.current_balance"),
        # -----------------------------------------------------------
        # Customer enrichment
        # -----------------------------------------------------------
        F.col("c.first_name"),
        F.col("c.last_name"),
        F.col("c.country").alias("customer_country"),
        F.col("c.risk_rating").alias("customer_risk_rating"),
        F.col("c.kyc_status"),
        F.col("c.customer_status"),
        # -----------------------------------------------------------
        # Merchant enrichment
        # -----------------------------------------------------------
        F.col("m.merchant_name"),
        F.col("m.merchant_category_code"),
        F.col("m.merchant_city"),
        F.col("m.merchant_country"),
        F.col("m.merchant_risk_rating"),
        F.col("m.merchant_status"),
        # -----------------------------------------------------------
        # Fraud-case enrichment
        # -----------------------------------------------------------
        F.col("f.case_id").alias("fraud_case_id"),
        F.col("f.opened_at").alias("fraud_case_opened_at"),
        F.col("f.fraud_case_status"),
        F.col("f.suspected_reason"),
        F.col("f.fraud_outcome"),
        F.col("f.closed_at").alias("fraud_case_closed_at"),
        F.col("f.case_id").isNotNull().alias("has_fraud_case"),
        # -----------------------------------------------------------
        # Dimension reconciliation flags
        # -----------------------------------------------------------
        F.col("a.account_id").isNotNull().alias("account_dimension_match"),
        F.col("c.customer_id").isNotNull().alias("customer_dimension_match"),
        F.col("m.merchant_id").isNotNull().alias("merchant_dimension_match"),
        # -----------------------------------------------------------
        # Transaction lineage
        # -----------------------------------------------------------
        F.col("t.source_file"),
        F.col("t.source_file_name"),
        F.col("t.bronze_ingested_at"),
        F.col("t.silver_processed_at"),
    )
