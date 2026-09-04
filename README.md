# Enterprise Payments Intelligence Platform

An enterprise-grade Databricks reference implementation for payments data engineering,
machine learning, MLOps, Generative AI, agentic AI, analytics, governance, and platform
engineering on AWS.

> **Project Status:** Active Development — Milestones 1–15 complete; Milestone 16 Security and Governance in progress.

---

## Business Problem

Modern financial institutions process large volumes of payment transactions across
multiple channels and source systems. A production payments intelligence platform must:

- ingest batch and streaming payment data reliably
- maintain trusted customer, account, and merchant history
- handle duplicates, late events, out-of-order events, CDC, and deletes
- implement governed Bronze, Silver, and Gold data products
- detect potentially fraudulent transactions
- forecast payment volumes
- provide point-in-time correct ML features
- promote models through governed MLOps controls
- ground Generative AI in governed enterprise knowledge
- evaluate AI agents before promotion
- expose governed business metrics through analytics
- protect sensitive data with least-privilege access controls
- automate validation and deployment through enterprise CI/CD
- provide operational monitoring and cost governance

The **Enterprise Payments Intelligence Platform (EPIP)** demonstrates how these
requirements can be implemented using the Databricks Data Intelligence Platform on AWS.

---

## Target Architecture

```text
                               PAYMENT DATA SOURCES

                    ┌─────────────┬─────────────┬─────────────┐
                    │             │             │
                    ▼             ▼             ▼
               S3 / Files     PostgreSQL     Kafka / MSK
                    │             │             │
                    └─────────────┼─────────────┘
                                  │
                                  ▼
                           AWS Databricks
                                  │
                            Unity Catalog
                                  │
                                  ▼
                         Ingestion Framework
                                  │
                ┌─────────────────┼─────────────────┐
                │                 │                 │
                ▼                 ▼                 ▼
           Auto Loader           JDBC       Structured Streaming
                │                 │                 │
                └─────────────────┼─────────────────┘
                                  │
                                  ▼
                                Bronze
                                  │
                                  ▼
                                Silver
                                  │
                    ┌─────────────┼─────────────┐
                    │             │             │
                    ▼             ▼             ▼
               Data Quality     AUTO CDC     SCD Type 2
                    │             │             │
                    └─────────────┼─────────────┘
                                  │
                                  ▼
                                 Gold
                                  │
          ┌───────────────────────┼────────────────────────┐
          │                       │                        │
          ▼                       ▼                        ▼
     Feature Store          Governed Analytics       AI Search / RAG
          │                 Semantic Layer                  │
          ▼                       │                         ▼
      ML Models                    ▼                 Fraud Knowledge Base
          │                 UC Metric Views                  │
          ▼                       │                         ▼
 Batch / Serving                  ▼                 Fraud Investigation
                                  │                        Agent
                                  │                         │
                                  │                         ▼
                                  │                  Agent Evaluation
                                  │                 + Regression Gates
                                  │                         │
                                  └───────────┬─────────────┘
                                              │
                                              ▼
                                  EPIP Payments Intelligence
                                      AI/BI Dashboard
                                              │
                                              ▼
                                      Business Consumers
```

Security and governance are cross-cutting controls:

```text
Account Identities / Groups
          │
          ▼
       UC RBAC
          │
          ▼
   Governed Tags
          │
          ▼
         ABAC
    ┌─────┴─────┐
    ▼           ▼
Column Masks  Row Filters
    │           │
    └─────┬─────┘
          ▼
Governed Data Products
```

---

## Environment Model

| Environment | Primary purpose | Catalog |
|---|---|---|
| Development | Engineering, ML, AI, analytics, experimentation | `payments_dev` |
| CI | Isolated validation and controlled deployment | `payments_ci` |
| Production-style | Approval-controlled deployment | `payments_prod` |

Production deployment uses a dedicated service principal and GitHub OIDC workload
identity federation rather than a Databricks PAT or stored OAuth client secret.

---

## Platform Capabilities

### Data Engineering

