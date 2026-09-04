# Enterprise Payments Intelligence Platform — Implementation Status

This document tracks the **actual deployed and validated implementation state** of EPIP.

A milestone is marked **COMPLETE** only when its code, deployment, validation,
tests, and documentation have been completed. Source files existing in Git do not,
by themselves, make a milestone complete.

> **Current status:** Milestones 1–15 complete. Milestone 16 Security and Governance is in progress.

---

## Overall Roadmap

| Milestone | Capability | Status |
|---|---|---|
| M1 | Platform foundation | COMPLETE |
| M2 | Synthetic payments domain | COMPLETE |
| M3 | Batch ingestion | COMPLETE |
| M4 | Streaming ingestion | COMPLETE |
| M5 | Lakeflow and Medallion architecture | COMPLETE |
| M6 | Data quality, CDC, and SCD Type 2 | COMPLETE |
| M7 | Feature engineering and Feature Store | COMPLETE |
| M8 | Fraud detection | COMPLETE |
| M9 | Forecasting | COMPLETE |
| M10 | MLOps | COMPLETE |
| M11 | Governed RAG and AI Search | COMPLETE |
| M12 | Governed Fraud Investigation Agent | COMPLETE |
| M13 | Agent evaluation and regression gates | COMPLETE |
| M14 | Governed AI/BI semantic layer and dashboard | COMPLETE |
| M15 | Enterprise CI/CD | COMPLETE |
| M16 | Security and governance | **IN PROGRESS** |
| M17 | Monitoring and cost optimisation | NOT STARTED |
| M18 | Azure portability | NOT STARTED |

---

## Milestones 1–14 — Completed Foundation

### M1 — Platform Foundation

**COMPLETE**

- local developer environment
- Databricks workspace
- Databricks CLI
- repository structure
- bundle foundation
- GitHub portfolio foundation

### M2 — Synthetic Payments Domain

**COMPLETE**

- canonical customer, account, merchant, payment, event, and fraud-case models
- deterministic synthetic data
- duplicate / late / out-of-order scenarios
- local source-system datasets

### M3 — Batch Ingestion

**COMPLETE**

- governed batch baseline
- Unity Catalog storage access
- AWS S3 landing zone
- PostgreSQL-style snapshots
- reconciliation

### M4 — Streaming Ingestion

**COMPLETE**

- Kafka event contract
- Amazon MSK
- IAM authentication
- service credential access
- Bronze streaming ingestion
- offset lineage
- duplicate / late / out-of-order scenarios
- checkpoint recovery
- reconciliation

### M5 — Lakeflow and Medallion Architecture

**COMPLETE**

- Silver transformation
- enrichment
- Gold analytics
- incremental design
- reconciliation
- tests and docs

### M6 — Data Quality, CDC, and SCD Type 2

**COMPLETE**

- expectations
- quarantine
- streaming deduplication
- watermark handling
- Auto Loader CDC
- AUTO CDC
- SCD Type 1
- SCD Type 2
- sequencing and deletes
- trusted enrichment
- Row Tracking
- Change Data Feed

### M7 — Feature Engineering and Feature Store

**COMPLETE**

Key assets:

```text
payments_dev.features.transaction_fraud_features
payments_dev.features.customer_behavior_features
payments_dev.features.merchant_behavior_features
```

### M8 — Fraud Detection

**COMPLETE**

- temporal split
- logistic baseline
- gradient-boosted challenger
- imbalance handling
- threshold tuning
- MLflow tracking
- governed evaluation

### M9 — Forecasting

**COMPLETE**

- daily forecasting dataset
- lag and rolling features
- seasonal baseline
- Ridge
- gradient boosting
- recursive forecasts
- temporal validation
- MLflow

### M10 — MLOps

**COMPLETE**

Key asset:

```text
payments_dev.models.fraud_detection_model
```

Implemented:

- UC Model Registry
- Candidate / Champion
- PreviousChampion
- model quality gates
- lifecycle audit
- serving package
- Champion batch scoring
- rollback support

### M11 — Governed RAG and AI Search

**COMPLETE**

- governed knowledge corpus
- AI Search
- HYBRID retrieval
- bounded Top-K
- Claude generation
- retrieval evaluation
- answer evaluation
- MLflow tracing

### M12 — Governed Fraud Investigation Agent

**COMPLETE**

Approved tools:

```text
get_transaction_context
get_fraud_evidence
search_fraud_knowledge
```

Implemented:

- governed evidence
- Champion model evidence
- bounded search
- scope controls
- no arbitrary SQL
- no state-changing tools
- human review
- durable history
- MLflow traceability

### M13 — Agent Evaluation and Regression Gates

**COMPLETE**

Key assets:

```text
payments_dev.ai.agent_evaluation_dataset
payments_dev.ai.agent_evaluation_results
payments_dev.ai.agent_evaluation_summary
```

Implemented:

- golden cases
- deterministic scoring
- LLM judge
- groundedness
- evidence completeness
- safety / human review / scope gates
- per-case history
- aggregate regression gates

### M14 — Governed AI/BI Analytics

**COMPLETE**

Implemented:

- analytics semantic schema
- semantic base views
- metric views
- governed measures
- three-page AI/BI dashboard
- dashboard-as-code

Genie remains optional/deferred.

---

## Milestone 15 — Enterprise CI/CD

