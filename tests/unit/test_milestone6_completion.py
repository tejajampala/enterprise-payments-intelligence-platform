from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_milestone6_architecture_document_exists() -> None:
    assert (ROOT / "docs/architecture/milestone-6-data-trust.md").exists()


def test_milestone6_adr_exists() -> None:
    assert (ROOT / "docs/adr/0004-data-trust-and-auto-cdc-strategy.md").exists()


def test_milestone6_reconciliation_exists() -> None:
    assert (ROOT / "sql/reconciliation/06f_milestone6_reconciliation.sql").exists()


def test_data_quality_foundation_exists() -> None:
    quality = _read("pipelines/silver/payment_quality.py")

    assert "payment_events_validated" in quality
    assert "payment_events_quarantine" in quality

    assert "payment_transactions_validated" in quality
    assert "payment_transactions_quarantine" in quality


def test_streaming_trust_layer_exists() -> None:
    trust = _read("pipelines/silver/payment_event_trust.py")

    assert 'name="payment_events_trusted"' in trust

    assert ".dropDuplicatesWithinWatermark(" in trust

    assert '["event_id"]' in trust

    assert 'name="payment_event_exceptions"' in trust


def test_streaming_trust_detects_major_anomalies() -> None:
    trust = _read("pipelines/silver/payment_event_trust.py")

    expected = [
        "is_duplicate_event",
        "is_late_arrival",
        "is_out_of_order",
        '"DUPLICATE"',
        '"LATE"',
        '"OUT_OF_ORDER"',
    ]

    for value in expected:
        assert value in trust


def test_master_data_auto_cdc_exists() -> None:
    cdc = _read("pipelines/silver/master_data_cdc.py")

    assert cdc.count("dp.create_streaming_table(") == 6

    assert cdc.count("dp.create_auto_cdc_flow(") == 12


def test_snapshot_seed_auto_cdc_flows_are_once() -> None:
    cdc = _read("pipelines/silver/master_data_cdc.py")

    assert cdc.count("once=True") == 7


def test_auto_cdc_uses_business_sequence() -> None:
    cdc = _read("pipelines/silver/master_data_cdc.py")

    assert cdc.count('sequence_by="record_version"') == 12


def test_auto_cdc_supports_deletes() -> None:
    cdc = _read("pipelines/silver/master_data_cdc.py")

    assert "is_deleted = true" in cdc


def test_scd1_and_scd2_targets_exist() -> None:
    cdc = _read("pipelines/silver/master_data_cdc.py")

    expected = [
        "customers_current",
        "customer_history",
        "accounts_current",
        "account_history",
        "merchants_current",
        "merchant_history",
    ]

    for dataset in expected:
        assert dataset in cdc


def test_enrichment_uses_validated_transactions() -> None:
    enriched = _read("pipelines/silver/payment_transactions_enriched.py")

    assert "payment_transactions_validated" in enriched


def test_enrichment_uses_auto_cdc_current_dimensions() -> None:
    enriched = _read("pipelines/silver/payment_transactions_enriched.py")

    expected = [
        "customers_current",
        "accounts_current",
        "merchants_current",
    ]

    for dataset in expected:
        assert dataset in enriched


def test_final_reconciliation_covers_all_trust_layers() -> None:
    reconciliation = _read("sql/reconciliation/06f_milestone6_reconciliation.sql")

    expected = [
        "payment_events_quarantine",
        "payment_events_trusted",
        "payment_event_exceptions",
        "payment_transactions_quarantine",
        "customer_history",
        "account_history",
        "merchant_history",
        "payment_transactions_enriched",
        "daily_payment_metrics",
        "fraud_operations_metrics",
    ]

    for dataset in expected:
        assert dataset in reconciliation
