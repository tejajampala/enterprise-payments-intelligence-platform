# M17B — Observability Foundation Runbook

## 1. Branch

```powershell
git checkout main
git pull origin main
git checkout -b feature/m17b-observability-foundation
```

## 2. Add the M17B files

Expected files:

```text
bundle/resources/monitoring_observability.yml

sql/monitoring/17_create_monitoring_schema.sql
sql/monitoring/17_system_table_inventory.sql
sql/monitoring/17_platform_health_views.sql
sql/monitoring/17_validate_observability_foundation.sql

tests/unit/test_monitoring_contracts.py

docs/architecture/monitoring-cost-architecture.md
docs/demo/M17B-runbook.md
```

## 3. Validate the bundle resource

```powershell
databricks bundle validate -t dev -p PAYMENTS_DEV
```

The bundle should resolve:

```text
${var.catalog_name}.monitoring
```

to:

```text
payments_dev.monitoring
```

for the development target.

## 4. Deploy the development bundle

```powershell
databricks bundle deploy -t dev -p PAYMENTS_DEV
```

This creates/manages the monitoring schema resource.

## 5. Run the system inventory SQL

Execute:

```text
sql/monitoring/17_system_table_inventory.sql
```

This re-validates system-table access and source presence.

## 6. Create the foundation views

Execute:

```text
sql/monitoring/17_platform_health_views.sql
```

Expected views:

```text
payments_dev.monitoring.current_epip_pipelines
payments_dev.monitoring.epip_pipeline_update_health
payments_dev.monitoring.current_epip_jobs
payments_dev.monitoring.epip_job_run_health
payments_dev.monitoring.system_source_readiness
```

## 7. Validate

Execute:

```text
sql/monitoring/17_validate_observability_foundation.sql
```

Review:

- detected EPIP pipelines
- pipeline update result states
- detected EPIP jobs
- recent job run states
- source-readiness timestamps and counts

It is valid for a recent-history view to return zero rows when the relevant
workload has not run in the last 30 days.

## 8. Local quality gates

```powershell
uv run pytest tests/unit/test_monitoring_contracts.py -v
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv build
databricks bundle validate -t dev -p PAYMENTS_DEV
databricks bundle validate -t ci -p PAYMENTS_DEV
```

## 9. Commit

```powershell
git add .
git commit -m "feat(observability): add Databricks system-table foundation"
git push -u origin feature/m17b-observability-foundation
```

Suggested PR title:

```text
feat(observability): add Databricks system-table foundation
```

## 10. Do not start detailed cost logic yet

M17B only verifies billing-source readiness.

Detailed cost calculation and attribution belong to M17F, after the operational
monitoring contracts are established.