Implemented capabilities include:

- governed AWS S3 batch ingestion
- PostgreSQL-style snapshot ingestion
- PostgreSQL-style CDC extracts
- Amazon MSK streaming ingestion
- AWS IAM authenticated Kafka publishing
- Unity Catalog service credentials
- Bronze Kafka physical-event preservation
- Silver streaming standardization
- watermark-aware event deduplication
- late-event classification
- out-of-order delivery auditing
- Auto Loader ingestion
- Lakeflow Declarative Pipelines
- Lakeflow data-quality expectations
- validated and quarantine data products
- Lakeflow AUTO CDC
- SCD Type 1 current-state dimensions
- SCD Type 2 historical dimensions
- delete handling
- record-version sequencing
- trusted current-state transaction enrichment
- Gold payment, merchant, channel, and fraud operations metrics
- Delta Row Tracking
- Delta Change Data Feed
- Silver-to-Gold reconciliation

### Feature Engineering

Implemented capabilities include:

- Unity Catalog governed feature tables
- transaction-level fraud features
- point-in-time customer behavior features
- point-in-time merchant behavior features
- TIMESERIES feature-table primary keys
- leakage-safe feature windows
- `FeatureEngineeringClient` training-set construction
- point-in-time feature lookups

Key assets:

```text
payments_dev.features.transaction_fraud_features
payments_dev.features.customer_behavior_features
payments_dev.features.merchant_behavior_features
```

### Machine Learning and MLOps

Implemented capabilities include:

- temporal train / validation / test splits
- logistic-regression fraud baseline
- gradient-boosted fraud challenger
- class-imbalance handling
- fraud-focused F2 threshold tuning
- average precision evaluation
- untouched test evaluation
- payment-volume forecasting
- lag and rolling features
- seasonal, Ridge, and gradient-boosted forecast comparison
- recursive forecasting
- MLflow experiment tracking
- Unity Catalog Model Registry
- Candidate / Champion aliases
- PreviousChampion rollback support
- model validation gates
- lifecycle audit history
- production serving package
- Champion-based batch scoring
- model provenance tags

Key model asset:

```text
payments_dev.models.fraud_detection_model
```

### Governed RAG and AI Search

Implemented capabilities include:

- governed fraud-investigation knowledge corpus
- Databricks AI Search
- HYBRID retrieval
- bounded Top-K retrieval
- source-aware answers
- RAG evaluation datasets
- retrieval-quality evaluation
- response-quality evaluation
- MLflow GenAI tracing
- Claude generation with Databricks-governed retrieval

### Governed Fraud Investigation Agent

Approved tools:

```text
get_transaction_context
get_fraud_evidence
search_fraud_knowledge
```

Implemented controls include:

- transaction-scope enforcement
- tool allowlist
- duplicate tool-call protection
- maximum tool-call enforcement
- unknown-tool rejection
- no arbitrary SQL tool
- no state-changing tools
- no autonomous fraud decision
- human-review requirement
- MLflow ResponsesAgent integration
- durable Delta investigation history
- evidence and model provenance
- bounded knowledge retrieval

The agent cannot decline a payment, block a card, freeze an account, update a fraud
case, or confirm fraud. Human review remains mandatory.

### Agent Evaluation and Regression Gates

Implemented capabilities include:

- governed golden evaluation dataset
- deterministic tool-selection scoring
- tool-argument scoring
- tool-efficiency scoring
- transaction-scope compliance
- response-structure compliance
- citation correctness
- human-review compliance
- autonomous-action safety checks
- groundedness evaluation
- evidence-completeness evaluation
- structured LLM-as-a-judge scoring
- per-case persisted evaluation history
- aggregate regression gates
- MLflow trace linkage

Critical controls:

```text
transaction scope
safety
human review
response structure
```

### Governed AI/BI Analytics

Implemented capabilities include:

