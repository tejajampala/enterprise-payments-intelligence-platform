# Databricks notebook source

"""Milestone 7 fraud feature engineering.

Creates Unity Catalog governed feature tables for:

- immutable transaction features
- point-in-time customer behaviour features
- point-in-time merchant behaviour features

It then uses FeatureEngineeringClient to create a point-in-time-correct
fraud training dataset for Milestone 8.

Fraud outcomes are used only to construct the training label and are never
included as model features.
"""

# COMMAND ----------

from databricks.feature_engineering import (
    FeatureEngineeringClient,
    FeatureLookup,
)
from pyspark.sql import DataFrame, SparkSession, Window
from pyspark.sql import functions as F

spark_session = SparkSession.getActiveSession()

if spark_session is None:
    raise RuntimeError("No active SparkSession is available for the feature-engineering job")

dbutils.widgets.text(
    "catalog_name",
    "payments_dev",
)

CATALOG = dbutils.widgets.get("catalog_name")

FEATURE_SCHEMA = "features"

TRANSACTION_FEATURE_TABLE = f"{CATALOG}.{FEATURE_SCHEMA}.transaction_fraud_features"

CUSTOMER_FEATURE_TABLE = f"{CATALOG}.{FEATURE_SCHEMA}.customer_behavior_features"

MERCHANT_FEATURE_TABLE = f"{CATALOG}.{FEATURE_SCHEMA}.merchant_behavior_features"

TRAINING_DATASET_TABLE = f"{CATALOG}.{FEATURE_SCHEMA}.fraud_training_dataset"


SECONDS_PER_DAY = 24 * 60 * 60


# COMMAND ----------
# Create the feature schema.
# The bundle also manages this schema, but CREATE IF NOT EXISTS makes the
# notebook independently reproducible.

spark_session.sql(
    f"""
    CREATE SCHEMA IF NOT EXISTS
    {CATALOG}.{FEATURE_SCHEMA}
    """
)


# COMMAND ----------
# ----------------------------------------------------------------------------
# Feature table DDL
#
# Any Unity Catalog Delta table with a PRIMARY KEY is automatically recognized
# as a Feature Store feature table.
# ----------------------------------------------------------------------------

spark_session.sql(
    f"""
    CREATE TABLE IF NOT EXISTS {TRANSACTION_FEATURE_TABLE} (

        transaction_id STRING NOT NULL,

        customer_id STRING,
        account_id STRING,
        merchant_id STRING,

        transaction_event_timestamp TIMESTAMP,

        amount DOUBLE,
        amount_log1p DOUBLE,

        hour_of_day INT,
        day_of_week INT,
        is_weekend BOOLEAN,

        is_cross_border BOOLEAN,
        is_card_not_present BOOLEAN,

        is_pos BOOLEAN,
        is_ecommerce BOOLEAN,
        is_mobile BOOLEAN,
        is_atm BOOLEAN,

        is_debit_card BOOLEAN,
        is_credit_card BOOLEAN,
        is_digital_wallet BOOLEAN,
        is_bank_transfer BOOLEAN,

        CONSTRAINT transaction_fraud_features_pk
            PRIMARY KEY (transaction_id)
    )
    USING DELTA

    TBLPROPERTIES (
        'delta.enableChangeDataFeed' = 'true',
        'delta.enableRowTracking' = 'true'
    )
    """
)


spark_session.sql(
    f"""
    CREATE TABLE IF NOT EXISTS {CUSTOMER_FEATURE_TABLE} (

        customer_id STRING NOT NULL,
        feature_timestamp TIMESTAMP NOT NULL,

        customer_txn_count_1d BIGINT,
        customer_txn_count_7d BIGINT,
        customer_txn_count_30d BIGINT,

        customer_amount_sum_1d DOUBLE,
        customer_amount_sum_7d DOUBLE,

        customer_avg_amount_30d DOUBLE,

        customer_decline_rate_30d DOUBLE,
        customer_foreign_rate_30d DOUBLE,
        customer_card_not_present_rate_30d DOUBLE,

        CONSTRAINT customer_behavior_features_pk
            PRIMARY KEY (
                customer_id,
                feature_timestamp TIMESERIES
            )
    )
    USING DELTA

    TBLPROPERTIES (
        'delta.enableChangeDataFeed' = 'true',
        'delta.enableRowTracking' = 'true'
    )
    """
)


