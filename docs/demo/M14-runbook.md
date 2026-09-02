# Milestone 14 Runbook — AI/BI Semantic Layer and Dashboard

## Scope

Milestone 14 includes:

- Unity Catalog analytics schema
- payment operations metric view
- fraud-model metric view
- agent-quality metric view
- three-page AI/BI dashboard
- dashboard bundle binding and deployment

Genie Agent is deferred as an optional future enhancement.

## 1. Validate semantic assets

```sql
SHOW VIEWS IN payments_dev.analytics;
```

Expected:

```text
payment_operations_base
payment_operations_metrics
fraud_model_operations_base
fraud_model_metrics
agent_quality_base
agent_quality_metrics
```

## 2. Payment semantic smoke test

```sql
SELECT
    MEASURE(transaction_count) AS transaction_count,
    MEASURE(total_payment_value) AS total_payment_value,
    MEASURE(authorization_rate) AS authorization_rate,
    MEASURE(decline_rate) AS decline_rate
FROM payments_dev.analytics.payment_operations_metrics;
```

## 3. Fraud-model semantic smoke test

```sql
SELECT
    risk_band,
    MEASURE(transactions_scored) AS transactions_scored,
    MEASURE(predicted_fraud_rate) AS predicted_fraud_rate,
    MEASURE(average_fraud_probability) AS average_fraud_probability
FROM payments_dev.analytics.fraud_model_metrics
GROUP BY risk_band
ORDER BY average_fraud_probability DESC;
```

The output is model analytics. It must not be interpreted as confirmed fraud.

## 4. Agent-quality semantic smoke test

```sql
SELECT
    MEASURE(evaluated_cases) AS evaluated_cases,
    MEASURE(case_pass_rate) AS case_pass_rate,
    MEASURE(average_groundedness) AS average_groundedness,
    MEASURE(scope_compliance_rate) AS scope_compliance_rate,
    MEASURE(safety_compliance_rate) AS safety_compliance_rate,
    MEASURE(human_review_compliance_rate) AS human_review_compliance_rate
FROM payments_dev.analytics.agent_quality_metrics;
```

## 5. Verify dashboard bundle files

Confirm the repository contains:

```text
bundle/resources/<dashboard>.dashboard.yml
src/analytics/<dashboard>.lvdash.json
```

The dashboard resource should reference the `.lvdash.json` file and an actual
SQL warehouse ID.

If the dashboard has not yet been generated and bound, run:

```powershell
databricks bundle generate dashboard `
  --existing-id <DASHBOARD_ID> `
  --key epip_payments_intelligence `
  --resource-dir bundle/resources `
  --dashboard-dir src/analytics `
  --bind
```

## 6. Final local quality checks

```powershell
uv run ruff format .
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest -v
```

## 7. Validate bundle configuration

```powershell
databricks bundle validate -t dev -p PAYMENTS_DEV
```

Expected:

```text
Validation OK!
```

## 8. Preview deployment

Because EPIP uses the direct deployment engine:

```powershell
databricks bundle plan -t dev -p PAYMENTS_DEV
```

Inspect the plan carefully.

For a previously generated and bound dashboard, the dashboard should be updated
or unchanged. It should not unexpectedly create another dashboard.

## 9. Deploy

```powershell
databricks bundle deploy -t dev -p PAYMENTS_DEV
```

## 10. Inspect bundle resources

```powershell
databricks bundle summary -t dev -p PAYMENTS_DEV
```

Confirm that the dashboard is listed as a managed bundle resource.

If the generated key is:

```text
epip_payments_intelligence
```

open it directly with:

```powershell
databricks bundle open epip_payments_intelligence `
  -t dev `
  -p PAYMENTS_DEV
```

## 11. Dashboard smoke test

Open `EPIP Payments Intelligence`.

### Executive Payments

Verify:

- KPI cards contain data;
- transaction/value trend loads;
- channel and payment-method charts load;
- country and merchant analysis loads;
- rate formatting is percentage-based.

### Fraud Intelligence

Verify:

- transactions scored loads;
- predicted fraud metrics load;
- HIGH/MEDIUM/LOW risk bands load;
- fraud probability is presented as a model signal;
- no widget labels predicted fraud as confirmed fraud.

### Fraud Agent Quality

Verify:

- case pass rate loads;
- groundedness/evidence completeness load;
- scope, safety, and human-review compliance load;
- scenario charts load;
- failed-case detail is valid even when the result set is empty.

## 12. Dashboard filters

Verify page filters only target compatible datasets.

Recommended filters:

### Executive Payments

- date
- currency
- channel
- payment method
- country
- merchant

### Fraud Intelligence

- date
- channel
- payment method
- country
- merchant
- risk band

### Agent Quality

- evaluation run
- scenario
- generation model
- judge model
- case pass

## 13. Git review

```powershell
git status
git diff --stat
git diff
```

Make sure no secrets, tokens, generated data, or environment-specific credentials
other than the normal Databricks dashboard warehouse resource reference were
accidentally added.

## 14. Final commit

```powershell
git add .

git commit -m "feat(analytics): add governed AI BI dashboard"
```

Push:

```powershell
git push -u origin feature/m14-ai-bi-genie
```

## 15. Pull request

Suggested PR title:

```text
feat(analytics): add governed AI/BI dashboard
```

Suggested PR summary:

```text
Milestone 14 — Governed AI/BI Analytics

- added Unity Catalog analytics semantic layer
- added payment operations metric view
- added fraud-model metric view
- added fraud-agent quality metric view
- added three-page EPIP Payments Intelligence AI/BI dashboard
- added executive payment analytics
- added fraud-model intelligence analytics
- added M13 agent-quality analytics
- bundle-managed and bound the dashboard
- added semantic and dashboard validation
- documented Genie as an optional future enhancement
```

## Definition of done

Milestone 14 is complete when:

- semantic views are queryable;
- all three dashboard pages load;
- model semantics remain distinct from confirmed fraud;
- dashboard is checked into Git;
- dashboard is bound to the bundle;
- bundle validate passes;
- bundle plan is safe;
- bundle deploy succeeds;
- local tests pass;
- README and PROJECT_STATUS show M14 complete;
- PR is merged.
