from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_data_quality_rules_module_exists() -> None:
    assert (ROOT / "pipelines/silver/dq_rules.py").exists()


def test_payment_quality_pipeline_exists() -> None:
    assert (ROOT / "pipelines/silver/payment_quality.py").exists()


def test_payment_event_rules_are_defined() -> None:
    source = _read("pipelines/silver/dq_rules.py")

    expected_rules = [
        "event_id_present",
        "transaction_id_present",
        "sequence_number_positive",
        "amount_positive",
        "currency_code_valid",
        "event_type_valid",
        "payload_parsed",
        "kafka_lineage_present",
    ]

    for rule in expected_rules:
        assert rule in source


def test_payment_transaction_rules_are_defined() -> None:
    source = _read("pipelines/silver/dq_rules.py")

    expected_rules = [
        "transaction_id_present",
        "account_id_present",
        "merchant_id_present",
        "amount_positive",
        "channel_valid",
        "payment_method_valid",
        "transaction_status_valid",
    ]

    for rule in expected_rules:
        assert rule in source


def test_quality_pipeline_uses_expectations() -> None:
    source = _read("pipelines/silver/payment_quality.py")

    assert "@dp.expect_all(PAYMENT_EVENT_RULES)" in source

    assert "@dp.expect_all(PAYMENT_TRANSACTION_RULES)" in source


def test_quality_pipeline_has_private_classification_tables() -> None:
    source = _read("pipelines/silver/payment_quality.py")

    assert 'name="payment_events_dq_classified"' in source
    assert 'name="payment_transactions_dq_classified"' in source

    assert source.count("private=True") == 2


def test_quality_pipeline_has_validated_tables() -> None:
    source = _read("pipelines/silver/payment_quality.py")

    assert 'name="payment_events_validated"' in source
    assert 'name="payment_transactions_validated"' in source


def test_quality_pipeline_has_quarantine_tables() -> None:
    source = _read("pipelines/silver/payment_quality.py")

    assert 'name="payment_events_quarantine"' in source
    assert 'name="payment_transactions_quarantine"' in source


def test_validated_transactions_enable_change_tracking() -> None:
    source = _read("pipelines/silver/payment_quality.py")

    assert '"delta.enableRowTracking": "true"' in source
    assert '"delta.enableChangeDataFeed": "true"' in source


def test_enrichment_reads_validated_transactions() -> None:
    source = _read("pipelines/silver/payment_transactions_enriched.py")

    assert 'spark.read.table("payment_transactions_validated")' in source


def test_dimension_expectations_are_defined() -> None:
    source = _read("pipelines/silver/reference_dimensions.py")

    expected = [
        "@dp.expect_all(CUSTOMER_RULES)",
        "@dp.expect_all(ACCOUNT_RULES)",
        "@dp.expect_all(MERCHANT_RULES)",
        "@dp.expect_all(FRAUD_CASE_RULES)",
    ]

    for expectation in expected:
        assert expectation in source
