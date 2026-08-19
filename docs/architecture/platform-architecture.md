# Enterprise Payments Intelligence Platform Architecture

## Purpose

This document describes the high-level architecture of the Enterprise Payments
Intelligence Platform.

The architecture will evolve incrementally as each implementation milestone is completed.

---

## Architecture Goals

The platform is designed to support:

- batch payment ingestion
- streaming payment ingestion
- customer and account reference data
- slowly changing dimensions
- payment transaction processing
- fraud detection
- transaction forecasting
- governed analytical reporting
- AI-assisted fraud investigation
- ML lifecycle management
- GenAI and agent lifecycle management
- enterprise security and governance
- observability and cost management

---

## Primary Cloud Platform

The primary implementation uses:

```text
AWS
+
Databricks
```

Primary Databricks region:

```text
ap-southeast-2
```

---

## Multi-Cloud Strategy

The initial implementation targets AWS.

Azure portability will be designed later in the project.

Cloud-specific infrastructure will be isolated under:

```text
infra/terraform/aws
```

and:

```text
infra/terraform/azure
```

Where practical, application and business logic will remain cloud-neutral.

---

## High-Level Data Flow

```text
Source Systems
      │
      ├── Amazon S3 / Files
      │
      ├── PostgreSQL
      │
      └── Kafka / Amazon MSK
      │
      ▼
Ingestion Layer
      │
      ├── Auto Loader
      ├── JDBC / incremental ingestion
      └── Structured Streaming
      │
      ▼
Bronze Layer
      │
      ▼
Silver Layer
      │
      ├── validation
      ├── standardisation
      ├── deduplication
      ├── data quality
      ├── AUTO CDC
      └── SCD Type 2
      │
      ▼
Gold Layer
      │
      ├── payments analytics
      ├── fraud features
      ├── forecasting features
      └── business aggregates
      │
      ├─────────────────────┐
      │                     │
      ▼                     ▼
Analytics                  ML
      │                     │
      │                     ├── Feature Store
      │                     ├── Fraud Detection
      │                     ├── Forecasting
      │                     └── MLflow
      │                           │
      │                           ▼
      │                    Model Serving
      │
      └─────────────────────┐
                            │
                            ▼
                    GenAI / Agent Layer
                            │
                            ├── RAG
                            ├── Vector Search
                            ├── Foundation Models
                            ├── Claude / Anthropic
                            └── Fraud Investigation Agent
```

---

## Governance Architecture

Unity Catalog will provide centralized governance for:

- catalogs
- schemas
- tables and views
- storage access
- lineage
- data permissions
- model governance
- AI assets
- discovery

Detailed Unity Catalog design will be implemented in a later milestone.

---

## Infrastructure Responsibilities

### Terraform

Terraform will be responsible for infrastructure such as:

- AWS IAM
- Amazon S3
- PostgreSQL / Amazon RDS
- Kafka / Amazon MSK
- networking
- security groups
- cloud-specific infrastructure configuration

### Databricks Declarative Automation Bundles

Databricks bundles will manage application-level Databricks resources such as:

- Lakeflow pipelines
- Databricks jobs
- Databricks application code
- ML workflows
- dashboards
- AI workloads

### GitHub Actions

GitHub Actions will eventually provide:

- unit testing
- linting
- type checking
- Databricks bundle validation
- deployment automation
- integration testing
- ML model evaluation gates
- agent evaluation gates

---

## Development Strategy

The project currently uses a serverless-first Databricks development strategy.

This keeps the initial development environment:

- easier to operate
- faster to set up
- more cost-efficient

AWS infrastructure will be introduced incrementally as each milestone requires it.

---

## Architecture Evolution

This architecture document is intentionally version-controlled.

As the implementation evolves, this file will be updated to reflect the architecture that actually exists in the repository rather than only documenting a future-state design.