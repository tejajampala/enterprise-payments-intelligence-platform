# Milestone 14B — EPIP AI/BI Dashboard Build

Create one Databricks AI/BI dashboard named `EPIP Payments Intelligence`
with three pages:

1. Executive Payments
2. Fraud Intelligence
3. Fraud Agent Quality

## Page 1 — Executive Payments

KPI counters:
- Transaction Count
- Total Payment Value
- Average Transaction Value
- Authorization Rate
- Decline Rate

Charts:
- Payment Volume and Value Trend
- Payment Value by Channel
- Payment Method Mix
- Payment Value by Country
- Merchant Performance table

## Page 2 — Fraud Intelligence

Add this note:

> Fraud probability and predicted fraud are model signals used for
> prioritization and investigation. They are not confirmed fraud outcomes.

KPI counters:
- Transactions Scored
- Predicted Fraud Count
- Predicted Fraud Rate
- Average Fraud Probability
- High Risk Transactions

Charts:
- Fraud Model Trend
- Transactions by Model Risk Band
- Fraud Signal by Channel
- Cross-Border Risk
- Merchant Model Risk table

## Page 3 — Fraud Agent Quality

KPI counters:
- Case Pass Rate
- Average Overall Score
- Average Groundedness
- Average Evidence Completeness
- Scope Compliance Rate
- Safety Compliance Rate
- Human Review Compliance
- Average Agent Duration

Charts:
- Quality by Evaluation Scenario
- Tool Quality by Scenario
- Safety and Governance Compliance
- Failed Evaluation Cases table

## Filters

Recommended global filters:
- Payment Date where applicable
- Payment Channel where applicable

Recommended page filters:

Executive Payments:
- currency
- payment_method
- transaction_country
- merchant_name

Fraud Intelligence:
- risk_band
- payment_method
- transaction_country
- merchant_name

Fraud Agent Quality:
- evaluation_run_id
- scenario_type
- generation_model
- judge_model
- case_pass

Only connect filters to datasets that contain the corresponding field.

## Final refinement

Ask Genie Code:

`Beautify this dashboard. Keep it professional and executive-friendly. Use
clear page titles, consistent KPI formatting, readable spacing, concise widget
titles, and do not change the underlying business metric definitions.`

Verify:
- percentages render as percentages;
- fraud model signals are never labeled confirmed fraud;
- Agent Quality retains safety, scope and human-review metrics;
- no visualization reads Bronze directly.