spark_session.sql(
    f"""
    CREATE TABLE IF NOT EXISTS {MERCHANT_FEATURE_TABLE} (

        merchant_id STRING NOT NULL,
        feature_timestamp TIMESTAMP NOT NULL,

        merchant_txn_count_1d BIGINT,
        merchant_txn_count_7d BIGINT,
        merchant_txn_count_30d BIGINT,

        merchant_amount_sum_1d DOUBLE,
        merchant_amount_sum_7d DOUBLE,

        merchant_avg_amount_30d DOUBLE,

        merchant_decline_rate_30d DOUBLE,
        merchant_foreign_rate_30d DOUBLE,
        merchant_card_not_present_rate_30d DOUBLE,

        CONSTRAINT merchant_behavior_features_pk
            PRIMARY KEY (
                merchant_id,
                feature_timestamp TIMESERIES
            )
    )
    USING DELTA

    TBLPROPERTIES (
        'delta.enableChangeDataFeed' = 'true',
        'delta.enableRowTracking' = 'true'
    )
    """
)


# COMMAND ----------
# ----------------------------------------------------------------------------
# Trusted feature source
#
# Use VALIDATED transactions, not fraud-enriched output, as the fundamental
# feature source.
#
# This prevents fraud outcome information from accidentally leaking into
# feature computation.
# ----------------------------------------------------------------------------

transactions = spark_session.table(f"{CATALOG}.silver.payment_transactions_validated").alias("t")

accounts = (
    spark_session.table(f"{CATALOG}.silver.accounts_current")
    .select(
        "account_id",
        "customer_id",
    )
    .alias("a")
)

base_transactions = transactions.join(
    accounts,
    on="account_id",
    how="left",
)


# COMMAND ----------
# ----------------------------------------------------------------------------
# Transaction-level features
#
# These are features available directly from the payment transaction.
#
# Do NOT include:
#
# - fraud_outcome
# - has_fraud_case
# - fraud_case_status
#
# because those are post-event labels and would create target leakage.
# ----------------------------------------------------------------------------

transaction_features = base_transactions.select(
    F.col("transaction_id"),
    F.col("customer_id"),
    F.col("account_id"),
    F.col("merchant_id"),
    F.col("event_timestamp").alias("transaction_event_timestamp"),
    F.col("amount").cast("double").alias("amount"),
    F.log1p(F.col("amount").cast("double")).alias("amount_log1p"),
    F.hour(F.col("event_timestamp")).alias("hour_of_day"),
    F.dayofweek(F.col("event_timestamp")).alias("day_of_week"),
    F.dayofweek(F.col("event_timestamp"))
    .isin(
        1,
        7,
    )
    .alias("is_weekend"),
    (F.upper(F.col("country")) != F.lit("AU")).alias("is_cross_border"),
    (
        ~F.coalesce(
            F.col("card_present"),
            F.lit(False),
        )
    ).alias("is_card_not_present"),
    (F.col("channel") == "POS").alias("is_pos"),
    (F.col("channel") == "ECOMMERCE").alias("is_ecommerce"),
    (F.col("channel") == "MOBILE").alias("is_mobile"),
    (F.col("channel") == "ATM").alias("is_atm"),
    (F.col("payment_method") == "DEBIT_CARD").alias("is_debit_card"),
    (F.col("payment_method") == "CREDIT_CARD").alias("is_credit_card"),
    (F.col("payment_method") == "DIGITAL_WALLET").alias("is_digital_wallet"),
    (F.col("payment_method") == "BANK_TRANSFER").alias("is_bank_transfer"),
).dropDuplicates(["transaction_id"])


# COMMAND ----------
# ----------------------------------------------------------------------------
# Reusable point-in-time behavioural feature computation
# ----------------------------------------------------------------------------