- Unity Catalog `analytics` schema
- payment-operations semantic base views
- fraud-model semantic base views
- fraud-agent quality semantic base views
- Unity Catalog metric views
- governed `MEASURE(...)` KPI definitions
- three-page `EPIP Payments Intelligence` AI/BI dashboard
- dashboard-as-code through Declarative Automation Bundles

Dashboard pages:

1. Executive Payments
2. Fraud Intelligence
3. Fraud Agent Quality

Databricks Genie remains an optional future enhancement.

---

## Enterprise CI/CD

Milestone 15 is complete.

```text
Feature Branch
      │
      ▼
Pull Request
      │
      ▼
Python / Terraform / Bundle Validation
      │
      ▼
main
      │
      ▼
CI OIDC Service Principal
      │
      ▼
payments_ci Deployment
      │
      ▼
ML + Agent Promotion Gates
      │
      ▼
PASS
      │
      ▼
GitHub Production Environment Approval
      │
      ▼
Production OIDC Service Principal
      │
      ▼
payments_prod Deployment
```

Implemented controls include:

- pull-request quality gates
- Ruff validation
- formatting checks
- mypy checks
- pytest
- package build validation
- Terraform formatting and validation
- Databricks bundle validation and planning
- GitHub OIDC workload identity federation
- dedicated CI service principal
- dedicated production service principal
- isolated CI catalog
- isolated production catalog
- controlled production workspace path
- ML promotion validation
- agent regression promotion validation
- evaluation freshness checks
- promoted-SHA verification
- GitHub Environment production approval
- full production bundle deployment without production `--select`
- no Databricks PAT
- no Databricks OAuth client secret

---

## Security and Governance — Milestone 16

**Status: IN PROGRESS**

The M16 governance-as-code assets are present, but workspace group assignment,
runtime RBAC/ABAC application, and live validation must be completed before the
milestone is marked complete.

### Account Groups

```text
epip-platform-admins
epip-data-engineers
epip-ml-engineers
epip-fraud-analysts
epip-fraud-analysts-au
epip-bi-consumers
```

Automation identities remain separate:

```text
epip-github-actions-ci
epip-github-actions-prod
```

### Governed Tags

EPIP uses:

```text
epip_classification
epip_pii
epip_region_key
```

`epip_classification` is **not dead metadata**.

It is used for:

- enterprise discovery and search
- security inventory
- audit evidence
- object and column sensitivity
- ABAC policy scoping through `WHEN has_tag_value(...)`

For the initial protected data product:

```text
payments_dev.silver.customers_current
    epip_classification = restricted
```

`epip_pii` selects the type-specific mask:

```text
name
date_of_birth
email
phone
address
network_identifier
```

`epip_region_key` identifies the jurisdiction column:

```text
country
```

### Why Classification and PII Are Separate

A classification tier tells us **how sensitive** something is.

A PII category tells us **how it should be masked**.

```text
epip_classification
        ↓
"Should this object be under restricted-data policy scope?"

epip_pii
        ↓
"What masking behavior should this column use?"
```

Examples:

| Field | Classification | PII type | Behavior |
|---|---|---|---|
| `first_name` | restricted | name | full mask |
| `email` | restricted | email | retain domain only |
| `phone` | restricted | phone | full mask |
| `date_of_birth` | restricted | date_of_birth | reduce to year |
| `address_line_1` | restricted | address | full mask |

### RBAC + ABAC

```text
RBAC
  → Can the principal access the object?

ABAC
  → If yes, which rows and values can the principal see?
```

The AU fraud analyst demonstration adds:

```text
country = AU
```

through a row-filter policy.

---

## Engineering Principles

- Infrastructure as Code
- automated testing
- reproducible environments
- environment isolation
- workload identity federation
- least privilege
- account-group-based human access
- service-principal-based automation
- governed data classification
- centralized ABAC
- separation of duties
- data-quality enforcement
- model evaluation before promotion
- agent evaluation before promotion
- synthetic data only
- cost-aware development
- human oversight for consequential AI-assisted decisions
- point-in-time correctness
- leakage prevention
- ML and agent traceability
- version-controlled analytics assets

---

## Repository Structure

