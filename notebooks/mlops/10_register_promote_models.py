# Databricks notebook source

"""Milestone 10 — Governed model registration and promotion.

This notebook implements the enterprise MLOps lifecycle for:

- fraud detection
- payment-volume forecasting

Responsibilities:

1. Read final M8/M9 evaluation results.
2. Apply model quality gates.
3. Package the fraud model for production inference.
4. Register approved learned models in Unity Catalog.
5. Add governed model-version metadata.
6. Promote versions using Candidate / Champion aliases.
7. Preserve the previous Champion for rollback.
8. Write an auditable model-lifecycle record.

Model Serving and batch inference are handled by downstream M10 tasks.
"""

# COMMAND ----------

import json
import math
from typing import Any
from uuid import uuid4

import mlflow
import mlflow.pyfunc
import mlflow.sklearn
import pandas as pd
import sklearn
from mlflow.exceptions import MlflowException
from mlflow.models import infer_signature
from mlflow.tracking import MlflowClient
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

# COMMAND ----------
# Spark session.

spark_session = SparkSession.getActiveSession()

if spark_session is None:
    raise RuntimeError("No active SparkSession is available for the MLOps lifecycle job")


# COMMAND ----------
# Runtime configuration.

dbutils.widgets.text(
    "catalog_name",
    "payments_dev",
)

dbutils.widgets.text(
    "fraud_min_recall",
    "0.50",
)

dbutils.widgets.text(
    "forecast_max_wape",
    "1.00",
)


CATALOG = dbutils.widgets.get("catalog_name")

FRAUD_MIN_RECALL = float(dbutils.widgets.get("fraud_min_recall"))

FORECAST_MAX_WAPE = float(dbutils.widgets.get("forecast_max_wape"))


# COMMAND ----------
# Source tables from Milestones 8 and 9.

FRAUD_EVALUATION_TABLE = f"{CATALOG}.ml.fraud_model_evaluation"

FORECAST_EVALUATION_TABLE = f"{CATALOG}.ml.payment_volume_forecast_evaluation"

FRAUD_TRAINING_TABLE = f"{CATALOG}.features.fraud_training_dataset"


# COMMAND ----------
# MLOps output table.

AUDIT_TABLE = f"{CATALOG}.ml.model_lifecycle_audit"


# COMMAND ----------
# Unity Catalog registered model names.

FRAUD_REGISTERED_MODEL = f"{CATALOG}.models.fraud_detection_model"

FORECAST_REGISTERED_MODEL = f"{CATALOG}.models.payment_volume_forecaster"


# COMMAND ----------
# Fraud model production features.
#
# Keep this contract synchronized with Milestone 8.

