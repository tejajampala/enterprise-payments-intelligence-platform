"""Silver current-state reference dimensions.

These datasets standardize the PostgreSQL-style source snapshots.

They intentionally represent current snapshot state only.
CDC processing and SCD Type 2 history are implemented in Milestone 6.
"""

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
    name="customers_current",
    comment=(
        "Current standardized customer snapshot used for Silver enrichment. "
        "Historical SCD Type 2 processing is intentionally deferred."
    ),
    table_properties={
        "quality": "silver",
        "domain": "customer",
    },
)
def customers_current():
    """Create the current customer reference dataset."""

    spark = _spark()

    customers = spark.read.table("payments_dev.ingestion.customers_snapshot")

    return customers.filter(
        ~F.coalesce(
            F.col("is_deleted"),
            F.lit(False),
        )
    ).select(
        F.col("customer_id"),
        F.trim(F.col("first_name")).alias("first_name"),
        F.trim(F.col("last_name")).alias("last_name"),
        F.col("date_of_birth"),
        F.lower(F.trim(F.col("email"))).alias("email"),
        F.trim(F.col("phone")).alias("phone"),
        F.trim(F.col("address_line_1")).alias("address_line_1"),
        F.trim(F.col("city")).alias("city"),
        F.upper(F.trim(F.col("state"))).alias("state"),
        F.trim(F.col("postcode")).alias("postcode"),
        F.upper(F.trim(F.col("country"))).alias("country"),
        F.upper(F.trim(F.col("risk_rating"))).alias("risk_rating"),
        F.upper(F.trim(F.col("kyc_status"))).alias("kyc_status"),
        F.upper(F.trim(F.col("status"))).alias("customer_status"),
        F.col("record_version"),
        F.col("source_updated_at"),
        F.col("is_deleted"),
        F.col("source_file"),
        F.col("source_file_name"),
        F.col("ingested_at").alias("source_ingested_at"),
    )


@dp.materialized_view(
    name="accounts_current",
    comment=(
        "Current standardized account snapshot used for Silver enrichment. "
        "Historical SCD Type 2 processing is intentionally deferred."
    ),
    table_properties={
        "quality": "silver",
        "domain": "account",
    },
)
def accounts_current():
    """Create the current account reference dataset."""

    spark = _spark()

    accounts = spark.read.table("payments_dev.ingestion.accounts_snapshot")

    return accounts.filter(
        ~F.coalesce(
            F.col("is_deleted"),
            F.lit(False),
        )
    ).select(
        F.col("account_id"),
        F.col("customer_id"),
        F.upper(F.trim(F.col("account_type"))).alias("account_type"),
        F.upper(F.trim(F.col("currency"))).alias("account_currency"),
        F.upper(F.trim(F.col("status"))).alias("account_status"),
        F.col("opened_date"),
        F.col("current_balance"),
        F.col("record_version"),
        F.col("source_updated_at"),
        F.col("is_deleted"),
        F.col("source_file"),
        F.col("source_file_name"),
        F.col("ingested_at").alias("source_ingested_at"),
    )


@dp.materialized_view(
    name="merchants_current",
    comment=(
        "Current standardized merchant snapshot used for Silver enrichment. "
        "Historical CDC processing is intentionally deferred."
    ),
    table_properties={
        "quality": "silver",
        "domain": "merchant",
    },
)
def merchants_current():
    """Create the current merchant reference dataset."""

    spark = _spark()

    merchants = spark.read.table("payments_dev.ingestion.merchants_snapshot")

    return merchants.filter(
        ~F.coalesce(
            F.col("is_deleted"),
            F.lit(False),
        )
    ).select(
        F.col("merchant_id"),
        F.trim(F.col("merchant_name")).alias("merchant_name"),
        F.trim(F.col("merchant_category_code")).alias("merchant_category_code"),
        F.trim(F.col("city")).alias("merchant_city"),
        F.upper(F.trim(F.col("country"))).alias("merchant_country"),
        F.upper(F.trim(F.col("risk_rating"))).alias("merchant_risk_rating"),
        F.upper(F.trim(F.col("status"))).alias("merchant_status"),
        F.col("record_version"),
        F.col("source_updated_at"),
        F.col("is_deleted"),
        F.col("source_file"),
        F.col("source_file_name"),
        F.col("ingested_at").alias("source_ingested_at"),
    )


@dp.materialized_view(
    name="fraud_cases_current",
    comment=("Current fraud-case snapshot used to enrich payment transactions."),
    table_properties={
        "quality": "silver",
        "domain": "fraud",
    },
)
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
