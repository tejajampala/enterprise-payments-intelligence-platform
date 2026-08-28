from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]

RESOURCE = ROOT / "bundle/resources/fraud_detection.yml"


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_fraud_bundle_resource_exists() -> None:
    assert RESOURCE.exists()


def test_fraud_training_job_exists() -> None:
    with RESOURCE.open(encoding="utf-8") as file:
        config = yaml.safe_load(file)

    assert "fraud_model_training" in config["resources"]["jobs"]


def test_training_notebook_exists() -> None:
    assert (ROOT / "notebooks/ml/08_train_fraud_model.py").exists()


def test_training_uses_temporal_split() -> None:
    source = _read("notebooks/ml/08_train_fraud_model.py")

    assert "event_timestamp" in source

    assert "row_count * 0.70" in source
    assert "row_count * 0.85" in source


def test_non_feature_columns_are_not_model_features() -> None:
    source = _read("notebooks/ml/08_train_fraud_model.py")

    feature_section = source.split(
        "FEATURE_COLUMNS =",
        maxsplit=1,
    )[1].split(
        "# COMMAND ----------",
        maxsplit=1,
    )[0]

    assert "transaction_id" not in feature_section

    assert "event_timestamp" not in feature_section

    assert "fraud_outcome" not in feature_section


def test_two_models_are_compared() -> None:
    source = _read("notebooks/ml/08_train_fraud_model.py")

    assert "LogisticRegression" in source

    assert "HistGradientBoostingClassifier" in source


def test_class_imbalance_is_handled() -> None:
    source = _read("notebooks/ml/08_train_fraud_model.py")

    assert 'class_weight="balanced"' in source


def test_validation_threshold_is_tuned() -> None:
    source = _read("notebooks/ml/08_train_fraud_model.py")

    assert "choose_threshold" in source

    assert "fbeta_score" in source


def test_fraud_metrics_are_present() -> None:
    source = _read("notebooks/ml/08_train_fraud_model.py")

    expected = [
        "roc_auc",
        "pr_auc",
        "average_precision",
        "precision",
        "recall",
        "f1",
        "f2",
    ]

    for metric in expected:
        assert metric in source


def test_mlflow_tracking_is_used() -> None:
    source = _read("notebooks/ml/08_train_fraud_model.py")

    assert "mlflow.set_experiment" in source

    assert "mlflow.start_run" in source

    assert "mlflow.sklearn.log_model" in source


def test_registry_is_not_used_yet() -> None:
    source = _read("notebooks/ml/08_train_fraud_model.py")

    assert "registered_model_name" not in source


def test_evaluation_outputs_are_persisted() -> None:
    source = _read("notebooks/ml/08_train_fraud_model.py")

    assert "fraud_model_evaluation" in source

    assert "fraud_test_predictions" in source
