from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

BUNDLE_RESOURCE = ROOT / "bundle" / "resources" / "monitoring_observability.yml"
CREATE_SCHEMA_SQL = ROOT / "sql" / "monitoring" / "17_create_monitoring_schema.sql"
INVENTORY_SQL = ROOT / "sql" / "monitoring" / "17_system_table_inventory.sql"
FOUNDATION_SQL = ROOT / "sql" / "monitoring" / "17_platform_health_views.sql"
VALIDATION_SQL = ROOT / "sql" / "monitoring" / "17_validate_observability_foundation.sql"
ARCHITECTURE_DOC = ROOT / "docs" / "architecture" / "monitoring-cost-architecture.md"
RUNBOOK = ROOT / "docs" / "demo" / "M17B-runbook.md"


def test_monitoring_schema_is_bundle_managed() -> None:
    source = BUNDLE_RESOURCE.read_text(encoding="utf-8")

    assert "monitoring_schema:" in source
    assert "name: monitoring" in source
    assert "catalog_name: ${var.catalog_name}" in source


def test_foundation_system_tables_are_inventory_documented() -> None:
    source = INVENTORY_SQL.read_text(encoding="utf-8")

    required_sources = [
        "system.billing.usage",
        "system.billing.list_prices",
        "system.lakeflow.pipelines",
        "system.lakeflow.pipeline_update_timeline",
        "system.lakeflow.jobs",
        "system.lakeflow.job_run_timeline",
        "system.lakeflow.job_task_run_timeline",
        "system.query.history",
        "system.access.audit",
        "system.compute.warehouses",
        "system.compute.warehouse_events",
    ]

    for table in required_sources:
        assert table in source


def test_pipeline_scd2_is_resolved_correctly() -> None:
    source = FOUNDATION_SQL.read_text(encoding="utf-8")

    assert "system.lakeflow.pipelines" in source
    assert "PARTITION BY workspace_id, pipeline_id" in source
    assert "ORDER BY change_time DESC" in source
    assert "version_rank = 1" in source
    assert "delete_time IS NULL" in source


def test_job_scd2_is_resolved_correctly() -> None:
    source = FOUNDATION_SQL.read_text(encoding="utf-8")

    assert "system.lakeflow.jobs" in source
    assert "PARTITION BY workspace_id, job_id" in source
    assert "ORDER BY change_time DESC" in source
    assert "version_rank = 1" in source
    assert "delete_time IS NULL" in source


def test_timeline_views_normalize_hourly_slices() -> None:
    source = FOUNDATION_SQL.read_text(encoding="utf-8")

    assert "system.lakeflow.pipeline_update_timeline" in source
    assert "SUM(timeline.period_end_time - timeline.period_start_time)" in source
    assert "system.lakeflow.job_run_timeline" in source


def test_epip_assets_are_filtered_by_project_prefix() -> None:
    source = FOUNDATION_SQL.read_text(encoding="utf-8")

    assert source.count("LOWER(name) LIKE '%epip%'") >= 2


def test_foundation_does_not_hardcode_workspace_or_account_ids() -> None:
    combined = "\n".join(
        [
            FOUNDATION_SQL.read_text(encoding="utf-8"),
            INVENTORY_SQL.read_text(encoding="utf-8"),
            VALIDATION_SQL.read_text(encoding="utf-8"),
        ]
    )

    assert "7474647968455545" not in combined
    assert "f6539484-c223-4570-ac76-83eaf74283f5" not in combined


def test_m17b_does_not_calculate_cost_prematurely() -> None:
    source = FOUNDATION_SQL.read_text(encoding="utf-8")

    assert "list_cost" not in source
    assert "pricing.default" not in source
    assert "effective_list" not in source


def test_validation_covers_foundation_views() -> None:
    source = VALIDATION_SQL.read_text(encoding="utf-8")

    for view in [
        "current_epip_pipelines",
        "epip_pipeline_update_health",
        "current_epip_jobs",
        "epip_job_run_health",
        "system_source_readiness",
    ]:
        assert view in source


def test_m17b_documentation_exists() -> None:
    assert CREATE_SCHEMA_SQL.is_file()
    assert ARCHITECTURE_DOC.is_file()
    assert RUNBOOK.is_file()