Status: **COMPLETE**

### M15A — Pull Request Quality Gates

**COMPLETE**

- pytest
- Ruff
- formatting
- mypy
- package build
- Terraform validation
- Databricks bundle validation/plan

### M15B — CI Workload Identity

**COMPLETE**

- dedicated CI service principal
- GitHub OIDC
- no PAT
- no client secret
- CI GitHub Environment

### M15C — Controlled Databricks Deployment

**COMPLETE**

- post-merge deployment
- isolated `payments_ci`
- controlled resource slice
- serialized deployment
- cost-safe pipeline definitions

### M15D — ML and Agent Promotion Gates

**COMPLETE**

- fraud selected-model validation
- Champion consistency check
- agent threshold checks
- evaluation freshness
- release blocking on stale/failed evidence

### M15E — Production Approval and Release

**COMPLETE**

- dedicated production service principal
- production OIDC
- GitHub production Environment
- `payments_prod`
- production bundle
- production mode
- promoted-SHA verification
- approval-controlled deployment
- full production bundle deployment
- no production `--select`

Validated chain:

```text
PR
 ↓
CI
 ↓
main
 ↓
CI Deployment
 ↓
ML + Agent Promotion Gates
 ↓
Production Approval
 ↓
Production OIDC
 ↓
payments_prod
```

---

## Milestone 16 — Security and Governance

Status: **IN PROGRESS**

### Objective

Add explicit enterprise identity, RBAC, governed data classification, ABAC masking,
jurisdictional row filtering, environment isolation validation, and security evidence.

### M16A — Account Groups and RBAC Foundation

Status: **IN PROGRESS**

Account-level groups created:

```text
epip-platform-admins
epip-data-engineers
epip-ml-engineers
epip-fraud-analysts
epip-fraud-analysts-au
epip-bi-consumers
```

Remaining:

- assign account groups to the workspace
- confirm workspace group source is Account
- assign selected users to appropriate groups
- apply and validate RBAC

Automation identities remain separate:

```text
epip-github-actions-ci
epip-github-actions-prod
```

### M16B — Governed Classification

Status: **SOURCE IMPLEMENTED / RUNTIME VALIDATION PENDING**

Assets:

```text
governance/classification.yml
governance/access-matrix.yml
sql/governance/16_create_governed_tags.sql
sql/governance/16_apply_data_classification.sql
```

Governed tags:

```text
epip_classification
epip_pii
epip_region_key
```

Design:

```text
epip_classification
    → sensitivity tier + ABAC policy scope

epip_pii
    → mask type

epip_region_key
    → row-filter key
```

### M16C — ABAC Masking and Row Filtering

Status: **SOURCE IMPLEMENTED / RUNTIME VALIDATION PENDING**

Initial protected table:

```text
payments_dev.silver.customers_current
```

Mask categories:

```text
name
email
phone
date_of_birth
address
```

Regional policy:

```text
epip-fraud-analysts-au
    → country = AU
```

Pending live validation:

- create/verify governance schema
- create UDFs
- create policies
- show effective policies
- privileged query
- restricted analyst query
- AU-only row-scope query

### M16D — Security Isolation and Audit Evidence

Status: **PENDING**

Validate:

- CI SP has no broad production access
- production SP has no broad development access
- BI consumers have no general Bronze/Silver engineering access
- fraud analysts have narrow Silver access
- customer table is `restricted`
- sensitive customer columns are governed tagged
- effective policies match design
- governed tag assignment permissions are restricted

### M16E — Tests, Documentation, Closeout

Status: **IN PROGRESS**

Artifacts:

```text
tests/unit/test_security_governance_contracts.py
docs/architecture/security-governance.md
docs/demo/M16-runbook.md
README.md
docs/PROJECT_STATUS.md
```

Definition of done:

```text
account groups assigned
RBAC applied
governed tags created
classification applied
security UDFs created
ABAC policies created
effective policies verified
restricted-user behavior verified
AU row filter verified
CI/prod isolation verified
tests passing
docs complete
PR merged
post-merge CI/CD green
```

Only then change M16 to **COMPLETE**.

---

## Milestone 17 — Monitoring and Cost Optimisation

Status: **NOT STARTED**

Planned:

- Lakeflow health
- job failure monitoring
- data-quality trends
- system-table observability
- ML monitoring
- agent/trace monitoring
- cost attribution
- serverless usage monitoring
- SQL warehouse optimisation
- budgets and alerts
- operational dashboard

---

## Milestone 18 — Azure Portability

Status: **NOT STARTED**

Planned:

- Azure Databricks mapping
- ADLS Gen2
- Azure identity/security mapping
- Azure networking
- Terraform portability
- AWS-to-Azure service mapping
- architecture trade-offs

---

## Current Portfolio Story

```text
Synthetic Payments
        ↓
Batch + Streaming
        ↓
Bronze / Silver / Gold
        ↓
Data Quality + CDC + SCD
        ↓
Feature Store
        ↓
Fraud ML + Forecasting
        ↓
MLOps
        ↓
RAG + AI Search
        ↓
Governed Fraud Agent
        ↓
Agent Evaluation
        ↓
Governed AI/BI
        ↓
Enterprise CI/CD
        ↓
Security / Governance (in progress)
```

After M16 closeout, the next milestone is M17 Monitoring and Cost Optimisation.
