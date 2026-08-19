# Enterprise Payments Intelligence Platform

An enterprise-grade Databricks reference implementation for payments data engineering,
machine learning, MLOps, Generative AI, agentic AI, analytics, governance, and platform engineering.

> **Project Status:** Active Development — Milestone 1 Foundation

---

## Business Problem

Modern financial institutions process large volumes of payment transactions across
multiple channels and source systems.

A modern payments intelligence platform needs to:

- ingest batch and streaming payment data reliably
- maintain trusted customer and account history
- detect potentially fraudulent transactions
- forecast payment and transaction volumes
- provide governed analytical datasets
- help investigators understand suspicious transactions
- deploy machine learning models safely
- deploy and evaluate Generative AI applications and agents
- monitor data, ML models, and AI agents
- maintain strong security and governance controls

The **Enterprise Payments Intelligence Platform** demonstrates how these requirements
can be implemented using the Databricks Data Intelligence Platform on AWS.

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
          ┌─────────────────────┼─────────────────────┐
          │                     │                     │
          ▼                     ▼                     ▼
       AI / BI            Feature Store          Vector Search
          │                     │                     │
          │                     ▼                     ▼
          │               ML Models                  RAG
          │                     │                     │
          │                     ▼                     ▼
          │              Model Serving       Fraud Investigation
          │                                           Agent
          │                                             │
          └─────────────────────┬───────────────────────┘
                                │
                                ▼
                       Business Consumers
```

---

## Platform Capabilities

### Data Engineering

Planned capabilities include:

- synthetic banking and payment data
- Amazon S3 ingestion
- PostgreSQL ingestion
- Kafka / Amazon MSK streaming
- Databricks Auto Loader
- Lakeflow Spark Declarative Pipelines
- Bronze / Silver / Gold architecture
- expectations and data quality
- AUTO CDC
- SCD Type 2
- materialized views
- performance optimisation

### Machine Learning

Planned capabilities include:

- feature engineering
- Databricks Feature Store
- fraud detection
- payment-volume forecasting
- MLflow 3
- experiment tracking
- model evaluation
- Unity Catalog Model Registry
- Model Serving
- model monitoring

### Generative AI and Agents

Planned capabilities include:

- Retrieval-Augmented Generation (RAG)
- Databricks Vector Search
- foundation models
- Claude / Anthropic
- fraud-investigation agent
- MLflow tracing
- golden evaluation datasets
- agent evaluation

### Analytics

Planned capabilities include:

- AI/BI dashboards
- Genie

### Platform Engineering

Planned capabilities include:

- Databricks Declarative Automation Bundles
- GitHub Actions
- Terraform
- AWS infrastructure
- RBAC / ABAC
- Unity Catalog governance
- monitoring and observability
- cost optimisation
- Azure portability

---

## Engineering Principles

This project follows production-oriented engineering practices:

- Infrastructure as Code
- configuration instead of manual deployment where practical
- automated testing
- reproducible development environments
- environment isolation
- least-privilege security
- data and ML observability
- model evaluation before deployment
- agent evaluation before deployment
- synthetic data only
- cost-aware development
- documented architecture decisions

---

## Repository Structure

```text
enterprise-payments-intelligence-platform/
│
├── .github/
│   └── workflows/
│
├── bundle/
│   └── resources/
│
├── dashboards/
│
├── docs/
│   ├── adr/
│   ├── architecture/
│   └── demo/
│
├── genie/
│
├── infra/
│   └── terraform/
│       ├── aws/
│       └── azure/
│
├── notebooks/
│
├── pipelines/
│   ├── bronze/
│   ├── silver/
│   └── gold/
│
├── scripts/
├── sql/
│
├── src/
│   └── payments_intelligence/
│       ├── agents/
│       ├── common/
│       ├── data_engineering/
│       └── ml/
│
├── tests/
│   ├── integration/
│   └── unit/
│
├── .env.example
├── .gitignore
├── .python-version
├── bundle.targets.yml
├── databricks.yml
├── pyproject.toml
├── README.md
└── uv.lock
```

---

## Development Environment

Primary development environment:

- Windows 11
- Cursor
- Python 3.12
- uv
- Git
- Databricks CLI
- AWS CLI
- Databricks on AWS

---

## Local Development

Synchronize the Python environment:

```powershell
uv sync
```

Run automated tests:

```powershell
uv run pytest -v
```

Run linting:

```powershell
uv run ruff check .
```

Check formatting:

```powershell
uv run ruff format --check .
```

Run type checking:

```powershell
uv run mypy src
```

Validate the Databricks bundle:

```powershell
databricks bundle validate -t dev -p PAYMENTS_DEV
```

---

## Implementation Roadmap

| Milestone | Capability | Status |
|---|---|---|
| 1 | Platform and repository foundation | Complete |
| 2 | Synthetic payments domain | Not Started |
| 3 | Batch ingestion | Not Started |
| 4 | Streaming ingestion | Not Started |
| 5 | Lakeflow and Medallion architecture | Not Started |
| 6 | Data quality, CDC, and SCD Type 2 | Not Started |
| 7 | Feature engineering and Feature Store | Not Started |
| 8 | Fraud detection ML | Not Started |
| 9 | Forecasting ML | Not Started |
| 10 | MLOps | Not Started |
| 11 | RAG and Vector Search | Not Started |
| 12 | Fraud Investigation Agent | Not Started |
| 13 | Agent evaluation | Not Started |
| 14 | AI/BI and Genie | Not Started |
| 15 | Enterprise CI/CD | Not Started |
| 16 | Security and governance | Not Started |
| 17 | Monitoring and cost optimisation | Not Started |
| 18 | Azure portability | Not Started |

Detailed implementation progress is tracked in:

```text
docs/PROJECT_STATUS.md
```

---

## Data Safety

No real banking or customer data is used by this project.

All customers, accounts, merchants, transactions, fraud cases, and other business
entities will be generated synthetically.

The repository must never contain:

- Databricks access tokens
- AWS access keys
- API keys
- passwords
- production data
- Terraform state containing sensitive values

---

## Current Development Environment

```text
Cloud: AWS
Databricks Environment: Development
Databricks CLI Profile: PAYMENTS_DEV
Python: 3.12
```

---

## Project Goal

The goal of this repository is to demonstrate how a production-style enterprise
payments platform can combine:

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
Analytics
       +
Platform Engineering
```

within a governed Databricks architecture.

---

## Disclaimer

This repository is an educational and portfolio reference implementation.

It uses synthetic data and does not represent the production architecture of any
specific financial institution.