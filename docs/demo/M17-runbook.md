# M17 — Final Monitoring, Observability and Cost Runbook

## Final milestone

M17D is the final implementation step of EPIP.

No further implementation milestone is planned.

After this runbook is completed and the PR is merged:

```text
M1-M17 COMPLETE
EPIP COMPLETE
```

---

# 1. Create the final branch

```powershell
git checkout main
git pull origin main

git branch -d feature/m17c-pipeline-dq-monitoring

git checkout -b feature/m17d-complete-observability
git status
```

If the old local M17C branch cannot be deleted because Git does not recognize
the GitHub merge as an ancestor, first confirm the M17C PR is merged and the
changes are present in `main`; only then use `git branch -D`.

---

# 2. Add the M17D files

Add:

```text
sql/monitoring/
├── 17_job_task_health.sql
├── 17_query_warehouse_health.sql
├── 17_security_events.sql
├── 17_ml_agent_health.sql
├── 17_cost_monitoring.sql
├── 17_operations_summary.sql
└── 17_validate_m17_complete.sql

bundle/resources/
├── epip_platform_operations.dashboard.yml
└── monitoring_alerts.yml

src/analytics/
└── epip_platform_operations.lvdash.json

tests/unit/
└── test_m17_complete_monitoring_contracts.py

docs/architecture/
└── monitoring-cost-architecture.md

docs/demo/
└── M17-runbook.md
```

Replace:

```text
databricks.yml
bundle/resources/epip_payments_intelligence.dashboard.yml
README.md
docs/PROJECT_STATUS.md
docs/architecture/platform-architecture.md
```

The root bundle change introduces a reusable:

```text
sql_warehouse_id
```

variable so both dashboards and operational alerts use a bundle variable rather
than duplicating a warehouse ID across resource files.

---

# 3. Important prerequisite

M17B and M17C must already exist.

The M17D views depend on:

```text
payments_dev.monitoring.current_epip_pipelines
payments_dev.monitoring.current_epip_jobs
payments_dev.monitoring.epip_job_run_health
payments_dev.monitoring.pipeline_operational_health
payments_dev.monitoring.data_freshness_health
```

M17C is already merged in EPIP.

---

# 4. Run M17D SQL

Use Databricks SQL and execute in this order.

## 4.1 Jobs and tasks

```text
sql/monitoring/17_job_task_health.sql
```

Creates:

```text
current_epip_job_tasks
epip_job_task_run_health
job_operational_health
job_daily_health
```

A current job that has never executed remains visible as:

```text
NEVER_RUN
```

Zero historical rows are not automatically failures.

## 4.2 Query and warehouse health

```text
sql/monitoring/17_query_warehouse_health.sql
```

Creates:

```text
epip_query_performance
query_performance_daily
warehouse_operational_health
```

The query layer surfaces:

```text
duration
queue wait
bytes/files read
file pruning
spill
shuffle
result-cache usage
job/dashboard/notebook source metadata
```

Demo indicators such as LONG_RUNNING and HIGH_SCAN are diagnostics, not
production banking SLAs.

## 4.3 Operational security

```text
sql/monitoring/17_security_events.sql
```

Creates:

```text
epip_security_events
security_event_daily
```

The curated view intentionally does not expose:

```text
source_ip_address
raw request_params
```

It is not intended to replace a security/SIEM platform.

## 4.4 ML and agent health

```text
sql/monitoring/17_ml_agent_health.sql
```

Creates:

```text
fraud_model_current_health
agent_evaluation_health
agent_latest_health
agent_failed_case_diagnostics
```

Fraud-model monitoring uses existing governed Champion scoring evidence.

Agent monitoring uses existing M13 persisted evaluation evidence.

No model retraining or agent re-evaluation is required merely to create these
views.

## 4.5 Cost monitoring

```text
sql/monitoring/17_cost_monitoring.sql
```

Creates:

```text
databricks_usage_cost_detail
databricks_cost_daily
databricks_cost_by_sku
databricks_cost_by_workload
cost_optimisation_candidates
```

The billing layer sums Databricks billing records including correction rows.

Do not interpret the resulting value as the complete AWS bill.

## 4.6 Consolidated operations

```text
sql/monitoring/17_operations_summary.sql
```

Creates:

```text
dq_current_health
platform_operations_summary
operations_alert_candidates
```

`dq_current_health` explicitly converts the healthy zero-quarantine situation
seen during M17C into a dashboard-ready state.

---

# 5. Run final SQL validation

Execute:

```text
sql/monitoring/17_validate_m17_complete.sql
```

Important interpretation rules:

| Result | Interpretation |
|---|---|
| `NEVER_RUN` pipeline/job | valid definition with no run history |
| empty task/query/security history | valid if no qualifying activity exists |
| quarantine historical views empty | valid when no rows failed DQ |
| `dq_current_health = HEALTHY` | explicit zero-quarantine state |
| billing rows delayed | normal System Table delivery behavior |
| cost = 0 | valid when no priced/recent qualifying usage exists |
| agent result absent | investigate only if M13 formal evaluation should exist |

Do not start expensive workloads merely to make monitoring charts non-empty.

---

# 6. Run local contract tests before bundle deployment