```text
enterprise-payments-intelligence-platform/
│
├── .github/
│   └── workflows/
├── bundle/
│   └── resources/
├── deploy/
│   └── prod/
├── docs/
│   ├── adr/
│   ├── architecture/
│   ├── demo/
│   └── PROJECT_STATUS.md
├── governance/
│   ├── access-matrix.yml
│   └── classification.yml
├── infra/
│   └── terraform/
├── notebooks/
├── pipelines/
├── scripts/
├── sql/
│   ├── analytics/
│   └── governance/
├── src/
├── tests/
├── bundle.targets.yml
├── databricks.yml
├── pyproject.toml
├── README.md
└── uv.lock
```

---

## Local Development

```powershell
uv sync --locked --dev
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv build
```

Validate the development bundle:

```powershell
databricks bundle validate -t dev -p PAYMENTS_DEV
databricks bundle plan -t dev -p PAYMENTS_DEV
```

---

## Key Demo Paths

Streaming runbook:

```text
docs/demo/streaming-demo-runbook.md
```

Fraud agent:

```powershell
uv run python scripts/agents/12_run_agent_demo_scenarios.py `
  --profile PAYMENTS_DEV `
  --catalog payments_dev
```

Agent evaluation:

```powershell
uv run python scripts/agents/13_evaluate_fraud_investigation_agent.py `
  --profile PAYMENTS_DEV `
  --catalog payments_dev
```

AI/BI dashboard:

```text
EPIP Payments Intelligence
```

Security/governance:

```text
docs/architecture/security-governance.md
docs/demo/M16-runbook.md
```

---

## Implementation Roadmap

| Milestone | Capability | Status |
|---|---|---|
| 1 | Platform and repository foundation | Complete |
| 2 | Synthetic payments domain | Complete |
| 3 | Batch ingestion | Complete |
| 4 | Streaming ingestion | Complete |
| 5 | Lakeflow and Medallion architecture | Complete |
| 6 | Data quality, CDC, and SCD Type 2 | Complete |
| 7 | Feature engineering and Feature Store | Complete |
| 8 | Fraud detection ML | Complete |
| 9 | Forecasting ML | Complete |
| 10 | MLOps | Complete |
| 11 | RAG and AI Search | Complete |
| 12 | Governed Fraud Investigation Agent | Complete |
| 13 | Agent evaluation and regression gates | Complete |
| 14 | Governed AI/BI semantic layer and dashboard | Complete |
| 15 | Enterprise CI/CD | Complete |
| 16 | Security and governance | **In Progress** |
| 17 | Monitoring and cost optimisation | Not Started |
| 18 | Azure portability | Not Started |

Detailed implementation progress:

```text
docs/PROJECT_STATUS.md
```

---

## Current Milestone — M16

Remaining closeout work:

- complete workspace assignment of account-level EPIP groups
- verify workspace-visible groups remain account sourced
- apply and validate RBAC
- create/verify governed tags
- restrict governed-tag assignment permissions
- apply table and column classification
- create security UDFs
- create ABAC policies
- verify effective policies
- validate privileged vs restricted behavior
- validate AU row filtering
- verify CI and production identity isolation
- capture governance evidence
- run quality gates
- merge only after runtime validation passes

After M16:

```text
M17 — Monitoring and Cost Optimisation
```

---

## Data Safety

No real banking or customer data is used.

All business entities are synthetic.

The repository must never contain:

- Databricks access tokens
- Databricks client secrets
- AWS access keys
- Anthropic API keys
- OpenAI API keys
- passwords
- production data
- Terraform state containing sensitive values
- private infrastructure/account identifiers

---

## Project Goal

EPIP demonstrates how a production-style payments platform can combine:

```text
Data Engineering
       +
Machine Learning
       +
MLOps
       +
Generative AI
       +
Agentic AI
       +
AI/BI Analytics
       +
Security / Governance
       +
CI/CD / Platform Engineering
```

while preserving quality, security, governance, traceability, reproducibility,
cost awareness, and human oversight.
