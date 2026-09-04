from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

PIPELINE_HEALTH_SQL = ROOT / "sql" / "monitoring" / "17_pipeline_operational_health.sql"
DQ_HEALTH_SQL = ROOT / "sql" / "monitoring" / "17_data_quality_health.sql"
FRESHNESS_SQL = ROOT / "sql" / "monitoring" / "17_data_freshness.sql"
VALIDATION_SQL = ROOT / "sql" / "monitoring" / "17_validate_pipeline_dq_monitoring.sql"
RUNBOOK = ROOT / "docs" / "demo" / "M17C-runbook.md"


def test_m17c_files_exist() -> None:
    for path in [
        PIPELINE_HEALTH_SQL,
        DQ_HEALTH_SQL,
        FRESHNESS_SQL,
        VALIDATION_SQL,
        RUNBOOK,
    ]:
        assert path.is_file()


def test_pipeline_health_preserves_never_run_pipelines() -> None:
    source = PIPELINE_HEALTH_SQL.read_text(encoding="utf-8")

    assert "current_epip_pipelines" in source
    assert "LEFT JOIN latest_update" in source
    assert "WHEN u.update_id IS NULL THEN 'NEVER_RUN'" in source
    assert "WHEN u.result_state = 'COMPLETED' THEN 'HEALTHY'" in source
    assert "WHEN u.result_state IN ('FAILED', 'CANCELED') THEN 'FAILED'" in source
    assert "WHEN u.result_state IS NULL THEN 'IN_PROGRESS'" in source


def test_pipeline_timeline_slices_are_aggregated() -> None:
    source = PIPELINE_HEALTH_SQL.read_text(encoding="utf-8")

    assert "system.lakeflow.pipeline_update_timeline" in source
    assert "t.update_id" in source
    assert "TIMESTAMPDIFF(" in source


def test_expectations_use_table_event_log_not_pipeline_uuid() -> None:
    source = DQ_HEALTH_SQL.read_text(encoding="utf-8")

    assert "event_log(" in source
    assert "TABLE(payments_dev.silver.payment_events_validated)" in source
    assert "data_quality.expectations" in source
    assert "passed_records" in source
    assert "failed_records" in source


def test_existing_quarantine_assets_are_reused() -> None:
    source = DQ_HEALTH_SQL.read_text(encoding="utf-8")

    assert "payments_dev.silver.payment_events_quarantine" in source
    assert "payments_dev.silver.payment_transactions_quarantine" in source
    assert "dq_failed_rules" in source
    assert "dq_checked_at" in source


def test_event_trust_anomalies_are_monitored() -> None:
    source = DQ_HEALTH_SQL.read_text(encoding="utf-8")

    assert "payments_dev.silver.payment_event_exceptions" in source
    assert "is_duplicate_event" in source
    assert "is_late_arrival" in source
    assert "is_out_of_order" in source


def test_freshness_uses_processing_time_not_only_business_time() -> None:
    source = FRESHNESS_SQL.read_text(encoding="utf-8")

    assert "latest_business_time" in source
    assert "latest_observed_at" in source
    assert "trusted_at" in source
    assert "dq_checked_at" in source
    assert "latest_silver_processed_at" in source

    for status in ["'RECENT'", "'AGING'", "'STALE'", "'NO_DATA'"]:
        assert status in source


def test_m17c_does_not_modify_upstream_dq_rules() -> None:
    combined = "\n".join(
        [
            PIPELINE_HEALTH_SQL.read_text(encoding="utf-8"),
            DQ_HEALTH_SQL.read_text(encoding="utf-8"),
            FRESHNESS_SQL.read_text(encoding="utf-8"),
        ]
    )

    assert "@dp.expect" not in combined
    assert "DROP TABLE" not in combined
    assert "DELETE FROM payments_dev.silver" not in combined


def test_m17c_has_no_hardcoded_pipeline_uuid() -> None:
    combined = "\n".join(
        [
            PIPELINE_HEALTH_SQL.read_text(encoding="utf-8"),
            DQ_HEALTH_SQL.read_text(encoding="utf-8"),
        ]
    )

    assert "<pipeline-id>" not in combined
    assert "pipeline_uuid" not in combined.lower()


def test_validation_exercises_all_m17c_views() -> None:
    source = VALIDATION_SQL.read_text(encoding="utf-8")

    for view in [
        "pipeline_operational_health",
        "lakeflow_expectation_metrics",
        "dq_quarantine_daily",
        "dq_quarantine_rule_metrics",
        "payment_event_exception_health",
        "data_freshness_health",
    ]:
        assert view in source


def test_current_dq_health_exposes_zero_quarantine_state() -> None:
    source = DQ_HEALTH_SQL.read_text(encoding="utf-8")

    assert "dq_current_health" in source
    assert "'payment_events'" in source
    assert "'payment_transactions'" in source
    assert "quarantined_records" in source
    assert "'HEALTHY'" in source
    assert "'ATTENTION'" in source
