from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_master_data_cdc_pipeline_exists() -> None:
    assert (ROOT / "pipelines/silver/master_data_cdc.py").exists()


def test_auto_cdc_targets_exist() -> None:
    source = _read("pipelines/silver/master_data_cdc.py")

    expected = [
        "customers_current",
        "customer_history",
        "accounts_current",
        "account_history",
        "merchants_current",
        "merchant_history",
    ]

    for dataset in expected:
        assert dataset in source


def test_six_auto_cdc_targets_are_streaming_tables() -> None:
    source = _read("pipelines/silver/master_data_cdc.py")

    assert source.count("dp.create_streaming_table(") == 6


def test_snapshot_and_incremental_flows_exist() -> None:
    source = _read("pipelines/silver/master_data_cdc.py")

    assert source.count("dp.create_auto_cdc_flow(") == 12

    assert source.count("once=True") == 7


def test_scd1_and_scd2_are_both_used() -> None:
    source = _read("pipelines/silver/master_data_cdc.py")

    assert source.count("stored_as_scd_type=1") == 6

    assert source.count('stored_as_scd_type="2"') == 6


def test_record_version_controls_sequence() -> None:
    source = _read("pipelines/silver/master_data_cdc.py")

    assert source.count('sequence_by="record_version"') == 12


def test_auto_cdc_handles_deletes() -> None:
    source = _read("pipelines/silver/master_data_cdc.py")

    assert "is_deleted = true" in source


def test_cdc_sources_use_auto_loader() -> None:
    source = _read("pipelines/silver/master_data_cdc.py")

    assert '.format("cloudFiles")' in source

    assert "cloudFiles.includeExistingFiles" in source


def test_snapshot_high_water_mark_is_enforced() -> None:
    source = _read("pipelines/silver/master_data_cdc.py")

    assert "_snapshot_record_version" in source

    assert "c.record_version" in source


def test_cdc_data_quality_is_enforced() -> None:
    source = _read("pipelines/silver/master_data_cdc.py")

    assert "@dp.expect_all_or_drop(CUSTOMER_RULES)" in source

    assert "@dp.expect_all_or_drop(ACCOUNT_RULES)" in source

    assert "@dp.expect_all_or_drop(MERCHANT_RULES)" in source


def test_delete_tombstone_retention_is_configured() -> None:
    source = _read("pipelines/silver/master_data_cdc.py")

    assert "pipelines.cdc.tombstoneGCThresholdInSeconds" in source
