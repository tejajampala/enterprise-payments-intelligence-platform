# Databricks notebook source

"""Milestone 8 — Fraud detection model development.

This notebook implements:

- temporal train / validation / test splitting
- class-imbalance handling
- logistic-regression baseline
- histogram gradient-boosting challenger
- MLflow 3 experiment tracking
- validation-based threshold tuning
- PR / ROC evaluation
- best-model selection
- final untouched test evaluation
- governed evaluation and prediction tables

Model registration and serving are intentionally deferred to Milestone 10.
"""

# COMMAND ----------

import json
from typing import Any

import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from mlflow.models import infer_signature
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    auc,
    average_precision_score,
    confusion_matrix,
    f1_score,
    fbeta_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

# COMMAND ----------
# Runtime configuration

spark_session = SparkSession.getActiveSession()

if spark_session is None:
    raise RuntimeError("No active SparkSession is available")


dbutils.widgets.text(
    "catalog_name",
    "payments_dev",
)

dbutils.widgets.text(
    "experiment_name",
    "/Shared/epip-dev-fraud-detection",
)

dbutils.widgets.text(
    "random_seed",
    "42",
)


CATALOG = dbutils.widgets.get("catalog_name")

EXPERIMENT_NAME = dbutils.widgets.get("experiment_name")

RANDOM_SEED = int(dbutils.widgets.get("random_seed"))


TRAINING_TABLE = f"{CATALOG}.features.fraud_training_dataset"

EVALUATION_TABLE = f"{CATALOG}.ml.fraud_model_evaluation"

PREDICTION_TABLE = f"{CATALOG}.ml.fraud_test_predictions"


LABEL_COLUMN = "is_confirmed_fraud"


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
# Ensure ML schema exists.

spark_session.sql(
    f"""
    CREATE SCHEMA IF NOT EXISTS
    {CATALOG}.ml
    """
)


# COMMAND ----------
# Load the governed Feature Store training snapshot.

required_columns = [
    "transaction_id",
    "event_timestamp",
    *FEATURE_COLUMNS,
    LABEL_COLUMN,
]


training_spark = (
    spark_session.table(TRAINING_TABLE)
    .select(*required_columns)
    .orderBy(
        "event_timestamp",
        "transaction_id",
    )
)


training_pdf = (
    training_spark.toPandas()
    .sort_values(
        [
            "event_timestamp",
            "transaction_id",
        ]
    )
    .reset_index(drop=True)
)


if training_pdf.empty:
    raise ValueError("Fraud training dataset is empty")


if training_pdf[LABEL_COLUMN].nunique() != 2:
    raise ValueError("Fraud training dataset must contain both fraud and non-fraud labels")


# COMMAND ----------
# Temporal train / validation / test split.
#
# OLD data -> training
# NEWER data -> validation
# NEWEST data -> test
#
# This better approximates production fraud scoring than random splitting.

row_count = len(training_pdf)

if row_count < 30:
    raise ValueError("At least 30 labelled rows are required")


train_end = int(row_count * 0.70)

validation_end = int(row_count * 0.85)


train_pdf = training_pdf.iloc[:train_end].copy()

validation_pdf = training_pdf.iloc[train_end:validation_end].copy()

test_pdf = training_pdf.iloc[validation_end:].copy()


def validate_split(
    dataframe: pd.DataFrame,
    split_name: str,
) -> None:
    """Ensure each model-evaluation split contains both classes."""

    label_counts = dataframe[LABEL_COLUMN].value_counts().to_dict()

    if dataframe[LABEL_COLUMN].nunique() != 2:
        raise ValueError(f"{split_name} does not contain both classes. Counts: {label_counts}")


validate_split(
    train_pdf,
    "train",
)

validate_split(
    validation_pdf,
    "validation",
)

validate_split(
    test_pdf,
    "test",
)


# COMMAND ----------
# Model-ready matrices.
#
# transaction_id and event_timestamp are intentionally NOT in FEATURE_COLUMNS.


