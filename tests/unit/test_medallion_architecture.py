from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]

MEDALLION_RESOURCE = ROOT / "bundle/resources/medallion_pipeline.yml"


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _load_medallion_config() -> dict:
    with MEDALLION_RESOURCE.open(encoding="utf-8") as file:
        return yaml.safe_load(file)


def test_medallion_resource_exists() -> None:
    assert MEDALLION_RESOURCE.exists()


def test_silver_pipeline_is_serverless_triggered() -> None:
    config = _load_medallion_config()

    pipeline = config["resources"]["pipelines"]["silver_transformations"]

    assert pipeline["serverless"] is True
    assert pipeline["continuous"] is False
    assert pipeline["development"] is True


def test_gold_pipeline_is_serverless_triggered() -> None:
    config = _load_medallion_config()

    pipeline = config["resources"]["pipelines"]["gold_analytics"]

    assert pipeline["serverless"] is True
    assert pipeline["continuous"] is False
    assert pipeline["development"] is True


def test_payment_events_are_streaming() -> None:
    source = _read("pipelines/silver/payment_events.py")

    assert "@dp.table" in source
    assert "spark.readStream.table" in source
    assert "payments_dev.bronze.payment_events" in source


def test_payment_transactions_are_streaming() -> None:
    source = _read("pipelines/silver/payment_transactions.py")

    assert "@dp.table" in source
    assert "@dp.materialized_view" not in source
    assert "spark.readStream.table" in source

    assert "payments_dev.ingestion.payment_transactions_batch_s3" in source


def test_payment_transactions_enable_change_tracking() -> None:
    source = _read("pipelines/silver/payment_transactions.py")

    assert '"delta.enableRowTracking": "true"' in source
    assert '"delta.enableChangeDataFeed": "true"' in source


def test_current_dimensions_are_materialized_views() -> None:
    source = _read("pipelines/silver/reference_dimensions.py")

    expected_datasets = [
        'name="customers_current"',
        'name="accounts_current"',
        'name="merchants_current"',
        'name="fraud_cases_current"',
    ]

    for dataset in expected_datasets:
        assert dataset in source

    assert source.count("@dp.materialized_view") == 4


def test_current_dimensions_enable_change_tracking() -> None:
    source = _read("pipelines/silver/reference_dimensions.py")

    assert source.count('"delta.enableRowTracking": "true"') == 4

    assert source.count('"delta.enableChangeDataFeed": "true"') == 4


def test_enriched_transactions_are_materialized_view() -> None:
    source = _read("pipelines/silver/payment_transactions_enriched.py")

    assert "@dp.materialized_view" in source
    assert 'name="payment_transactions_enriched"' in source

    assert source.count('"left"') == 4


def test_enriched_transactions_enable_change_tracking() -> None:
    source = _read("pipelines/silver/payment_transactions_enriched.py")

    assert '"delta.enableRowTracking": "true"' in source
    assert '"delta.enableChangeDataFeed": "true"' in source


def test_gold_business_metrics_are_materialized_views() -> None:
    source = _read("pipelines/gold/payment_metrics.py")

    expected_datasets = [
        'name="daily_payment_metrics"',
        'name="merchant_payment_metrics"',
        'name="channel_payment_metrics"',
        'name="fraud_operations_metrics"',
    ]

    for dataset in expected_datasets:
        assert dataset in source

    assert source.count("@dp.materialized_view") == 4


def test_gold_reads_enriched_silver() -> None:
    source = _read("pipelines/gold/payment_metrics.py")

    assert "payments_dev.silver.payment_transactions_enriched" in source


def test_snapshot_feature_migration_exists() -> None:
    source = _read("sql/medallion/05d_enable_incremental_refresh_features.sql")

    expected_tables = [
        "customers_snapshot",
        "accounts_snapshot",
        "merchants_snapshot",
        "fraud_cases_snapshot",
    ]

    for table in expected_tables:
        assert table in source

    assert source.count("delta.enableRowTracking") == 4
    assert source.count("delta.enableChangeDataFeed") == 4
