from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]

RESOURCE = ROOT / "bundle/resources/payment_forecasting.yml"


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_forecasting_bundle_resource_exists() -> None:
    assert RESOURCE.exists()


def test_forecasting_job_exists() -> None:
    with RESOURCE.open(encoding="utf-8") as file:
        config = yaml.safe_load(file)

    assert "payment_volume_forecasting" in config["resources"]["jobs"]


def test_forecasting_notebook_exists() -> None:
    assert (ROOT / "notebooks/ml/09_forecast_payment_volume.py").exists()


def test_gold_metrics_are_forecasting_source() -> None:
    source = _read("notebooks/ml/09_forecast_payment_volume.py")

    assert "daily_payment_metrics" in source


def test_lag_features_are_used() -> None:
    source = _read("notebooks/ml/09_forecast_payment_volume.py")

    assert "LAGS = [" in source

    assert "7," in source

    assert 'f"lag_{lag}"' in source

    assert ".shift(" in source


def test_rolling_features_exclude_current_day() -> None:
    source = _read("notebooks/ml/09_forecast_payment_volume.py")

    assert ".shift(" in source

    assert "rolling_mean_" in source


def test_seasonal_naive_baseline_exists() -> None:
    source = _read("notebooks/ml/09_forecast_payment_volume.py")

    assert "seasonal_naive_7d" in source


def test_multiple_forecasting_models_are_compared() -> None:
    source = _read("notebooks/ml/09_forecast_payment_volume.py")

    assert "Ridge" in source

    assert "HistGradientBoostingRegressor" in source


def test_recursive_forecasting_is_used() -> None:
    source = _read("notebooks/ml/09_forecast_payment_volume.py")

    assert "recursive_forecast" in source


def test_temporal_validation_and_test_are_used() -> None:
    source = _read("notebooks/ml/09_forecast_payment_volume.py")

    assert "validation_pdf" in source
    assert "test_pdf" in source


def test_forecasting_metrics_are_present() -> None:
    source = _read("notebooks/ml/09_forecast_payment_volume.py")

    for metric in [
        "mae",
        "rmse",
        "wape",
        "smape",
        "bias",
    ]:
        assert metric in source


def test_mlflow_tracking_is_used() -> None:
    source = _read("notebooks/ml/09_forecast_payment_volume.py")

    assert "mlflow.set_experiment" in source

    assert "mlflow.start_run" in source


def test_forecast_outputs_are_persisted() -> None:
    source = _read("notebooks/ml/09_forecast_payment_volume.py")

    assert "payment_volume_forecast_evaluation" in source

    assert "payment_volume_forecast" in source
