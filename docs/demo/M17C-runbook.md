# M17C — Lakeflow and Data Quality Monitoring Runbook

## Objective

M17C operationalizes Lakeflow and data-quality controls already implemented in EPIP.

It does not modify the M6 DQ rules.

```text
Current Lakeflow Pipelines
          +
Pipeline Update Timeline
          ↓
Operational Pipeline Health

Lakeflow Event Log
          +
Silver Quarantine Tables
          +
Payment Event Exception Audit
          ↓
Data Quality / Event Trust Health

Silver + Gold Processing Timestamps
          ↓
Data Freshness Health
```

---

## 1. Branch

```powershell
git checkout main
git pull origin main

git branch -d feature/m17b-observability-foundation

git checkout -b feature/m17c-pipeline-dq-monitoring
git status
```

---

## 2. Add files

```text
sql/monitoring/17_pipeline_operational_health.sql
sql/monitoring/17_data_quality_health.sql
sql/monitoring/17_data_freshness.sql
sql/monitoring/17_validate_pipeline_dq_monitoring.sql

tests/unit/test_pipeline_dq_monitoring_contracts.py
docs/demo/M17C-runbook.md
```

---

## 3. Create pipeline operational health

Run:

```text
sql/monitoring/17_pipeline_operational_health.sql
```

Validate:

```sql
SELECT *
FROM payments_dev.monitoring.pipeline_operational_health
ORDER BY pipeline_name;
```

A current pipeline without update history must remain visible as:

```text
operational_status = NEVER_RUN
```

Do not run a pipeline only to manufacture monitoring history.

---

## 4. Create DQ and event-trust monitoring

Run:

```text
sql/monitoring/17_data_quality_health.sql
```

Creates:

```text
payments_dev.monitoring.lakeflow_expectation_metrics
payments_dev.monitoring.dq_quarantine_daily
payments_dev.monitoring.dq_quarantine_rule_metrics
payments_dev.monitoring.payment_event_exception_health
```

### Expectations

Expectation metrics are resolved using:

```sql
event_log(
    TABLE(payments_dev.silver.payment_events_validated)
)
```

This avoids storing a workspace-specific pipeline UUID in Git.

If the Silver pipeline has not emitted expectation-bearing `flow_progress`
events, `lakeflow_expectation_metrics` may legitimately be empty.

### Quarantine

Existing M6 quarantine assets are reused:

```text
payments_dev.silver.payment_events_quarantine
payments_dev.silver.payment_transactions_quarantine
```

### Delivery anomalies

Existing trust audit is reused:

```text
payments_dev.silver.payment_event_exceptions
```

Monitored classifications:

```text
DUPLICATE
LATE
OUT_OF_ORDER
```

A single delivery can have multiple classifications.

---

## 5. Create freshness monitoring

Run:

```text
sql/monitoring/17_data_freshness.sql
```

Then:

```sql
SELECT *
FROM payments_dev.monitoring.data_freshness_health
ORDER BY dataset_name;
```

EPIP separates:

```text
latest_business_time
```

from:

```text
latest_observed_at
```

because synthetic payment events can intentionally use historical business timestamps.

Demo operational thresholds:

```text
RECENT  <= 24 hours
AGING   <= 7 days
STALE   > 7 days
NO_DATA no observed data
```

These are portfolio defaults, not production banking SLAs.

---

## 6. Run validation

Run:

```text
sql/monitoring/17_validate_pipeline_dq_monitoring.sql
```

Review:

- all current EPIP pipelines are visible
- never-run pipelines show `NEVER_RUN`
- latest pipeline states are normalized
- expectation metrics are queryable
- quarantine metrics are queryable
- failed-rule breakdown is queryable
- duplicate/late/out-of-order metrics are queryable
- freshness metrics are queryable

Empty historical metrics are valid when the corresponding workload has not run.

---

## 7. Local quality gates

```powershell
uv run pytest tests/unit/test_pipeline_dq_monitoring_contracts.py -v

uv run pytest -v
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv build

databricks bundle validate -t dev -p PAYMENTS_DEV
databricks bundle validate -t ci -p PAYMENTS_DEV
```

---

## 8. Commit

```powershell
git status

git add sql/monitoring `
        tests/unit/test_pipeline_dq_monitoring_contracts.py `
        docs/demo/M17C-runbook.md

git commit -m "feat(observability): add Lakeflow and data quality monitoring"

git push -u origin feature/m17c-pipeline-dq-monitoring
```

Suggested PR title:

```text
feat(observability): add Lakeflow and data quality monitoring
```

---

## 9. Definition of done

```text
[ ] pipeline_operational_health created
[ ] NEVER_RUN behavior validated
[ ] Lakeflow expectation metrics query successfully
[ ] quarantine daily metrics query successfully
[ ] quarantine rule metrics query successfully
[ ] payment event exception metrics query successfully
[ ] data freshness metrics query successfully
[ ] M17C unit tests pass
[ ] full tests pass
[ ] dev/ci bundle validation passes
[ ] PR merged
```

After M17C:

```text
M17D — Jobs, Query Performance and Operational Security Monitoring
```