```powershell
uv run pytest tests/unit/test_m17_complete_monitoring_contracts.py -v
```

Then:

```powershell
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv build
```

Fix code/test errors before proceeding.

---

# 7. Validate the bundle

The operational dashboard and alerts use:

```text
${var.sql_warehouse_id}
```

The development default points to the same existing SQL warehouse used by the
current business dashboard.

If you want to override it locally:

```powershell
$env:BUNDLE_VAR_sql_warehouse_id = "<existing-sql-warehouse-id>"
```

Then:

```powershell
databricks bundle validate -t dev -p PAYMENTS_DEV
databricks bundle plan -t dev -p PAYMENTS_DEV
```

Also validate CI configuration:

```powershell
databricks bundle validate -t ci -p PAYMENTS_DEV
databricks bundle plan -t ci -p PAYMENTS_DEV
```

Do not deploy until bundle validation is green.

---

# 8. Deploy the development bundle

After the SQL views exist:

```powershell
databricks bundle deploy -t dev -p PAYMENTS_DEV
```

Expected new resources include:

```text
EPIP Platform Operations & Cost
EPIP - Pipeline Failure
EPIP - Data Freshness
EPIP - DQ Degradation
EPIP - Agent Regression
EPIP - Databricks Cost Anomaly
```

The alerts should be:

```text
PAUSED
```

after deployment.

This is intentional.

---

# 9. Validate the operations dashboard

Open:

```text
EPIP Platform Operations & Cost
```

Expected pages:

1. Platform Health
2. Data Quality & Security
3. ML & Agent Health
4. Cost & Performance

The dashboard is operational and intentionally separate from:

```text
EPIP Payments Intelligence
```

The business dashboard answers business questions.

The operations dashboard answers platform reliability, quality, security, AI
quality and cost questions.

---

# 10. Alerts

Keep all five alerts paused during normal portfolio development.

The alert resources exist to demonstrate an enterprise monitoring architecture,
not to force scheduled compute consumption.

If you want a live demo later:

1. choose one alert
2. verify its query manually
3. configure an approved notification destination if required
4. unpause it
5. demonstrate it
6. pause it again

Do not invent or commit email addresses, Slack webhooks or notification IDs.

---

# 11. Final documentation closeout

Only after SQL, tests, bundle validation and dev deployment pass, replace the
final documentation files supplied with M17D:

```text
README.md
docs/PROJECT_STATUS.md
docs/architecture/platform-architecture.md
```

They intentionally mark:

```text
Milestones 1-17 COMPLETE
EPIP COMPLETE
```

and remove the obsolete future-milestone entry entirely.

This sequencing prevents the repository from claiming completion before
runtime validation.

---

# 12. Final quality gate

Run once more:

```powershell
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv build

databricks bundle validate -t dev -p PAYMENTS_DEV
databricks bundle plan -t dev -p PAYMENTS_DEV

databricks bundle validate -t ci -p PAYMENTS_DEV
databricks bundle plan -t ci -p PAYMENTS_DEV
```

Then:

```powershell
git status
git diff --check
```

Review especially:

```text
no secrets
no private account/workspace IDs added
no AWS DMS claim
no VPC endpoint claim
no production RDS claim
no complete AWS-cost claim
no obsolete future milestone
```

---

# 13. Suggested logical commits

One branch/PR, several meaningful commits:

```powershell
git add sql/monitoring
git commit -m "feat(observability): add operational platform monitoring"

git add bundle/resources src/analytics databricks.yml
git commit -m "feat(analytics): add platform operations dashboard and alerts"

git add tests docs README.md
git commit -m "docs(observability): close final EPIP milestone"
```

You can also use a single commit if preferred, but the logical history is
stronger for an interview portfolio.

---

# 14. Push and PR

```powershell
git push -u origin feature/m17d-complete-observability
```

Suggested PR title:

```text
feat(observability): complete EPIP monitoring and cost optimisation
```

Suggested PR summary:

```text
Final EPIP milestone.

- completes job/task operational monitoring
- adds query and SQL warehouse performance monitoring
- adds curated operational security monitoring
- adds Champion fraud-scoring health
- adds persisted agent evaluation/regression monitoring
- adds Databricks billing and list-cost attribution
- adds evidence-based cost optimisation candidates
- adds explicit zero-quarantine DQ health
- adds consolidated platform operations summary
- adds version-controlled Platform Operations & Cost dashboard
- adds paused SQL alert resources
- adds final M17 validation and contract tests
- closes M17 and removes the obsolete future-milestone entry from the roadmap
```

Merge only after CI is green.

---

# 15. Final project state

After merge:

```text
M1  COMPLETE
...
M16 COMPLETE
M17 COMPLETE

EPIP COMPLETE
```

No further implementation milestone is planned.

The repository is then a completed enterprise portfolio implementation with:

```text
Data Engineering
+ Streaming
+ Lakehouse
+ DQ / CDC / SCD
+ Feature Engineering
+ Fraud ML
+ Forecasting
+ MLOps
+ RAG
+ Agentic AI
+ Agent Evaluation
+ Governed Analytics
+ CI/CD
+ Security / Governance
+ Observability
+ Operational Security
+ Cost Attribution
+ Operations Dashboard / Alerts
```
