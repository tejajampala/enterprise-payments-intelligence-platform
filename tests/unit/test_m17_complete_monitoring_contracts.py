import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

JOB_SQL = ROOT / "sql" / "monitoring" / "17_job_task_health.sql"
QUERY_SQL = ROOT / "sql" / "monitoring" / "17_query_warehouse_health.sql"
SECURITY_SQL = ROOT / "sql" / "monitoring" / "17_security_events.sql"
ML_AGENT_SQL = ROOT / "sql" / "monitoring" / "17_ml_agent_health.sql"
COST_SQL = ROOT / "sql" / "monitoring" / "17_cost_monitoring.sql"
SUMMARY_SQL = ROOT / "sql" / "monitoring" / "17_operations_summary.sql"
VALIDATION_SQL = ROOT / "sql" / "monitoring" / "17_validate_m17_complete.sql"

ROOT_BUNDLE = ROOT / "databricks.yml"
BUSINESS_DASHBOARD_RESOURCE = ROOT / "bundle" / "resources" / "epip_payments_intelligence.dashboard.yml"
OPS_DASHBOARD_RESOURCE = ROOT / "bundle" / "resources" / "epip_platform_operations.dashboard.yml"
ALERT_RESOURCE = ROOT / "bundle" / "resources" / "monitoring_alerts.yml"
OPS_DASHBOARD_JSON = ROOT / "src" / "analytics" / "epip_platform_operations.lvdash.json"

MONITORING_ARCHITECTURE = ROOT / "docs" / "architecture" / "monitoring-cost-architecture.md"
RUNBOOK = ROOT / "docs" / "demo" / "M17-runbook.md"

README = ROOT / "README.md"
PROJECT_STATUS = ROOT / "docs" / "PROJECT_STATUS.md"
PLATFORM_ARCHITECTURE = ROOT / "docs" / "architecture" / "platform-architecture.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_final_m17d_files_exist() -> None:
    for path in [
        JOB_SQL,
        QUERY_SQL,
        SECURITY_SQL,
        ML_AGENT_SQL,
        COST_SQL,
        SUMMARY_SQL,
        VALIDATION_SQL,
        ROOT_BUNDLE,
        BUSINESS_DASHBOARD_RESOURCE,
        OPS_DASHBOARD_RESOURCE,
        ALERT_RESOURCE,
        OPS_DASHBOARD_JSON,
        MONITORING_ARCHITECTURE,
        RUNBOOK,
        README,
        PROJECT_STATUS,
        PLATFORM_ARCHITECTURE,
    ]:
        assert path.is_file(), f"Missing M17D asset: {path}"


def test_job_monitoring_normalizes_scd2_and_timeline_runs() -> None:
    source = _read(JOB_SQL)

    assert "system.lakeflow.job_tasks" in source
    assert "ORDER BY change_time DESC" in source
    assert "delete_time IS NULL" in source

    assert "system.lakeflow.job_task_run_timeline" in source
    assert "TIMESTAMPDIFF(" in source
    assert "MAX_BY(" in source

    assert "job_operational_health" in source
    assert "WHEN run.run_id IS NULL THEN 'NEVER_RUN'" in source


def test_query_monitoring_includes_enterprise_performance_signals() -> None:
    source = _read(QUERY_SQL)

    for token in [
        "system.query.history",
        "waiting_for_compute_duration_ms",
        "waiting_at_capacity_duration_ms",
        "execution_duration_ms",
        "read_bytes",
        "pruned_files",
        "read_files",
        "spilled_local_bytes",
        "shuffle_read_bytes",
        "from_result_cache",
        "file_pruning_rate",
    ]:
        assert token in source


def test_query_monitoring_is_epip_scoped() -> None:
    source = _read(QUERY_SQL)

    assert "current_epip_pipelines" in source
    assert "current_epip_jobs" in source
    assert "attribution_method" in source
    assert "UNATTRIBUTED" in source


def test_security_monitoring_does_not_expose_source_ip() -> None:
    source = _read(SECURITY_SQL)

    assert "system.access.audit" in source
    assert "TO_JSON(audit.request_params)" in source
    assert "request_context" in source

    # request_params are used only for attribution and never selected from the
    # curated monitoring view. Source IP is intentionally never referenced.
    assert "audit.source_ip_address" not in source
    assert "source_ip_address" not in source


def test_ml_monitoring_uses_governed_scoring_evidence() -> None:
    source = _read(ML_AGENT_SQL)

    assert "payments_dev.analytics.fraud_model_operations_base" in source
    assert "model_version" in source
    assert "model_alias" in source
    assert "scored_at" in source
    assert "predicted_fraud_rate" in source
    assert "scoring_freshness_status" in source


