# Databricks notebook source
"""M15D — fraud-model promotion evidence gate."""

from __future__ import annotations

import json
import math

from mlflow.exceptions import MlflowException
from mlflow.tracking import MlflowClient
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

spark = SparkSession.getActiveSession()

if spark is None:
    raise RuntimeError("No active SparkSession is available")


dbutils.widgets.text("evidence_catalog", "payments_dev")
dbutils.widgets.text("fraud_min_recall", "0.50")


CATALOG = dbutils.widgets.get("evidence_catalog").strip()
MIN_RECALL = float(dbutils.widgets.get("fraud_min_recall"))


FRAUD_EVALUATION_TABLE = f"{CATALOG}.ml.fraud_model_evaluation"
FRAUD_TRAINING_TABLE = f"{CATALOG}.features.fraud_training_dataset"

REGISTERED_MODEL = f"{CATALOG}.models.fraud_detection_model"


def finite(value: object) -> bool:
    if value is None:
        return False

    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return False

    return math.isfinite(numeric)


rows = (
    spark.table(FRAUD_EVALUATION_TABLE)
    .filter((F.col("evaluation_split") == "test") & (F.col("is_selected_model") == F.lit(True)))
    .orderBy(F.desc("average_precision"))
    .limit(1)
    .collect()
)

if not rows:
    raise RuntimeError(f"No selected fraud-model test evaluation exists in {FRAUD_EVALUATION_TABLE}")


fraud = rows[0].asDict()

model_uri = fraud.get("model_uri")
recall = float(fraud["recall"])
average_precision = float(fraud["average_precision"])
f2 = float(fraud["f2"])


base_rate_row = spark.table(FRAUD_TRAINING_TABLE).agg(F.avg("is_confirmed_fraud").alias("fraud_base_rate")).first()

if base_rate_row is None or base_rate_row["fraud_base_rate"] is None:
    raise RuntimeError("Unable to calculate fraud prevalence")

fraud_base_rate = float(base_rate_row["fraud_base_rate"])


registry = MlflowClient(registry_uri="databricks-uc")

try:
    champion = registry.get_model_version_by_alias(
        REGISTERED_MODEL,
        "Champion",
    )
except MlflowException as exc:
    raise RuntimeError(f"No Champion version exists for {REGISTERED_MODEL}") from exc


champion_tags = champion.tags or {}

champion_source_uri = champion_tags.get("epip_training_model_uri")


checks = {
    "selected_test_result_exists": True,
    "model_uri_present": bool(model_uri),
    "average_precision_finite": finite(average_precision),
    "average_precision_beats_base_rate": (average_precision >= fraud_base_rate),
    "recall_finite": finite(recall),
    "minimum_recall": recall >= MIN_RECALL,
    "f2_positive": finite(f2) and f2 > 0,
    "champion_exists": champion is not None,
    "champion_matches_selected_model": (champion_source_uri == model_uri),
}


failed = [name for name, passed in checks.items() if not passed]


print(
    json.dumps(
        {
            "registered_model": REGISTERED_MODEL,
            "champion_version": str(champion.version),
            "model_uri": model_uri,
            "average_precision": average_precision,
            "fraud_base_rate": fraud_base_rate,
            "recall": recall,
            "minimum_recall": MIN_RECALL,
            "f2": f2,
            "checks": checks,
            "failed_gates": failed,
        },
        indent=2,
        default=str,
    )
)


if failed:
    print("EPIP_ML_PROMOTION_GATE=FAIL")
    raise RuntimeError(f"Fraud model promotion gate failed: {failed}")


print("EPIP_ML_PROMOTION_GATE=PASS")
