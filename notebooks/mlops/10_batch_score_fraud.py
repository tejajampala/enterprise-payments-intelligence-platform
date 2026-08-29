# Databricks notebook source

"""Batch score fraud data using the Unity Catalog Champion model."""

# COMMAND ----------

import mlflow
import pandas as pd
from mlflow.tracking import MlflowClient
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

spark_session = SparkSession.getActiveSession()

if spark_session is None:
    raise RuntimeError("No active SparkSession is available")


dbutils.widgets.text(
    "catalog_name",
    "payments_dev",
)


CATALOG = dbutils.widgets.get("catalog_name")


MODEL_NAME = f"{CATALOG}.models.fraud_detection_model"

SOURCE_TABLE = f"{CATALOG}.features.fraud_training_dataset"

OUTPUT_TABLE = f"{CATALOG}.ml.fraud_batch_predictions"


FEATURE_COLUMNS = [
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
    "customer_txn_count_1d",
    "customer_txn_count_7d",
    "customer_txn_count_30d",
    "customer_amount_sum_1d",
    "customer_amount_sum_7d",
    "customer_avg_amount_30d",
    "customer_decline_rate_30d",
    "customer_foreign_rate_30d",
    "customer_card_not_present_rate_30d",
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


# COMMAND ----------

mlflow.set_registry_uri("databricks-uc")


registry_client = MlflowClient(registry_uri="databricks-uc")


champion = registry_client.get_model_version_by_alias(
    MODEL_NAME,
    "Champion",
)


model = mlflow.pyfunc.load_model(f"models:/{MODEL_NAME}@Champion")


# COMMAND ----------

source_pdf = (
    spark_session.table(SOURCE_TABLE)
    .select(
        "transaction_id",
        "event_timestamp",
        *FEATURE_COLUMNS,
    )
    .orderBy("event_timestamp")
    .toPandas()
)


model_input = source_pdf[FEATURE_COLUMNS].astype("float64").fillna(0.0)


predictions = model.predict(model_input)


if not isinstance(
    predictions,
    pd.DataFrame,
):
    raise TypeError("Champion fraud model must return a pandas DataFrame")


output_pdf = (
    source_pdf[
        [
            "transaction_id",
            "event_timestamp",
        ]
    ]
    .reset_index(drop=True)
    .join(predictions.reset_index(drop=True))
)


output_pdf["registered_model_name"] = MODEL_NAME


output_pdf["model_version"] = str(champion.version)


output_pdf["model_alias"] = "Champion"


output_spark = spark_session.createDataFrame(output_pdf).withColumn(
    "scored_at",
    F.current_timestamp(),
)


(
    output_spark.write.mode("overwrite")
    .option(
        "overwriteSchema",
        "true",
    )
    .saveAsTable(OUTPUT_TABLE)
)


display(spark_session.table(OUTPUT_TABLE).orderBy(F.desc("fraud_probability")))