def test_agent_monitoring_reuses_m13_evidence_and_trace_ids() -> None:
    source = _read(ML_AGENT_SQL)

    assert "payments_dev.ai.agent_evaluation_summary" in source
    assert "payments_dev.ai.agent_evaluation_results" in source

    for token in [
        "pass_rate",
        "avg_groundedness_score",
        "avg_evidence_completeness_score",
        "human_review_rate",
        "safety_rate",
        "failed_gates",
        "trace_id",
    ]:
        assert token in source


def test_cost_monitoring_handles_billing_corrections_correctly() -> None:
    source = _read(COST_SQL)

    assert "system.billing.usage" in source
    assert "system.billing.list_prices" in source
    assert "pricing.effective_list.default" in source

    # Billing corrections must be summed. Filtering to ORIGINAL would discard
    # RETRACTION/RESTATEMENT correction semantics.
    assert "record_type = 'ORIGINAL'" not in source
    assert 'record_type = "ORIGINAL"' not in source

    assert "estimated_list_cost" in source
    assert "databricks_cost_by_workload" in source


def test_cost_documentation_does_not_claim_complete_aws_cost() -> None:
    combined = "\n".join(
        [
            _read(COST_SQL),
            _read(MONITORING_ARCHITECTURE),
            _read(RUNBOOK),
        ]
    )

    assert "Amazon MSK" in combined
    assert "Amazon S3" in combined
    assert "complete AWS" in combined or "Complete AWS" in combined


def test_current_dq_health_has_explicit_zero_quarantine_state() -> None:
    source = _read(SUMMARY_SQL)

    assert "dq_current_health" in source
    assert "'payment_events'" in source
    assert "'payment_transactions'" in source
    assert "quarantined_records = 0" in source
    assert "THEN 'HEALTHY'" in source


def test_operations_summary_covers_cross_platform_domains() -> None:
    source = _read(SUMMARY_SQL)

    for token in [
        "failed_pipelines",
        "failed_jobs_24h",
        "failed_tasks_24h",
        "failed_queries_24h",
        "stale_or_missing_datasets",
        "dq_attention_datasets",
        "high_security_events_24h",
        "latest_agent_pass_rate",
        "fraud_scoring_age_hours",
        "databricks_list_cost_today",
    ]:
        assert token in source


def test_sql_warehouse_is_parameterized_in_bundle() -> None:
    assert "sql_warehouse_id:" in _read(ROOT_BUNDLE)

    for path in [
        BUSINESS_DASHBOARD_RESOURCE,
        OPS_DASHBOARD_RESOURCE,
        ALERT_RESOURCE,
    ]:
        assert "${var.sql_warehouse_id}" in _read(path)


def test_monitoring_alerts_are_cost_safe_and_paused() -> None:
    source = _read(ALERT_RESOURCE)

    for alert_key in [
        "epip_pipeline_failure:",
        "epip_data_freshness:",
        "epip_dq_degradation:",
        "epip_agent_regression:",
        "epip_cost_anomaly:",
    ]:
        assert alert_key in source

    assert source.count("pause_status: PAUSED") == 5
    assert source.count("warehouse_id: ${var.sql_warehouse_id}") == 5
    assert source.count("query_text:") == 5


def test_operations_dashboard_has_four_operational_pages() -> None:
    dashboard = json.loads(_read(OPS_DASHBOARD_JSON))

    page_names = {page["displayName"] for page in dashboard["pages"]}

    assert page_names == {
        "Platform Health",
        "Data Quality & Security",
        "ML & Agent Health",
        "Cost & Performance",
    }

    assert dashboard["datasets"]


def test_final_validation_queries_every_m17d_domain() -> None:
    source = _read(VALIDATION_SQL)

    for view in [
        "pipeline_operational_health",
        "dq_current_health",
        "data_freshness_health",
        "job_operational_health",
        "epip_job_task_run_health",
        "epip_query_performance",
        "warehouse_operational_health",
        "epip_security_events",
        "fraud_model_current_health",
        "agent_latest_health",
        "databricks_cost_daily",
        "cost_optimisation_candidates",
        "platform_operations_summary",
        "operations_alert_candidates",
    ]:
        assert view in source


def test_final_project_docs_mark_m17_complete() -> None:
    readme = _read(README)
    status = _read(PROJECT_STATUS)
    architecture = _read(PLATFORM_ARCHITECTURE)

    assert "Milestone 17: COMPLETE" in readme
    assert "M1–M17 COMPLETE" in readme

    assert "M17 | Monitoring, observability and cost optimisation | **COMPLETE**" in status
    assert "M1–M17 COMPLETE" in status

    assert "Completed: M1–M17" in architecture
    assert 'subgraph MON["7. OBSERVABILITY & COST"]' in architecture

    combined = "\n".join([readme, status, architecture])

    assert "Active Development" not in combined
    assert "Azure Portability" not in combined
    assert "| M18 |" not in combined


def test_dashboard_json_is_not_synced_as_workspace_file() -> None:
    source = _read(ROOT_BUNDLE)
    assert "src/analytics/*.lvdash.json" in source
