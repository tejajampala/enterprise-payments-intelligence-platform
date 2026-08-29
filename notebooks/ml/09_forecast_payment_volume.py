# Databricks notebook source

"""Milestone 9 — Daily payment-volume forecasting.

Implements:

- continuous daily time-series preparation
- calendar features
- lag features
- rolling historical features
- seasonal-naive forecasting baseline
- Ridge regression
- HistGradientBoostingRegressor
- temporal train / validation / test evaluation
- recursive multi-step forecasting
- MLflow experiment tracking
- governed forecast and evaluation Delta tables

Production deployment and scheduled model promotion remain Milestone 10.
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
from sklearn.base import clone
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
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
    "/Shared/epip-dev-payment-volume-forecasting",
)

dbutils.widgets.text(
    "forecast_horizon_days",
    "7",
)

dbutils.widgets.text(
    "random_seed",
    "42",
)


CATALOG = dbutils.widgets.get("catalog_name")

EXPERIMENT_NAME = dbutils.widgets.get("experiment_name")

REQUESTED_FORECAST_HORIZON = int(dbutils.widgets.get("forecast_horizon_days"))

RANDOM_SEED = int(dbutils.widgets.get("random_seed"))


SOURCE_TABLE = f"{CATALOG}.gold.daily_payment_metrics"

EVALUATION_TABLE = f"{CATALOG}.ml.payment_volume_forecast_evaluation"

FORECAST_TABLE = f"{CATALOG}.ml.payment_volume_forecast"


TARGET_COLUMN = "transaction_count"


# COMMAND ----------
# Prepare one enterprise-wide daily transaction-volume time series.

daily_spark = (
    spark_session.table(SOURCE_TABLE)
    .groupBy("event_date")
    .agg(
        F.sum("transaction_count").alias(TARGET_COLUMN),
        F.round(
            F.sum("total_payment_amount"),
            2,
        ).alias("total_payment_amount"),
    )
    .orderBy("event_date")
)


daily_pdf = daily_spark.toPandas()


if daily_pdf.empty:
    raise ValueError("Gold payment metrics contain no data")


daily_pdf["event_date"] = pd.to_datetime(daily_pdf["event_date"])


daily_pdf = daily_pdf.set_index("event_date").sort_index()


# COMMAND ----------
# Build a complete calendar.
#
# A missing day is different from a missing observation.
# For this synthetic payment platform, no Gold row means zero payments that day.

calendar = pd.date_range(
    start=daily_pdf.index.min(),
    end=daily_pdf.index.max(),
    freq="D",
)


daily_pdf = daily_pdf.reindex(calendar)


daily_pdf.index.name = "event_date"


daily_pdf[TARGET_COLUMN] = daily_pdf[TARGET_COLUMN].fillna(0).astype(float)


daily_pdf["total_payment_amount"] = daily_pdf["total_payment_amount"].fillna(0.0).astype(float)


daily_pdf = daily_pdf.reset_index()


# COMMAND ----------
# We require enough history to demonstrate an actual temporal forecasting
# workflow rather than random regression.

if len(daily_pdf) < 21:
    raise ValueError("At least 21 calendar days are required for payment-volume forecasting")


# Lag 7 is always present because it provides the seasonal-naive baseline.

LAGS = [
    1,
    2,
    3,
    7,
]


ROLLING_WINDOWS = [
    3,
    7,
]


# Add longer-term features if sufficient history exists.

if len(daily_pdf) >= 35:
    LAGS.append(14)

    ROLLING_WINDOWS.append(14)


# COMMAND ----------
# Feature engineering.


def build_supervised_features(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """Convert the time series into a leakage-safe supervised dataset."""

    result = dataframe.copy().sort_values("event_date").reset_index(drop=True)

    result["day_of_week"] = result["event_date"].dt.dayofweek

    result["day_of_month"] = result["event_date"].dt.day

    result["month"] = result["event_date"].dt.month

    result["is_weekend"] = (result["day_of_week"] >= 5).astype(int)

    result["day_of_week_sin"] = np.sin(2 * np.pi * result["day_of_week"] / 7)

    result["day_of_week_cos"] = np.cos(2 * np.pi * result["day_of_week"] / 7)

    for lag in LAGS:
        result[f"lag_{lag}"] = result[TARGET_COLUMN].shift(lag)

    for window in ROLLING_WINDOWS:
        prior_values = result[TARGET_COLUMN].shift(1)

        result[f"rolling_mean_{window}"] = prior_values.rolling(
            window=window,
            min_periods=1,
        ).mean()

        result[f"rolling_std_{window}"] = (
            prior_values.rolling(
                window=window,
                min_periods=2,
            )
            .std()
            .fillna(0.0)
        )

    lag_columns = [f"lag_{lag}" for lag in LAGS]

    return result.dropna(subset=lag_columns).reset_index(drop=True)


supervised_pdf = build_supervised_features(daily_pdf)


CALENDAR_COLUMNS = [
    "day_of_week",
    "day_of_month",
    "month",
    "is_weekend",
    "day_of_week_sin",
    "day_of_week_cos",
]


LAG_COLUMNS = [f"lag_{lag}" for lag in LAGS]


ROLLING_COLUMNS = [
    feature
    for window in ROLLING_WINDOWS
    for feature in [
        f"rolling_mean_{window}",
        f"rolling_std_{window}",
    ]
]


FEATURE_COLUMNS = CALENDAR_COLUMNS + LAG_COLUMNS + ROLLING_COLUMNS


# COMMAND ----------
# Choose temporal holdout lengths dynamically.
#
# With short synthetic history, a 7-day holdout is more sensible than forcing
# a 14-day horizon with very little training data.

available_rows = len(supervised_pdf)


horizon = min(
    REQUESTED_FORECAST_HORIZON,
    max(
        3,
        available_rows // 5,
    ),
)


if available_rows - (2 * horizon) < 7:
    raise ValueError("Insufficient supervised history for train, validation and test periods")


train_end = available_rows - (2 * horizon)


validation_end = available_rows - horizon


train_pdf = supervised_pdf.iloc[:train_end].copy()


validation_pdf = supervised_pdf.iloc[train_end:validation_end].copy()


test_pdf = supervised_pdf.iloc[validation_end:].copy()


train_cutoff = train_pdf["event_date"].max()


validation_cutoff = validation_pdf["event_date"].max()


# COMMAND ----------
# Model matrices.


def model_matrix(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """Return numeric forecasting model features."""

    return (
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


X_train = model_matrix(train_pdf)


y_train = train_pdf[TARGET_COLUMN].astype(float)


# COMMAND ----------
# Evaluation metrics.


def forecast_metrics(
    actual: np.ndarray,
    predicted: np.ndarray,
) -> dict[str, float]:
    """Return business-oriented regression forecasting metrics."""

    actual_values = np.asarray(
        actual,
        dtype=float,
    )

    predicted_values = np.asarray(
        predicted,
        dtype=float,
    )

    absolute_error = np.abs(actual_values - predicted_values)

    mae = mean_absolute_error(
        actual_values,
        predicted_values,
    )

    rmse = np.sqrt(
        mean_squared_error(
            actual_values,
            predicted_values,
        )
    )

    actual_total = np.sum(np.abs(actual_values))

    wape = np.sum(absolute_error) / actual_total if actual_total > 0 else 0.0

    denominator = np.abs(actual_values) + np.abs(predicted_values)

    smape = np.mean(
        np.where(
            denominator == 0,
            0.0,
            (2 * absolute_error / denominator),
        )
    )

    bias = np.mean(predicted_values - actual_values)

    return {
        "mae": float(mae),
        "rmse": float(rmse),
        "wape": float(wape),
        "smape": float(smape),
        "bias": float(bias),
    }


# COMMAND ----------
# Recursive feature generation.
#
# Future lag values do not exist, so each forecast is added to history and
# becomes available to later forecast steps.


def build_future_feature_row(
    history: pd.Series,
    forecast_date: pd.Timestamp,
) -> pd.DataFrame:
    """Build one future feature row using only prior actual/predicted values."""

    row: dict[str, float] = {}

    day_of_week = forecast_date.dayofweek

    row["day_of_week"] = float(day_of_week)

    row["day_of_month"] = float(forecast_date.day)

    row["month"] = float(forecast_date.month)

    row["is_weekend"] = float(day_of_week >= 5)

    row["day_of_week_sin"] = float(np.sin(2 * np.pi * day_of_week / 7))

    row["day_of_week_cos"] = float(np.cos(2 * np.pi * day_of_week / 7))

    for lag in LAGS:
        lookup_date = forecast_date - pd.Timedelta(days=lag)

        if lookup_date not in history.index:
            raise ValueError(f"Missing history for lag {lag} at {forecast_date}")

        row[f"lag_{lag}"] = float(history.loc[lookup_date])

    previous_history = history[history.index < forecast_date]

    for window in ROLLING_WINDOWS:
        values = previous_history.tail(window)

        row[f"rolling_mean_{window}"] = float(values.mean())

        row[f"rolling_std_{window}"] = float(values.std() if len(values) > 1 else 0.0)

    return pd.DataFrame(
        [row],
        columns=FEATURE_COLUMNS,
    )


def recursive_forecast(
    model: Any | None,
    history: pd.Series,
    start_date: pd.Timestamp,
    forecast_days: int,
    method_name: str,
) -> pd.DataFrame:
    """Generate a recursive multi-day forecast."""

    working_history = history.copy().sort_index()

    predictions: list[dict[str, Any]] = []

    for offset in range(forecast_days):
        forecast_date = start_date + pd.Timedelta(days=offset)

        if method_name == "seasonal_naive_7d":
            seasonal_date = forecast_date - pd.Timedelta(days=7)

            prediction = float(working_history.loc[seasonal_date])

        else:
            if model is None:
                raise ValueError(f"A model is required for {method_name}")

            feature_row = build_future_feature_row(
                working_history,
                forecast_date,
            )

            prediction = float(model.predict(feature_row)[0])

        prediction = max(
            0.0,
            prediction,
        )

        working_history.loc[forecast_date] = prediction

        predictions.append(
            {
                "forecast_date": (forecast_date),
                "forecast_transaction_count": (prediction),
            }
        )

    return pd.DataFrame(predictions)


# COMMAND ----------
# Full actual historical series used for recursive validation.

actual_history = daily_pdf.set_index("event_date")[TARGET_COLUMN].astype(float)


# COMMAND ----------
# Candidate models.

candidate_models: dict[
    str,
    Any,
] = {
    "ridge_regression": (
        Pipeline(
            steps=[
                (
                    "scale",
                    StandardScaler(),
                ),
                (
                    "model",
                    Ridge(
                        alpha=1.0,
                    ),
                ),
            ]
        )
    ),
    "hist_gradient_boosting": (
        HistGradientBoostingRegressor(
            loss="poisson",
            learning_rate=0.05,
            max_iter=250,
            max_leaf_nodes=15,
            min_samples_leaf=5,
            l2_regularization=1.0,
            random_state=RANDOM_SEED,
        )
    ),
}


# COMMAND ----------
# MLflow experiment.

mlflow.set_tracking_uri("databricks")

mlflow.set_experiment(EXPERIMENT_NAME)


evaluation_results: list[dict[str, Any]] = []


validation_results: dict[str, dict[str, Any]] = {}


# COMMAND ----------
# Validation comparison.

with mlflow.start_run(run_name="payment-volume-forecast-comparison") as parent_run:
    parent_run_id = parent_run.info.run_id

    mlflow.set_tags(
        {
            "project": ("enterprise-payments-intelligence-platform"),
            "milestone": "9",
            "use_case": ("payment_volume_forecasting"),
            "evaluation_strategy": ("temporal_recursive_holdout"),
        }
    )

    mlflow.log_params(
        {
            "source_table": SOURCE_TABLE,
            "target_column": TARGET_COLUMN,
            "forecast_horizon_days": (horizon),
            "requested_forecast_horizon": (REQUESTED_FORECAST_HORIZON),
            "lag_features": (",".join(str(value) for value in LAGS)),
            "rolling_windows": (",".join(str(value) for value in ROLLING_WINDOWS)),
            "training_rows": (len(train_pdf)),
            "validation_rows": (len(validation_pdf)),
            "test_rows": (len(test_pdf)),
        }
    )

    # ------------------------------------------------------------------------
    # Seasonal-naive baseline.
    # ------------------------------------------------------------------------

    baseline_history = actual_history[actual_history.index <= train_cutoff]

    baseline_validation = recursive_forecast(
        model=None,
        history=baseline_history,
        start_date=(validation_pdf["event_date"].min()),
        forecast_days=horizon,
        method_name=("seasonal_naive_7d"),
    )

    baseline_metrics = forecast_metrics(
        validation_pdf[TARGET_COLUMN].to_numpy(),
        baseline_validation["forecast_transaction_count"].to_numpy(),
    )

    validation_results["seasonal_naive_7d"] = {
        "metrics": (baseline_metrics),
        "model_uri": "",
    }

    evaluation_results.append(
        {
            "method_name": ("seasonal_naive_7d"),
            "evaluation_split": ("validation"),
            "is_selected_method": (False),
            **baseline_metrics,
            "mlflow_run_id": (parent_run_id),
            "model_uri": "",
        }
    )

    # ------------------------------------------------------------------------
    # ML candidates.
    # ------------------------------------------------------------------------

    for (
        model_name,
        model_template,
    ) in candidate_models.items():
        with mlflow.start_run(
            run_name=model_name,
            nested=True,
        ) as candidate_run:
            model = clone(model_template)

            model.fit(
                X_train,
                y_train,
            )

            validation_history = actual_history[actual_history.index <= train_cutoff]

            validation_forecast = recursive_forecast(
                model=model,
                history=(validation_history),
                start_date=(validation_pdf["event_date"].min()),
                forecast_days=horizon,
                method_name=model_name,
            )

            metrics = forecast_metrics(
                validation_pdf[TARGET_COLUMN].to_numpy(),
                validation_forecast["forecast_transaction_count"].to_numpy(),
            )

            signature = infer_signature(
                X_train,
                model.predict(X_train),
            )

            model_info = mlflow.sklearn.log_model(
                model,
                name=("candidate_forecaster"),
                signature=signature,
                input_example=(X_train.head(5)),
            )

            mlflow.log_param(
                "model_name",
                model_name,
            )

            mlflow.log_metrics(
                {
                    f"validation_{key}": (value)
                    for (
                        key,
                        value,
                    ) in metrics.items()
                }
            )

            validation_results[model_name] = {
                "metrics": metrics,
                "model_uri": (model_info.model_uri),
            }

            evaluation_results.append(
                {
                    "method_name": (model_name),
                    "evaluation_split": ("validation"),
                    "is_selected_method": (False),
                    **metrics,
                    "mlflow_run_id": (candidate_run.info.run_id),
                    "model_uri": (model_info.model_uri),
                }
            )

    # ------------------------------------------------------------------------
    # Select by validation MAE, with RMSE as tie-breaker.
    #
    # The baseline is allowed to win. That is an important forecasting
    # discipline: a complex model must demonstrate value over a naive baseline.
    # ------------------------------------------------------------------------

    selected_method = min(
        validation_results,
        key=lambda method: (
            validation_results[method]["metrics"]["mae"],
            validation_results[method]["metrics"]["rmse"],
        ),
    )

    mlflow.log_param(
        "selected_method",
        selected_method,
    )

    # ------------------------------------------------------------------------
    # Untouched test evaluation.
    # ------------------------------------------------------------------------

    train_validation_pdf = supervised_pdf[supervised_pdf["event_date"] <= validation_cutoff].copy()

    test_history = actual_history[actual_history.index <= validation_cutoff]

    if selected_method == "seasonal_naive_7d":
        test_model = None

    else:
        test_model = clone(candidate_models[selected_method])

        test_model.fit(
            model_matrix(train_validation_pdf),
            train_validation_pdf[TARGET_COLUMN].astype(float),
        )

    test_forecast = recursive_forecast(
        model=test_model,
        history=test_history,
        start_date=(test_pdf["event_date"].min()),
        forecast_days=horizon,
        method_name=(selected_method),
    )

    test_metrics = forecast_metrics(
        test_pdf[TARGET_COLUMN].to_numpy(),
        test_forecast["forecast_transaction_count"].to_numpy(),
    )

    mlflow.log_metrics(
        {
            f"test_{key}": value
            for (
                key,
                value,
            ) in test_metrics.items()
        }
    )

    # ------------------------------------------------------------------------
    # Refit using all available historical observations after the untouched
    # test metrics have been calculated.
    # ------------------------------------------------------------------------

    final_model = None
    final_model_uri = ""

    if selected_method != "seasonal_naive_7d":
        final_model = clone(candidate_models[selected_method])

        final_model.fit(
            model_matrix(supervised_pdf),
            supervised_pdf[TARGET_COLUMN].astype(float),
        )

        final_signature = infer_signature(
            model_matrix(supervised_pdf),
            final_model.predict(model_matrix(supervised_pdf)),
        )

        final_model_info = mlflow.sklearn.log_model(
            final_model,
            name=("best_payment_volume_forecaster"),
            signature=(final_signature),
            input_example=(model_matrix(supervised_pdf).head(5)),
        )

        final_model_uri = final_model_info.model_uri

    evaluation_results.append(
        {
            "method_name": (selected_method),
            "evaluation_split": ("test"),
            "is_selected_method": (True),
            **test_metrics,
            "mlflow_run_id": (parent_run_id),
            "model_uri": (final_model_uri),
        }
    )

    # ------------------------------------------------------------------------
    # Future forecast.
    # ------------------------------------------------------------------------

    future_start_date = actual_history.index.max() + pd.Timedelta(days=1)

    future_forecast = recursive_forecast(
        model=final_model,
        history=actual_history,
        start_date=(future_start_date),
        forecast_days=(REQUESTED_FORECAST_HORIZON),
        method_name=(selected_method),
    )

    future_forecast["selected_method"] = selected_method

    future_forecast["mlflow_run_id"] = parent_run_id

    future_forecast["model_uri"] = final_model_uri

    mlflow.log_dict(
        {
            "selected_method": (selected_method),
            "validation_metrics": (validation_results[selected_method]["metrics"]),
            "test_metrics": (test_metrics),
            "future_horizon_days": (REQUESTED_FORECAST_HORIZON),
            "feature_columns": (FEATURE_COLUMNS),
        },
        "evaluation/forecast_summary.json",
    )


# COMMAND ----------
# Persist evaluation results.

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
# Persist future forecasts.

forecast_spark = spark_session.createDataFrame(future_forecast).withColumn(
    "generated_at",
    F.current_timestamp(),
)


(
    forecast_spark.write.mode("overwrite")
    .option(
        "overwriteSchema",
        "true",
    )
    .saveAsTable(FORECAST_TABLE)
)


# COMMAND ----------
# Demo output.

print(
    json.dumps(
        {
            "selected_method": (selected_method),
            "validation_metrics": (validation_results[selected_method]["metrics"]),
            "test_metrics": (test_metrics),
            "forecast_horizon_days": (REQUESTED_FORECAST_HORIZON),
            "mlflow_run_id": (parent_run_id),
            "model_uri": (final_model_uri),
        },
        indent=2,
    )
)


display(spark_session.table(EVALUATION_TABLE))


display(spark_session.table(FORECAST_TABLE).orderBy("forecast_date"))
