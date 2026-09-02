# M14B — Genie Code Dashboard Authoring Prompt

Reference:

- `@payments_dev.analytics.payment_operations_metrics`
- `@payments_dev.analytics.fraud_model_metrics`
- `@payments_dev.analytics.agent_quality_metrics`
- `@payments_dev.analytics.agent_quality_base`

Prompt:

Create a professional three-page AI/BI dashboard named **EPIP Payments Intelligence**.

Use the referenced Unity Catalog metric views as the governed source of business
metrics. Do not recreate their measures with independent dashboard calculations.

Page 1: **Executive Payments**
- KPI counters: Transaction Count, Total Payment Value, Average Transaction Value,
  Authorization Rate, Decline Rate.
- Add daily payment volume/value trend.
- Add payment value by channel.
- Add payment method mix.
- Add payment value by transaction country.
- Add merchant performance table.

Page 2: **Fraud Intelligence**
Add a text note:
"Fraud probability and predicted fraud are model signals used for prioritization
and investigation. They are not confirmed fraud outcomes."

- KPI counters: Transactions Scored, Predicted Fraud Count, Predicted Fraud Rate,
  Average Fraud Probability, High Risk Transactions.
- Add fraud-model trend over time.
- Add HIGH/MEDIUM/LOW risk-band analysis.
- Add channel risk analysis.
- Add cross-border high-risk analysis.
- Add merchant model-risk table.
- Never label predicted_fraud or fraud_probability as confirmed fraud.

Page 3: **Fraud Agent Quality**
- KPI counters: Case Pass Rate, Average Overall Score, Average Groundedness,
  Average Evidence Completeness, Scope Compliance Rate, Safety Compliance Rate,
  Human Review Compliance, Average Agent Duration.
- Add quality by scenario.
- Add tool selection, argument correctness, efficiency and citation quality.
- Add safety, transaction-scope and human-review compliance by scenario.
- Add failed evaluation cases table with case ID, scenario, failure reasons,
  judge rationale and trace ID.

Filters:
- payments/fraud: date, channel, payment method, country, merchant, risk band
- agent quality: evaluation run, scenario type, generation model, judge model,
  case pass

Only connect filters to compatible datasets.

Keep all three pages in one dashboard.
Keep KPI counters at the top.
Use readable two-column chart layouts.
Put detail tables at the bottom.
Use consistent percentage formatting.
Do not query Bronze tables.
Do not alter the governed metric definitions.
Validate every visualization before completion.