def feature_matrix(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """Return numeric model features with defensive null handling."""

    matrix = (
        dataframe[FEATURE_COLUMNS]
        .astype("float64")
        .replace(
            [
                np.inf,
                -np.inf,
            ],
            np.nan,
        )
        .fillna(0.0)
    )

    return matrix


X_train = feature_matrix(train_pdf)

y_train = train_pdf[LABEL_COLUMN].astype(int)


X_validation = feature_matrix(validation_pdf)

y_validation = validation_pdf[LABEL_COLUMN].astype(int)


X_test = feature_matrix(test_pdf)

y_test = test_pdf[LABEL_COLUMN].astype(int)


# COMMAND ----------
# Metric helpers.


def classification_metrics(
    y_true: pd.Series,
    probabilities: np.ndarray,
    threshold: float,
) -> dict[str, float]:
    """Calculate fraud-classification metrics at one decision threshold."""

    predictions = (probabilities >= threshold).astype(int)

    tn, fp, fn, tp = confusion_matrix(
        y_true,
        predictions,
        labels=[
            0,
            1,
        ],
    ).ravel()

    curve_precision, curve_recall, _ = precision_recall_curve(
        y_true,
        probabilities,
    )

    return {
        "roc_auc": float(
            roc_auc_score(
                y_true,
                probabilities,
            )
        ),
        "pr_auc": float(
            auc(
                curve_recall,
                curve_precision,
            )
        ),
        "average_precision": float(
            average_precision_score(
                y_true,
                probabilities,
            )
        ),
        "precision": float(
            precision_score(
                y_true,
                predictions,
                zero_division=0,
            )
        ),
        "recall": float(
            recall_score(
                y_true,
                predictions,
                zero_division=0,
            )
        ),
        "f1": float(
            f1_score(
                y_true,
                predictions,
                zero_division=0,
            )
        ),
        "f2": float(
            fbeta_score(
                y_true,
                predictions,
                beta=2,
                zero_division=0,
            )
        ),
        "true_negative": float(tn),
        "false_positive": float(fp),
        "false_negative": float(fn),
        "true_positive": float(tp),
    }


def choose_threshold(
    y_true: pd.Series,
    probabilities: np.ndarray,
) -> tuple[
    float,
    dict[str, float],
]:
    """Choose a fraud threshold from validation data.

    F2 is used because fraud detection usually values recall more highly
    than ordinary accuracy, while still penalizing excessive false positives.
    """

    best_threshold = 0.50

    best_metrics = classification_metrics(
        y_true,
        probabilities,
        best_threshold,
    )

    for threshold in np.arange(
        0.05,
        0.96,
        0.01,
    ):
        metrics = classification_metrics(
            y_true,
            probabilities,
            float(threshold),
        )

        candidate_score = (
            metrics["f2"],
            metrics["precision"],
        )

        current_score = (
            best_metrics["f2"],
            best_metrics["precision"],
        )

        if candidate_score > current_score:
            best_threshold = float(threshold)

            best_metrics = metrics

    return (
        best_threshold,
        best_metrics,
    )


# COMMAND ----------
# Candidate models.
#
# Logistic Regression:
#   interpretable baseline
#
# HistGradientBoosting:
#   nonlinear tree-based challenger

models: dict[
    str,
    Any,
] = {
    "logistic_regression": (
        Pipeline(
            steps=[
                (
                    "scale",
                    StandardScaler(),
                ),
                (
                    "model",
                    LogisticRegression(
                        max_iter=2000,
                        class_weight="balanced",
                        random_state=RANDOM_SEED,
                    ),
                ),
            ]
        )
    ),
    "hist_gradient_boosting": (
        HistGradientBoostingClassifier(
            learning_rate=0.05,
            max_iter=250,
            max_leaf_nodes=31,
            min_samples_leaf=10,
            l2_regularization=1.0,
            class_weight="balanced",
            random_state=RANDOM_SEED,
        )
    ),
}


# COMMAND ----------
# MLflow experiment.

mlflow.set_tracking_uri("databricks")

mlflow.set_experiment(EXPERIMENT_NAME)


evaluation_results: list[dict[str, Any]] = []


candidate_results: dict[
    str,
    dict[str, Any],
] = {}


# COMMAND ----------
# Train candidates and tune threshold ONLY using validation data.

with mlflow.start_run(run_name="fraud-model-comparison") as parent_run:
    mlflow.set_tags(
        {
            "project": "enterprise-payments-intelligence-platform",
            "milestone": "8",
            "use_case": "fraud_detection",
            "split_strategy": "temporal_70_15_15",
        }
    )

    mlflow.log_params(
        {
            "random_seed": RANDOM_SEED,
            "training_table": TRAINING_TABLE,
            "feature_count": len(FEATURE_COLUMNS),
            "train_rows": len(train_pdf),
            "validation_rows": len(validation_pdf),
            "test_rows": len(test_pdf),
        }
    )

    for (
        model_name,
        model,
    ) in models.items():
        with mlflow.start_run(
            run_name=model_name,
            nested=True,
        ) as candidate_run:
            model.fit(
                X_train,
                y_train,
            )

            validation_probability = model.predict_proba(X_validation)[
                :,
                1,
            ]

            (
                selected_threshold,
                validation_metrics,
            ) = choose_threshold(
                y_validation,
                validation_probability,
            )

            mlflow.log_param(
                "decision_threshold",
                selected_threshold,
            )

            mlflow.log_param(
                "model_name",
                model_name,
            )

            mlflow.log_metrics({f"validation_{key}": value for key, value in validation_metrics.items()})

            signature = infer_signature(
                X_train,
                model.predict_proba(X_train)[
                    :,
                    1,
                ],
            )

            candidate_model_info = mlflow.sklearn.log_model(
                model,
                name="candidate_model",
                signature=signature,
                input_example=(X_train.head(5)),
                serialization_format="cloudpickle",
            )

            candidate_result = {
                "model_name": model_name,
                "threshold": selected_threshold,
                "validation_metrics": validation_metrics,
                "candidate_run_id": (candidate_run.info.run_id),
                "candidate_model_uri": (candidate_model_info.model_uri),
            }

            candidate_results[model_name] = candidate_result

            evaluation_results.append(
                {
                    "model_name": model_name,
                    "evaluation_split": "validation",
                    "is_selected_model": False,
                    "decision_threshold": (selected_threshold),
                    "roc_auc": validation_metrics["roc_auc"],
                    "pr_auc": validation_metrics["pr_auc"],
                    "average_precision": (validation_metrics["average_precision"]),
                    "precision": validation_metrics["precision"],
                    "recall": validation_metrics["recall"],
                    "f1": validation_metrics["f1"],
                    "f2": validation_metrics["f2"],
                    "true_negative": int(validation_metrics["true_negative"]),
                    "false_positive": int(validation_metrics["false_positive"]),
                    "false_negative": int(validation_metrics["false_negative"]),
                    "true_positive": int(validation_metrics["true_positive"]),
                    "mlflow_run_id": (candidate_run.info.run_id),
                    "model_uri": (candidate_model_info.model_uri),
                }
            )

    # ------------------------------------------------------------------------
    # Select candidate using validation Average Precision first,
    # then validation F2 as tie-breaker.
    # ------------------------------------------------------------------------

    best_model_name = max(
        candidate_results,
        key=lambda name: (
            candidate_results[name]["validation_metrics"]["average_precision"],
            candidate_results[name]["validation_metrics"]["f2"],
        ),
    )

    best_threshold = float(candidate_results[best_model_name]["threshold"])

    # ------------------------------------------------------------------------
    # Refit selected model using Train + Validation.
    #
    # Test remains completely untouched until this point.
    # ------------------------------------------------------------------------

    train_validation_pdf = pd.concat(
        [
            train_pdf,
            validation_pdf,
        ],
        ignore_index=True,
    )

    X_train_validation = feature_matrix(train_validation_pdf)

    y_train_validation = train_validation_pdf[LABEL_COLUMN].astype(int)

    final_model = models[best_model_name]

    final_model.fit(
        X_train_validation,
        y_train_validation,
    )

    test_probability = final_model.predict_proba(X_test)[
        :,
        1,
    ]

    test_metrics = classification_metrics(
        y_test,
        test_probability,
        best_threshold,
    )

    test_predictions = (test_probability >= best_threshold).astype(int)

    mlflow.log_param(
        "selected_model",
        best_model_name,
    )

    mlflow.log_param(
        "selected_threshold",
        best_threshold,
    )

    mlflow.log_metrics({f"test_{key}": value for key, value in test_metrics.items()})

    final_signature = infer_signature(
        X_train_validation,
        final_model.predict_proba(X_train_validation)[
            :,
            1,
        ],
    )

    final_model_info = mlflow.sklearn.log_model(
        final_model,
        name="best_fraud_model",
        signature=final_signature,
        input_example=(X_train_validation.head(5)),
        serialization_format="cloudpickle",
    )

    mlflow.log_dict(
        {
            "selected_model": (best_model_name),
            "decision_threshold": (best_threshold),
            "test_metrics": (test_metrics),
            "feature_columns": (FEATURE_COLUMNS),
        },
        "evaluation/final_summary.json",
    )

    evaluation_results.append(
        {
            "model_name": best_model_name,
            "evaluation_split": "test",
            "is_selected_model": True,
            "decision_threshold": (best_threshold),
            "roc_auc": test_metrics["roc_auc"],
            "pr_auc": test_metrics["pr_auc"],
            "average_precision": (test_metrics["average_precision"]),
            "precision": test_metrics["precision"],
            "recall": test_metrics["recall"],
            "f1": test_metrics["f1"],
            "f2": test_metrics["f2"],
            "true_negative": int(test_metrics["true_negative"]),
            "false_positive": int(test_metrics["false_positive"]),
            "false_negative": int(test_metrics["false_negative"]),
            "true_positive": int(test_metrics["true_positive"]),
            "mlflow_run_id": (parent_run.info.run_id),
            "model_uri": (final_model_info.model_uri),
        }
    )


# COMMAND ----------
# Persist governed evaluation results.

evaluation_pdf = pd.DataFrame(evaluation_results)


(
    spark_session.createDataFrame(evaluation_pdf)
    .write.mode("overwrite")
    .option(
        "overwriteSchema",
        "true",
    )
    .saveAsTable(EVALUATION_TABLE)
)


# COMMAND ----------
# Persist untouched test-set predictions.

prediction_pdf = test_pdf[
    [
        "transaction_id",
        "event_timestamp",
        LABEL_COLUMN,
    ]
].copy()


prediction_pdf["fraud_probability"] = test_probability


prediction_pdf["predicted_fraud"] = test_predictions


prediction_pdf["decision_threshold"] = best_threshold


prediction_pdf["model_name"] = best_model_name


prediction_pdf["mlflow_run_id"] = parent_run.info.run_id


prediction_pdf["model_uri"] = final_model_info.model_uri


(
    spark_session.createDataFrame(prediction_pdf)
    .write.mode("overwrite")
    .option(
        "overwriteSchema",
        "true",
    )
    .saveAsTable(PREDICTION_TABLE)
)


# COMMAND ----------
# Output useful demo information.

print(
    json.dumps(
        {
            "selected_model": (best_model_name),
            "selected_threshold": (best_threshold),
            "test_metrics": (test_metrics),
            "mlflow_run_id": (parent_run.info.run_id),
            "model_uri": (final_model_info.model_uri),
        },
        indent=2,
    )
)


display(spark_session.table(EVALUATION_TABLE))


display(spark_session.table(PREDICTION_TABLE).orderBy(F.desc("fraud_probability")))
