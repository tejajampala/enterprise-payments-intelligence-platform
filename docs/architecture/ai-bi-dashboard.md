# Milestone 14 — Governed AI/BI Analytics Architecture

## Purpose

Milestone 14 exposes EPIP business, fraud-model, and agent-quality information
through a governed semantic analytics layer and a portfolio-ready Databricks
AI/BI dashboard.

The design deliberately separates:

```text
business data
    ↓
governed semantic definitions
    ↓
dashboard consumption
```

so KPI logic is not duplicated independently inside each visualization.

## Architecture

```text
Silver / Gold / ML / Agent Evaluation
                │
                ▼
      payments_dev.analytics
                │
      ┌─────────┼─────────┐
      │         │         │
      ▼         ▼         ▼
   Payments    Fraud     Agent
   Semantic    Model     Quality
   Layer       Layer     Layer
      │         │         │
      └─────────┼─────────┘
                ▼
       Unity Catalog Metric Views
                │
                ▼
      EPIP Payments Intelligence
          AI/BI Dashboard
                │
       ┌────────┼─────────┐
       ▼        ▼         ▼
   Executive   Fraud     Agent
   Payments    Intel     Quality
```

## Analytics schema

Milestone 14 introduces:

```text
payments_dev.analytics
```

This schema is a consumer-oriented semantic layer above the Medallion,
ML, and AI layers.

It does not replace Gold.

Gold continues to provide curated business data products. The analytics schema
provides reusable semantic definitions for BI consumption.

## Semantic base views

```text
payments_dev.analytics.payment_operations_base
payments_dev.analytics.fraud_model_operations_base
payments_dev.analytics.agent_quality_base
```

### Payment operations

`payment_operations_base` provides transaction-grain business-safe payment
dimensions for executive analytics.

### Fraud model

`fraud_model_operations_base` combines transaction context with Champion
fraud-model signals.

Important semantic rule:

```text
predicted_fraud != confirmed fraud
fraud_probability != proof of fraud
```

The risk bands are analytics-only groupings:

```text
HIGH    fraud_probability >= 0.80
MEDIUM  fraud_probability >= 0.50 and < 0.80
LOW     fraud_probability < 0.50
```

### Agent quality

`agent_quality_base` exposes persisted M13 evaluation history including:

- evaluation scenario
- overall quality score
- groundedness
- evidence completeness
- tool correctness
- safety
- scope compliance
- human-review compliance
- judge rationale
- MLflow trace ID

## Unity Catalog metric views

The shared governed metric views are:

```text
payments_dev.analytics.payment_operations_metrics
payments_dev.analytics.fraud_model_metrics
payments_dev.analytics.agent_quality_metrics
```

Metric views are queried using:

```sql
MEASURE(<measure_name>)
```

### Payment measures

Examples include:

- Transaction Count
- Total Payment Value
- Average Transaction Value
- Authorization Rate
- Decline Rate
- Card Not Present Rate
- Unique Customers
- Unique Merchants

### Fraud-model measures

Examples include:

- Transactions Scored
- Predicted Fraud Count
- Predicted Fraud Rate
- Average Fraud Probability
- High Risk Transactions
- Cross-Border High Risk
- Card-Not-Present High Risk

These are model-monitoring measures, not confirmed-fraud outcome measures.

### Agent-quality measures

Examples include:

- Evaluated Cases
- Case Pass Rate
- Average Overall Score
- Average Groundedness
- Average Evidence Completeness
- Average Investigation Quality
- Average Tool Selection
- Average Tool Argument Score
- Average Tool Efficiency
- Average Citation Score
- Scope Compliance Rate
- Safety Compliance Rate
- Human Review Compliance
- Average Agent Duration

## AI/BI dashboard

The dashboard is:

```text
EPIP Payments Intelligence
```

It contains three pages.

### Page 1 — Executive Payments

Provides:

- transaction count
- payment value
- average transaction value
- authorization and decline rates
- payment trends
- channel analysis
- payment-method analysis
- country analysis
- merchant performance

### Page 2 — Fraud Intelligence

Provides:

- transactions scored
- predicted fraud count and rate
- average fraud probability
- high-risk model signals
- risk-band trends
- channel risk
- cross-border model risk
- merchant model-risk analysis

The page explicitly distinguishes model signals from confirmed fraud.

### Page 3 — Fraud Agent Quality

Provides:

- M13 case pass rate
- groundedness
- evidence completeness
- investigation quality
- tool quality
- scope compliance
- safety compliance
- human-review compliance
- failed evaluation cases and trace IDs

This makes the AI evaluation lifecycle observable to engineers and reviewers.

## Dashboard as code

The dashboard is developed interactively in Databricks and then bound to the
Declarative Automation Bundle.

The checked-in representation contains:

```text
bundle/resources/*.dashboard.yml
src/analytics/*.lvdash.json
```

Binding the existing dashboard to the bundle prevents a second copy from being
created during deployment.

## Genie decision

Genie Agent integration is intentionally deferred.

The architecture remains Genie-ready because both the dashboard and a future
Genie Agent can consume the same Unity Catalog metric views.

```text
Metric Views
    ├── AI/BI Dashboard     ← implemented
    └── Genie Agent         ← optional future enhancement
```

Deferring Genie does not leave a gap in the governed semantic architecture.

## Enterprise rationale

The design demonstrates:

- centralized KPI definitions;
- semantic reuse;
- separation of Gold data products from consumption semantics;
- governed fraud-model terminology;
- AI-agent quality observability;
- dashboard version control;
- reproducible bundle deployment;
- extensibility to future conversational analytics.