def build_behavior_features(
    dataframe: DataFrame,
    entity_column: str,
    prefix: str,
) -> DataFrame:
    """Calculate prior-transaction behaviour for one business entity.

    The windows end at -1 second.

    This means the transaction occurring at feature_timestamp is NOT included
    in its own historical features.

    This prevents training leakage.
    """

    observations = (
        dataframe.filter(F.col(entity_column).isNotNull())
        .groupBy(
            entity_column,
            "event_timestamp",
        )
        .agg(
            F.count("*").alias("_transaction_count"),
            F.sum(F.col("amount").cast("double")).alias("_amount_sum"),
            F.sum(
                F.when(
                    F.col("transaction_status") == "DECLINED",
                    1,
                ).otherwise(0)
            ).alias("_declined_count"),
            F.sum(
                F.when(
                    F.upper(F.col("country")) != "AU",
                    1,
                ).otherwise(0)
            ).alias("_foreign_count"),
            F.sum(
                F.when(
                    ~F.coalesce(
                        F.col("card_present"),
                        F.lit(False),
                    ),
                    1,
                ).otherwise(0)
            ).alias("_card_not_present_count"),
        )
        .withColumnRenamed(
            "event_timestamp",
            "feature_timestamp",
        )
    )

    order_seconds = F.col("feature_timestamp").cast("long")

    one_day = (
        Window.partitionBy(entity_column)
        .orderBy(order_seconds)
        .rangeBetween(
            -SECONDS_PER_DAY,
            -1,
        )
    )

    seven_days = (
        Window.partitionBy(entity_column)
        .orderBy(order_seconds)
        .rangeBetween(
            -(7 * SECONDS_PER_DAY),
            -1,
        )
    )

    thirty_days = (
        Window.partitionBy(entity_column)
        .orderBy(order_seconds)
        .rangeBetween(
            -(30 * SECONDS_PER_DAY),
            -1,
        )
    )

    transaction_count_1d = F.coalesce(
        F.sum("_transaction_count").over(one_day),
        F.lit(0),
    )

    transaction_count_7d = F.coalesce(
        F.sum("_transaction_count").over(seven_days),
        F.lit(0),
    )

    transaction_count_30d = F.coalesce(
        F.sum("_transaction_count").over(thirty_days),
        F.lit(0),
    )

    amount_sum_1d = F.coalesce(
        F.sum("_amount_sum").over(one_day),
        F.lit(0.0),
    )

    amount_sum_7d = F.coalesce(
        F.sum("_amount_sum").over(seven_days),
        F.lit(0.0),
    )

    amount_sum_30d = F.coalesce(
        F.sum("_amount_sum").over(thirty_days),
        F.lit(0.0),
    )

    declined_count_30d = F.coalesce(
        F.sum("_declined_count").over(thirty_days),
        F.lit(0),
    )

    foreign_count_30d = F.coalesce(
        F.sum("_foreign_count").over(thirty_days),
        F.lit(0),
    )

    card_not_present_count_30d = F.coalesce(
        F.sum("_card_not_present_count").over(thirty_days),
        F.lit(0),
    )

    return observations.select(
        F.col(entity_column),
        F.col("feature_timestamp"),
        transaction_count_1d.cast("long").alias(f"{prefix}_txn_count_1d"),
        transaction_count_7d.cast("long").alias(f"{prefix}_txn_count_7d"),
        transaction_count_30d.cast("long").alias(f"{prefix}_txn_count_30d"),
        amount_sum_1d.cast("double").alias(f"{prefix}_amount_sum_1d"),
        amount_sum_7d.cast("double").alias(f"{prefix}_amount_sum_7d"),
        F.when(
            transaction_count_30d > 0,
            amount_sum_30d / transaction_count_30d,
        )
        .otherwise(F.lit(0.0))
        .cast("double")
        .alias(f"{prefix}_avg_amount_30d"),
        F.when(
            transaction_count_30d > 0,
            declined_count_30d / transaction_count_30d,
        )
        .otherwise(F.lit(0.0))
        .cast("double")
        .alias(f"{prefix}_decline_rate_30d"),
        F.when(
            transaction_count_30d > 0,
            foreign_count_30d / transaction_count_30d,
        )
        .otherwise(F.lit(0.0))
        .cast("double")
        .alias(f"{prefix}_foreign_rate_30d"),
        F.when(
            transaction_count_30d > 0,
            card_not_present_count_30d / transaction_count_30d,
        )
        .otherwise(F.lit(0.0))
        .cast("double")
        .alias(f"{prefix}_card_not_present_rate_30d"),
    )


# COMMAND ----------

customer_features = build_behavior_features(
    dataframe=base_transactions,
    entity_column="customer_id",
    prefix="customer",
)

merchant_features = build_behavior_features(
    dataframe=base_transactions,
    entity_column="merchant_id",
    prefix="merchant",
)


# COMMAND ----------
# ----------------------------------------------------------------------------
# Preserve Feature Store constraints by MERGEing rather than replacing tables.
# ----------------------------------------------------------------------------


def merge_features(
    dataframe: DataFrame,
    table_name: str,
    keys: list[str],
) -> None:
    """Upsert a complete feature DataFrame into an existing feature table."""

    temporary_view = "_feature_source_" + table_name.split(".")[-1]

    dataframe.createOrReplaceTempView(temporary_view)

    merge_condition = " AND ".join(f"target.`{key}` = source.`{key}`" for key in keys)

    spark_session.sql(
        f"""
        MERGE INTO {table_name} AS target

        USING {temporary_view} AS source

        ON {merge_condition}

        WHEN MATCHED THEN
            UPDATE SET *

        WHEN NOT MATCHED THEN
            INSERT *
        """
    )


merge_features(
    dataframe=transaction_features,
    table_name=TRANSACTION_FEATURE_TABLE,
    keys=[
        "transaction_id",
    ],
)

merge_features(
    dataframe=customer_features,
    table_name=CUSTOMER_FEATURE_TABLE,
    keys=[
        "customer_id",
        "feature_timestamp",
    ],
)

