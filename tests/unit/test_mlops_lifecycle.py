from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]

RESOURCE = ROOT / "bundle/resources/mlops.yml"


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_mlops_bundle_exists() -> None:
    assert RESOURCE.exists()


def test_model_registry_schema_exists() -> None:
    with RESOURCE.open(encoding="utf-8") as file:
        config = yaml.safe_load(file)

    assert "model_registry_schema" in config["resources"]["schemas"]


def test_mlops_job_has_three_tasks() -> None:
    with RESOURCE.open(encoding="utf-8") as file:
        config = yaml.safe_load(file)

    job = config["resources"]["jobs"]["mlops_model_lifecycle"]

    task_keys = {task["task_key"] for task in job["tasks"]}

    assert task_keys == {
        "register_and_promote_models",
        "deploy_fraud_serving",
        "batch_score_fraud",
    }


def test_uc_registry_is_used() -> None:
    source = _read("notebooks/mlops/10_register_promote_models.py")

    assert 'set_registry_uri("databricks-uc")' in source


def test_custom_fraud_serving_wrapper_exists() -> None:
    source = _read("notebooks/mlops/10_register_promote_models.py")

    assert "class FraudServingModel" in source

    assert "predict_proba" in source

    assert "fraud_probability" in source

    assert "predicted_fraud" in source


def test_model_aliases_are_used() -> None:
    source = _read("notebooks/mlops/10_register_promote_models.py")

    assert '"Candidate"' in source
    assert '"Champion"' in source

    assert '"PreviousChampion"' in source


def test_fraud_quality_gate_exists() -> None:
    source = _read("notebooks/mlops/10_register_promote_models.py")

    assert "average_precision_beats_base_rate" in source

    assert "minimum_recall" in source


def test_forecasting_quality_gate_exists() -> None:
    source = _read("notebooks/mlops/10_register_promote_models.py")

    assert "wape_below_limit" in source


def test_serving_endpoint_scales_to_zero() -> None:
    source = _read("notebooks/mlops/10_deploy_fraud_serving.py")

    assert 'workload_size="Small"' in source

    assert "scale_to_zero_enabled=True" in source


def test_serving_uses_champion_version() -> None:
    source = _read("notebooks/mlops/10_deploy_fraud_serving.py")

    assert "get_model_version_by_alias" in source

    assert '"Champion"' in source


def test_serving_smoke_test_exists() -> None:
    source = _read("notebooks/mlops/10_deploy_fraud_serving.py")

    assert "serving_endpoints.query" in source


def test_batch_inference_uses_champion() -> None:
    source = _read("notebooks/mlops/10_batch_score_fraud.py")

    assert "@Champion" in source

    assert "fraud_batch_predictions" in source