FRAUD_FEATURE_COLUMNS = [
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
# MLflow configuration.

mlflow.set_tracking_uri("databricks")

mlflow.set_registry_uri("databricks-uc")

mlflow.set_experiment("/Shared/epip-dev-mlops")


registry_client = MlflowClient(registry_uri="databricks-uc")


# COMMAND ----------
# Production fraud-serving wrapper.
#
# The Milestone 8 classifier itself exposes predict() and predict_proba().
#
# For production we want the serving contract to return:
#
# - fraud_probability
# - predicted_fraud
#
# using the threshold selected during M8 validation.


class FraudServingModel(mlflow.pyfunc.PythonModel):
    """Production fraud-scoring MLflow model."""

    def __init__(
        self,
        classifier: Any,
        threshold: float,
        feature_columns: list[str],
    ) -> None:
        self.classifier = classifier
        self.threshold = threshold
        self.feature_columns = feature_columns

    def predict(
        self,
        context: Any,
        model_input: pd.DataFrame,
        params: dict[str, Any] | None = None,
    ) -> pd.DataFrame:
        """Return fraud probability and thresholded decision."""

        del context
        del params

        missing_features = [column for column in self.feature_columns if column not in model_input.columns]

        if missing_features:
            raise ValueError(f"Fraud model input is missing required features: {missing_features}")

        matrix = model_input[self.feature_columns].astype("float64").fillna(0.0)

        probabilities = self.classifier.predict_proba(matrix)[
            :,
            1,
        ]

        predictions = (probabilities >= self.threshold).astype(int)

        return pd.DataFrame(
            {
                "fraud_probability": (probabilities),
                "predicted_fraud": (predictions),
            }
        )


# COMMAND ----------
# Utility functions.


def finite_metric(
    value: Any,
) -> bool:
    """Return True when a value is a finite numeric metric."""

    if value is None:
        return False

    try:
        numeric_value = float(value)

    except (
        TypeError,
        ValueError,
    ):
        return False

    return math.isfinite(numeric_value)


def find_existing_version(
    model_name: str,
    source_tag: str,
    source_value: str,
):
    """Find an existing registered version linked to a source model.

    Model-version listing responses are followed by a full version lookup so
    that the complete tag dictionary is available.

    This makes reruns idempotent after a successfully tagged registration.
    """

    versions = registry_client.search_model_versions(f"name='{model_name}'")

    for version in versions:
        try:
            full_version = registry_client.get_model_version(
                model_name,
                version.version,
            )

        except MlflowException:
            continue

        tags = full_version.tags or {}

        if tags.get(source_tag) == source_value:
            return full_version

    return None


def set_version_tags(
    model_name: str,
    version: str,
    tags: dict[str, str],
) -> None:
    """Apply Unity Catalog-safe model-version tags."""

    for key, value in tags.items():
        registry_client.set_model_version_tag(
            model_name,
            version,
            key,
            value,
        )


def get_alias_or_none(
    model_name: str,
    alias: str,
):
    """Return a model version for an alias if the alias exists."""

    try:
        return registry_client.get_model_version_by_alias(
            model_name,
            alias,
        )

    except MlflowException:
        return None


def promote_version(
    model_name: str,
    version: str,
) -> None:
    """Promote a model version through the EPIP alias lifecycle.

    Candidate
        ↓
    Champion

    Existing Champion
        ↓
    PreviousChampion
    """

    # Candidate identifies the version that passed current lifecycle checks.

    registry_client.set_registered_model_alias(
        model_name,
        "Candidate",
        version,
    )

    current_champion = get_alias_or_none(
        model_name,
        "Champion",
    )

    # Preserve the previous production version for rollback.

    if current_champion is not None and str(current_champion.version) != str(version):
        registry_client.set_registered_model_alias(
            model_name,
            "PreviousChampion",
            current_champion.version,
        )

    # Promote approved Candidate to Champion.

    registry_client.set_registered_model_alias(
        model_name,
        "Champion",
        version,
    )


# COMMAND ----------
# ---------------------------------------------------------------------------
# FRAUD MODEL QUALITY GATE
# ---------------------------------------------------------------------------

fraud_result = (
    spark_session.table(FRAUD_EVALUATION_TABLE)
    .filter((F.col("evaluation_split") == "test") & (F.col("is_selected_model") == F.lit(True)))
    .orderBy(F.desc("average_precision"))
    .limit(1)
    .collect()
)


if not fraud_result:
    raise ValueError(f"No selected fraud model test result was found in {FRAUD_EVALUATION_TABLE}")


fraud = fraud_result[0].asDict()


fraud_source_model_uri = fraud.get("model_uri")


if not fraud_source_model_uri:
    raise ValueError("Selected fraud model does not contain an MLflow model URI")


fraud_threshold = float(fraud["decision_threshold"])

fraud_recall = float(fraud["recall"])

fraud_average_precision = float(fraud["average_precision"])

fraud_f2 = float(fraud["f2"])


# COMMAND ----------
# Calculate fraud prevalence baseline.
#
# Average Precision should beat the raw positive-class prevalence.

fraud_base_rate_row = (
    spark_session.table(FRAUD_TRAINING_TABLE).agg(F.avg("is_confirmed_fraud").alias("fraud_base_rate")).first()
)


if fraud_base_rate_row is None or fraud_base_rate_row["fraud_base_rate"] is None:
    raise ValueError(f"Unable to calculate fraud base rate from {FRAUD_TRAINING_TABLE}")


fraud_base_rate = float(fraud_base_rate_row["fraud_base_rate"])


# COMMAND ----------
# Fraud promotion gates.

fraud_gate_checks = {
    "model_uri_present": bool(fraud_source_model_uri),
    "average_precision_finite": (finite_metric(fraud_average_precision)),
    "average_precision_beats_base_rate": (fraud_average_precision >= fraud_base_rate),
    "recall_finite": (finite_metric(fraud_recall)),
    "minimum_recall": (fraud_recall >= FRAUD_MIN_RECALL),
    "f2_positive": (finite_metric(fraud_f2) and fraud_f2 > 0),
}


failed_fraud_gates = [
    gate_name
    for (
        gate_name,
        passed,
    ) in fraud_gate_checks.items()
    if not passed
]


if failed_fraud_gates:
    raise ValueError(
        "Fraud model failed MLOps promotion gates. "
        f"Failed gates: {failed_fraud_gates}. "
        f"All results: {fraud_gate_checks}"
    )


print(
    "Fraud quality gates PASSED:",
    fraud_gate_checks,
)


# COMMAND ----------
# ---------------------------------------------------------------------------
# FRAUD MODEL REGISTRATION
# ---------------------------------------------------------------------------
#
# First try to find a previously registered version created from the exact
# same Milestone 8 model artifact.
#
# This prevents duplicate versions after successful reruns.

existing_fraud_version = find_existing_version(
    FRAUD_REGISTERED_MODEL,
    "epip_training_model_uri",
    fraud_source_model_uri,
)


if existing_fraud_version is not None:
    fraud_registered_version = str(existing_fraud_version.version)

    print(
        "Reusing existing fraud registered model version:",
        fraud_registered_version,
    )

else:
    # Load the selected Milestone 8 sklearn classifier.

    classifier = mlflow.sklearn.load_model(fraud_source_model_uri)

    # Build a governed production input example.

    input_example = (
        spark_session.table(FRAUD_TRAINING_TABLE)
        .select(*FRAUD_FEATURE_COLUMNS)
        .limit(5)
        .toPandas()
        .astype("float64")
        .fillna(0.0)
    )

    if input_example.empty:
        raise ValueError("Unable to build fraud serving input example because the training table is empty")

    # Wrap the classifier with the business decision threshold.

    serving_model = FraudServingModel(
        classifier=classifier,
        threshold=fraud_threshold,
        feature_columns=(FRAUD_FEATURE_COLUMNS),
    )

    example_output = serving_model.predict(
        context=None,
        model_input=(input_example),
    )

    signature = infer_signature(
        input_example,
        example_output,
    )

    # Log the production-serving package as a new MLflow Logged Model.

    with mlflow.start_run(run_name=("package-fraud-serving-model")) as packaging_run:
        mlflow.set_tags(
            {
                "epip_use_case": ("fraud_detection"),
                "epip_milestone": ("10"),
                "epip_source_model_uri": (fraud_source_model_uri),
            }
        )

        serving_model_info = mlflow.pyfunc.log_model(
            name=("fraud_serving_package"),
            python_model=(serving_model),
            signature=(signature),
            input_example=(input_example),
            pip_requirements=[
                (f"mlflow=={mlflow.__version__}"),
                (f"scikit-learn=={sklearn.__version__}"),
                (f"pandas=={pd.__version__}"),
            ],
        )

        print(
            "Fraud serving package logged:",
            serving_model_info.model_uri,
        )

        print(
            "Fraud packaging run:",
            packaging_run.info.run_id,
        )

    # Register in Unity Catalog.
    #
    # Tag keys deliberately use underscores because Unity Catalog rejects
    # reserved characters such as "." in tag keys.

    registered_fraud = mlflow.register_model(
        serving_model_info.model_uri,
        FRAUD_REGISTERED_MODEL,
        await_registration_for=300,
        tags={
            "epip_training_model_uri": (fraud_source_model_uri),
            "epip_decision_threshold": (str(fraud_threshold)),
            "epip_test_average_precision": (str(fraud_average_precision)),
            "epip_test_recall": (str(fraud_recall)),
            "epip_test_f2": (str(fraud_f2)),
            "epip_use_case": ("fraud_detection"),
        },
    )

    fraud_registered_version = str(registered_fraud.version)

    print(
        "Registered new fraud model version:",
        fraud_registered_version,
    )


# COMMAND ----------
# Ensure fraud version metadata is complete even when reusing an existing
# registration.

set_version_tags(
    FRAUD_REGISTERED_MODEL,
    fraud_registered_version,
    {
        "epip_training_model_uri": (fraud_source_model_uri),
        "epip_decision_threshold": (str(fraud_threshold)),
        "epip_test_average_precision": (str(fraud_average_precision)),
        "epip_test_recall": (str(fraud_recall)),
        "epip_test_f2": (str(fraud_f2)),
        "epip_fraud_base_rate": (str(fraud_base_rate)),
        "epip_use_case": ("fraud_detection"),
    },
)


# COMMAND ----------
# Promote fraud model.

promote_version(
    FRAUD_REGISTERED_MODEL,
    fraud_registered_version,
)


fraud_champion = registry_client.get_model_version_by_alias(
    FRAUD_REGISTERED_MODEL,
    "Champion",
)


if str(fraud_champion.version) != fraud_registered_version:
    raise RuntimeError("Fraud Champion alias validation failed")


print(
    "Fraud Champion promoted:",
    fraud_registered_version,
)


# COMMAND ----------
# ---------------------------------------------------------------------------
# FORECAST QUALITY GATE
# ---------------------------------------------------------------------------

forecast_result = (
    spark_session.table(FORECAST_EVALUATION_TABLE)
    .filter((F.col("evaluation_split") == "test") & (F.col("is_selected_method") == F.lit(True)))
    .limit(1)
    .collect()
)


if not forecast_result:
    raise ValueError(f"No selected forecasting test result was found in {FORECAST_EVALUATION_TABLE}")


forecast = forecast_result[0].asDict()


forecast_method = forecast["method_name"]


forecast_source_model_uri = forecast.get("model_uri") or ""


forecast_wape = float(forecast["wape"])


# COMMAND ----------
# Forecast quality gates.

forecast_gate_checks = {
    "wape_finite": (finite_metric(forecast_wape)),
    "wape_below_limit": (forecast_wape <= FORECAST_MAX_WAPE),
}


failed_forecast_gates = [
    gate_name
    for (
        gate_name,
        passed,
    ) in forecast_gate_checks.items()
    if not passed
]


if failed_forecast_gates:
    raise ValueError(
        "Forecasting method failed MLOps promotion gates. "
        f"Failed gates: {failed_forecast_gates}. "
        f"All results: {forecast_gate_checks}"
    )


print(
    "Forecast quality gates PASSED:",
    forecast_gate_checks,
)


# COMMAND ----------
# ---------------------------------------------------------------------------
# FORECAST MODEL REGISTRATION
# ---------------------------------------------------------------------------
#
# A forecasting baseline such as seasonal_naive_7d has no MLflow learned-model
# artifact.
#
# In that case it remains an approved operational policy rather than being
# artificially forced into Model Registry.

forecast_registered_version: str | None = None


forecast_lifecycle_status = "APPROVED_BASELINE_POLICY"


if forecast_source_model_uri:
    existing_forecast_version = find_existing_version(
        FORECAST_REGISTERED_MODEL,
        "epip_training_model_uri",
        forecast_source_model_uri,
    )

    if existing_forecast_version is not None:
        forecast_registered_version = str(existing_forecast_version.version)

        print(
            "Reusing existing forecast model version:",
            forecast_registered_version,
        )

    else:
        registered_forecast = mlflow.register_model(
            forecast_source_model_uri,
            FORECAST_REGISTERED_MODEL,
            await_registration_for=300,
            tags={
                "epip_training_model_uri": (forecast_source_model_uri),
                "epip_test_wape": (str(forecast_wape)),
                "epip_forecast_method": (forecast_method),
                "epip_use_case": ("payment_volume_forecasting"),
            },
        )

        forecast_registered_version = str(registered_forecast.version)

        print(
            "Registered new forecast model version:",
            forecast_registered_version,
        )

    if forecast_registered_version is None:
        raise RuntimeError("Forecast model registration returned no model version")

    set_version_tags(
        FORECAST_REGISTERED_MODEL,
        forecast_registered_version,
        {
            "epip_training_model_uri": (forecast_source_model_uri),
            "epip_test_wape": (str(forecast_wape)),
            "epip_forecast_method": (forecast_method),
            "epip_use_case": ("payment_volume_forecasting"),
        },
    )

    promote_version(
        FORECAST_REGISTERED_MODEL,
        forecast_registered_version,
    )

    forecast_champion = registry_client.get_model_version_by_alias(
        FORECAST_REGISTERED_MODEL,
        "Champion",
    )

    if str(forecast_champion.version) != forecast_registered_version:
        raise RuntimeError("Forecast Champion alias validation failed")

    forecast_lifecycle_status = "PROMOTED_CHAMPION"

    print(
        "Forecast Champion promoted:",
        forecast_registered_version,
    )


else:
    print("Forecast selected method has no learned MLflow model artifact.")

    print(
        "Treating forecasting method as approved operational baseline:",
        forecast_method,
    )


# COMMAND ----------
# ---------------------------------------------------------------------------
# GOVERNED LIFECYCLE AUDIT
# ---------------------------------------------------------------------------

lifecycle_run_id = str(uuid4())


fraud_metrics_json = json.dumps(
    {
        "average_precision": (fraud_average_precision),
        "recall": (fraud_recall),
        "f2": (fraud_f2),
        "fraud_base_rate": (fraud_base_rate),
        "decision_threshold": (fraud_threshold),
        "minimum_required_recall": (FRAUD_MIN_RECALL),
    },
    sort_keys=True,
)


forecast_metrics_json = json.dumps(
    {
        "wape": (forecast_wape),
        "maximum_allowed_wape": (FORECAST_MAX_WAPE),
    },
    sort_keys=True,
)


audit_rows = [
    {
        "lifecycle_run_id": (lifecycle_run_id),
        "use_case": ("fraud_detection"),
        "registered_model_name": (FRAUD_REGISTERED_MODEL),
        "model_version": (fraud_registered_version),
        "source_model_uri": (fraud_source_model_uri),
        "selected_method": (fraud["model_name"]),
        "gate_status": ("PASSED"),
        "lifecycle_status": ("PROMOTED_CHAMPION"),
        "metrics_json": (fraud_metrics_json),
    },
    {
        "lifecycle_run_id": (lifecycle_run_id),
        "use_case": ("payment_volume_forecasting"),
        "registered_model_name": (FORECAST_REGISTERED_MODEL if forecast_registered_version is not None else None),
        "model_version": (forecast_registered_version),
        "source_model_uri": (forecast_source_model_uri if forecast_source_model_uri else None),
        "selected_method": (forecast_method),
        "gate_status": ("PASSED"),
        "lifecycle_status": (forecast_lifecycle_status),
        "metrics_json": (forecast_metrics_json),
    },
]


audit_df = spark_session.createDataFrame(audit_rows).withColumn(
    "promoted_at",
    F.current_timestamp(),
)


(audit_df.write.mode("append").saveAsTable(AUDIT_TABLE))


# COMMAND ----------
# ---------------------------------------------------------------------------
# FINAL VALIDATION OUTPUT
# ---------------------------------------------------------------------------

result_summary = {
    "lifecycle_run_id": (lifecycle_run_id),
    "fraud": {
        "registered_model": (FRAUD_REGISTERED_MODEL),
        "version": (fraud_registered_version),
        "candidate_alias": ("Candidate"),
        "champion_alias": ("Champion"),
        "decision_threshold": (fraud_threshold),
        "test_average_precision": (fraud_average_precision),
        "test_recall": (fraud_recall),
        "test_f2": (fraud_f2),
        "base_rate": (fraud_base_rate),
    },
    "forecast": {
        "selected_method": (forecast_method),
        "registered_model": (FORECAST_REGISTERED_MODEL if forecast_registered_version is not None else None),
        "version": (forecast_registered_version),
        "lifecycle_status": (forecast_lifecycle_status),
        "test_wape": (forecast_wape),
    },
}


print(
    json.dumps(
        result_summary,
        indent=2,
        default=str,
    )
)


# COMMAND ----------
# Display latest lifecycle audit.

display(spark_session.table(AUDIT_TABLE).filter(F.col("lifecycle_run_id") == lifecycle_run_id).orderBy("use_case"))