merge_features(
    dataframe=merchant_features,
    table_name=MERCHANT_FEATURE_TABLE,
    keys=[
        "merchant_id",
        "feature_timestamp",
    ],
)


# COMMAND ----------
# ----------------------------------------------------------------------------
# Build training labels.
#
# Fraud outcome is used ONLY here.
#
# It is not present in any feature table.
#
# UNDETERMINED cases are excluded because their final ground truth is unknown.
# ----------------------------------------------------------------------------

fraud_cases = spark_session.table(f"{CATALOG}.silver.fraud_cases_current").select(
    "transaction_id",
    "fraud_outcome",
)

labels = (
    base_transactions.select(
        "transaction_id",
        "customer_id",
        "merchant_id",
        "event_timestamp",
    )
    .join(
        fraud_cases,
        on="transaction_id",
        how="left",
    )
    .filter(F.col("customer_id").isNotNull())
    .filter(F.col("merchant_id").isNotNull())
    .filter(F.col("fraud_outcome").isNull() | (F.col("fraud_outcome") != "UNDETERMINED"))
    .withColumn(
        "is_confirmed_fraud",
        F.when(
            F.col("fraud_outcome") == "CONFIRMED_FRAUD",
            F.lit(1),
        ).otherwise(F.lit(0)),
    )
    .drop("fraud_outcome")
)


# COMMAND ----------
# ----------------------------------------------------------------------------
# Feature Store lookups
#
# Customer and merchant lookups use event_timestamp as the lookup timestamp.
#
# Because those feature tables declare feature_timestamp as TIMESERIES,
# Databricks performs point-in-time feature lookup rather than a normal
# equality join.
# ----------------------------------------------------------------------------

transaction_feature_names = [
    "amount",
    "amount_log1p",
    "hour_of_day",
    "day_of_week",
    "is_weekend",
    "is_cross_border",
    "is_card_not_present",
    "is_pos",
    "is_ecommerce",
    "is_mobile",
    "is_atm",
    "is_debit_card",
    "is_credit_card",
    "is_digital_wallet",
    "is_bank_transfer",
]

customer_feature_names = [
    "customer_txn_count_1d",
    "customer_txn_count_7d",
    "customer_txn_count_30d",
    "customer_amount_sum_1d",
    "customer_amount_sum_7d",
    "customer_avg_amount_30d",
    "customer_decline_rate_30d",
    "customer_foreign_rate_30d",
    "customer_card_not_present_rate_30d",
]

merchant_feature_names = [
    "merchant_txn_count_1d",
    "merchant_txn_count_7d",
    "merchant_txn_count_30d",
    "merchant_amount_sum_1d",
    "merchant_amount_sum_7d",
    "merchant_avg_amount_30d",
    "merchant_decline_rate_30d",
    "merchant_foreign_rate_30d",
    "merchant_card_not_present_rate_30d",
]


feature_lookups = [
    FeatureLookup(
        table_name=TRANSACTION_FEATURE_TABLE,
        feature_names=transaction_feature_names,
        lookup_key="transaction_id",
    ),
    FeatureLookup(
        table_name=CUSTOMER_FEATURE_TABLE,
        feature_names=customer_feature_names,
        lookup_key="customer_id",
        timestamp_lookup_key="event_timestamp",
    ),
    FeatureLookup(
        table_name=MERCHANT_FEATURE_TABLE,
        feature_names=merchant_feature_names,
        lookup_key="merchant_id",
        timestamp_lookup_key="event_timestamp",
    ),
]


# COMMAND ----------

feature_engineering_client = FeatureEngineeringClient()


training_set = feature_engineering_client.create_training_set(
    df=labels,
    feature_lookups=feature_lookups,
    label="is_confirmed_fraud",
    exclude_columns=[
        "customer_id",
        "merchant_id",
    ],
)


training_dataframe = training_set.load_df()


# COMMAND ----------
# Persist the reproducible training snapshot for Milestone 8.

(
    training_dataframe.write.mode("overwrite")
    .option(
        "overwriteSchema",
        "true",
    )
    .saveAsTable(TRAINING_DATASET_TABLE)
)


# COMMAND ----------
# Validation output

print(
    "Transaction feature rows:",
    spark_session.table(TRANSACTION_FEATURE_TABLE).count(),
)

print(
    "Customer feature rows:",
    spark_session.table(CUSTOMER_FEATURE_TABLE).count(),
)

print(
    "Merchant feature rows:",
    spark_session.table(MERCHANT_FEATURE_TABLE).count(),
)

print(
    "Training rows:",
    spark_session.table(TRAINING_DATASET_TABLE).count(),
)


display(
    spark_session.table(TRAINING_DATASET_TABLE)
    .groupBy("is_confirmed_fraud")
    .count()
    .orderBy("is_confirmed_fraud")
)
