# Databricks notebook source

"""Deploy the fraud Champion version to Databricks Model Serving."""

# COMMAND ----------

import json

from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import NotFound
from databricks.sdk.service.serving import (
    EndpointCoreConfigInput,
    ServedEntityInput,
)
from mlflow.tracking import MlflowClient
from pyspark.sql import SparkSession

spark_session = SparkSession.getActiveSession()

if spark_session is None:
    raise RuntimeError("No active SparkSession is available")


dbutils.widgets.text(
    "catalog_name",
    "payments_dev",
)

dbutils.widgets.text(
    "endpoint_name",
    "epip-dev-fraud-serving",
)


CATALOG = dbutils.widgets.get("catalog_name")

ENDPOINT_NAME = dbutils.widgets.get("endpoint_name")


MODEL_NAME = f"{CATALOG}.models.fraud_detection_model"


TRAINING_TABLE = f"{CATALOG}.features.fraud_training_dataset"


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

registry_client = MlflowClient(registry_uri="databricks-uc")


champion = registry_client.get_model_version_by_alias(
    MODEL_NAME,
    "Champion",
)


champion_version = str(champion.version)


served_entity = ServedEntityInput(
    name=(f"fraud-champion-v{champion_version}"),
    entity_name=MODEL_NAME,
    entity_version=champion_version,
    workload_size="Small",
    scale_to_zero_enabled=True,
)


workspace = WorkspaceClient()


# COMMAND ----------
# Create or update endpoint.

try:
    workspace.serving_endpoints.get(ENDPOINT_NAME)

    endpoint = workspace.serving_endpoints.update_config_and_wait(
        name=ENDPOINT_NAME,
        served_entities=[served_entity],
    )

    operation = "updated"

except NotFound:
    endpoint = workspace.serving_endpoints.create_and_wait(
        name=ENDPOINT_NAME,
        config=(
            EndpointCoreConfigInput(
                name=ENDPOINT_NAME,
                served_entities=[served_entity],
            )
        ),
    )

    operation = "created"


# COMMAND ----------
# Smoke test with one governed feature record.

sample_pdf = spark_session.table(TRAINING_TABLE).select(*FEATURE_COLUMNS).limit(1).toPandas()


records = json.loads(sample_pdf.to_json(orient="records"))


response = workspace.serving_endpoints.query(
    name=ENDPOINT_NAME,
    dataframe_records=records,
    client_request_id=("epip-m10-smoke-test"),
)


print(
    json.dumps(
        {
            "endpoint": ENDPOINT_NAME,
            "operation": operation,
            "registered_model": (MODEL_NAME),
            "champion_version": (champion_version),
            "endpoint_state": (endpoint.state.as_dict() if endpoint.state else None),
            "smoke_test_response": (response.as_dict()),
        },
        indent=2,
        default=str,
    )
)
