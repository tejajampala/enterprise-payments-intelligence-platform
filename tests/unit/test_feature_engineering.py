from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]

FEATURE_RESOURCE = ROOT / "bundle/resources/feature_engineering.yml"


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _load_feature_config() -> dict:
    with FEATURE_RESOURCE.open(encoding="utf-8") as file:
        return yaml.safe_load(file)


def test_feature_engineering_bundle_resource_exists() -> None:
    assert FEATURE_RESOURCE.exists()


def test_features_schema_is_declared() -> None:
    config = _load_feature_config()

    assert "features_schema" in config["resources"]["schemas"]


def test_feature_engineering_job_is_serverless() -> None:
    config = _load_feature_config()

    job = config["resources"]["jobs"]["feature_engineering"]

    task = job["tasks"][0]

    assert "new_cluster" not in task
    assert "existing_cluster_id" not in task


def test_feature_notebook_exists() -> None:
    assert (ROOT / "notebooks/features/07_build_fraud_features.py").exists()


def test_transaction_feature_table_exists_in_code() -> None:
    source = _read("notebooks/features/07_build_fraud_features.py")

    assert "transaction_fraud_features" in source

    assert "PRIMARY KEY (transaction_id)" in source


def test_customer_feature_table_is_timeseries() -> None:
    source = _read("notebooks/features/07_build_fraud_features.py")

    assert "customer_behavior_features" in source

    assert "feature_timestamp TIMESERIES" in source


def test_merchant_feature_table_is_timeseries() -> None:
    source = _read("notebooks/features/07_build_fraud_features.py")

    assert "merchant_behavior_features" in source


def test_behavior_windows_exclude_current_transaction() -> None:
    source = _read("notebooks/features/07_build_fraud_features.py")

    assert ".rangeBetween(" in source

    assert "-1," in source


def test_feature_store_client_is_used() -> None:
    source = _read("notebooks/features/07_build_fraud_features.py")

    assert "FeatureEngineeringClient" in source

    assert "FeatureLookup" in source

    assert "create_training_set" in source


def test_point_in_time_feature_lookup_is_used() -> None:
    source = _read("notebooks/features/07_build_fraud_features.py")

    assert 'timestamp_lookup_key="event_timestamp"' in source


def test_fraud_outcome_is_not_a_feature() -> None:
    source = _read("notebooks/features/07_build_fraud_features.py")

    transaction_feature_section = source.split(
        "transaction_feature_names =",
        maxsplit=1,
    )[1].split(
        "customer_feature_names =",
        maxsplit=1,
    )[0]

    assert "fraud_outcome" not in transaction_feature_section

    assert "has_fraud_case" not in transaction_feature_section


def test_training_dataset_is_persisted() -> None:
    source = _read("notebooks/features/07_build_fraud_features.py")

    assert "fraud_training_dataset" in source
