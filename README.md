# Enterprise Payments Intelligence Platform

An enterprise-grade Databricks reference implementation for payments data engineering,
machine learning, MLOps, Generative AI, agentic AI, analytics, governance, and platform engineering.

> **Project Status:** Active Development — Milestone 14 Governed AI/BI Analytics Complete

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
- expose governed business metrics through analytics
- maintain strong security and governance controls
- support repeatable CI/CD and platform automation

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

---

## Platform Capabilities

### Data Engineering

The implemented data-engineering architecture includes:

- governed AWS S3 batch ingestion
- PostgreSQL-style source snapshots and CDC extracts
- Amazon MSK streaming ingestion
- Bronze Kafka physical-event preservation
- Silver streaming payment-event standardization
- Silver incremental transaction processing
- reusable Lakeflow data-quality expectations
- validated and quarantine payment datasets
- watermark-aware streaming event deduplication
- late-event classification and event-time policy
- out-of-order event-delivery auditing
- trusted payment-event streaming tables
- Auto Loader master-data CDC ingestion
- Lakeflow AUTO CDC using business keys and version sequencing
- SCD Type 1 customer, account, and merchant current-state datasets
- SCD Type 2 customer, account, and merchant history
- delete and out-of-order CDC handling
- current-state transaction enrichment
- Gold payment, merchant, channel, and fraud-operation metrics
- Delta Row Tracking for change-sensitive datasets
- Delta Change Data Feed for downstream incremental processing
- end-to-end Silver-to-Gold reconciliation

### Feature Engineering

Milestone 7 adds governed feature engineering and Feature Store capabilities:

- Unity Catalog governed feature tables
- transaction-level fraud features
- point-in-time customer behavior features
- point-in-time merchant behavior features
- TIMESERIES feature-table primary keys
- leakage-safe feature windows
- FeatureEngineeringClient training-set construction
- point-in-time feature lookups

Key feature assets:

```text
payments_dev.features.transaction_fraud_features
payments_dev.features.customer_behavior_features
payments_dev.features.merchant_behavior_features
```

### Machine Learning and MLOps

Implemented capabilities include:

- leakage-safe temporal train, validation, and test splits
- logistic-regression fraud baseline
- gradient-boosted fraud model
- class-imbalance handling
- fraud-threshold optimization
- fraud-focused evaluation metrics
- payment-volume forecasting
- lag and rolling time-series features
- seasonal, Ridge, and gradient-boosted forecast comparison
- recursive forecasting
- MLflow experiment tracking
- Unity Catalog Model Registry
- Candidate / Champion lifecycle governance
- automated model-validation gates
- Champion model promotion
- production serving package
- Champion-based batch fraud inference
- model lifecycle auditability
- rollback strategy

Key model assets:

```text
payments_dev.models.fraud_detection_model
payments_dev.ml.fraud_batch_predictions
```

### Generative AI and Agents

Implemented capabilities include:

- governed fraud-investigation knowledge base
- Retrieval-Augmented Generation (RAG)
- Databricks AI Search
- HYBRID retrieval
- bounded Top-K retrieval
- governed RAG evaluation datasets
- local Claude generation with Databricks-governed retrieval
- OpenAI-based judge evaluation for RAG quality
- MLflow GenAI tracing
- governed fraud-investigation agent
- approved read-only business tools
- transaction-scope guardrails
- duplicate tool-call protection
- maximum tool-call enforcement
- MLflow ResponsesAgent integration
- durable investigation history
- human-in-the-loop fraud investigation controls
- governed golden agent-evaluation cases
- deterministic tool and trajectory evaluation
- transaction-scope, safety, structure, citation, and human-review scoring
- structured LLM-as-a-judge evaluation
- groundedness and evidence-completeness scoring
- persistent per-case agent evaluation history
- aggregate regression-gate summaries
- MLflow-linked agent evaluation results

### Analytics

Implemented capabilities include:

- Unity Catalog `analytics` semantic schema
- reusable payment-operations semantic base view
- reusable fraud-model semantic base view
- reusable fraud-agent-quality semantic base view
- Unity Catalog metric views
- governed `MEASURE(...)` KPI definitions
- reusable payment operations metrics
- reusable fraud-model metrics
- reusable fraud-agent quality metrics
- three-page `EPIP Payments Intelligence` AI/BI dashboard
- Executive Payments analytics
- Fraud Intelligence model analytics
- Fraud Agent Quality and regression analytics
- dashboard serialization and bundle management
- dashboard deployment through Databricks Declarative Automation Bundles

Databricks Genie Agent is intentionally deferred as an optional future
conversational-analytics enhancement. The semantic layer is already designed so
a future Genie Agent can consume the same governed metric views.

### Platform Engineering

The project includes or is planned to include:

- Databricks Declarative Automation Bundles
- GitHub Actions
- Terraform
- AWS infrastructure
- Unity Catalog governance
- RBAC / ABAC
- monitoring and observability
- cost optimisation
- Azure portability

---

## Governed RAG Architecture

Milestone 11 introduces a governed Retrieval-Augmented Generation layer for fraud investigations.

```text
Fraud Investigation Question
            │
            ▼
 Databricks AI Search
 HYBRID retrieval / Top K = 3
            │
            ▼
payments_dev.ai.
fraud_investigation_knowledge_index
            │
            ▼
Governed Knowledge Chunks
            │
            ▼
Claude Generation
            │
            ▼
MLflow Trace + RAG Evaluation
```

Key M11 assets:

```text
payments_dev.ai.fraud_investigation_knowledge_chunks
payments_dev.ai.rag_evaluation_dataset
payments_dev.ai.rag_retrieval_evaluation
payments_dev.ai.rag_quality_metrics
payments_dev.ai.rag_demo_responses
payments_dev.ai.fraud_investigation_knowledge_index
```

AI Search endpoint:

```text
epip-dev-fraud-knowledge-search
```

Embedding endpoint:

```text
databricks-qwen3-embedding-0-6b
```

MLflow experiment:

```text
/Shared/epip-dev-fraud-rag
```

---

## Governed Fraud Investigation Agent

Milestone 12 introduces a governed agentic-AI fraud investigation capability.

The agent combines trusted Databricks evidence, Champion fraud-model evidence,
governed fraud knowledge, Claude tool calling, MLflow tracing, and investigation persistence.

```text
Human Investigator
        │
        ▼
Fraud Investigation Agent
        │
        ├── get_transaction_context
        ├── get_fraud_evidence
        └── search_fraud_knowledge
        │
        ▼
Structured Investigation Assessment
        │
        ├── MLflow GenAI Trace
        └── Delta Investigation History
```

### Governed evidence

```text
payments_dev.ai.agent_transaction_context
payments_dev.ai.agent_fraud_evidence
payments_dev.ai.get_transaction_context(transaction_id)
payments_dev.ai.get_fraud_evidence(transaction_id)
```

Outcome-derived fields such as final fraud labels, analyst outcomes, and closed-case
information are deliberately excluded from agent evidence.

### Approved agent tools

Claude receives only three approved tools:

```text
get_transaction_context
get_fraud_evidence
search_fraud_knowledge
```

The agent does **not** receive arbitrary SQL or state-changing tools.

It cannot:

- decline a payment
- block a card
- freeze an account
- update a fraud case
- confirm fraud

Human review remains mandatory.

### Agent guardrails

M12 includes:

- canonical transaction-ID validation
- transaction-scope enforcement
- three-tool allowlist
- unknown-tool rejection
- repeated-call detection
- maximum six tool calls
- bounded knowledge retrieval
- no arbitrary SQL tool
- no state-changing tools
- explicit limitations and uncertainty
- human-review requirement

### MLflow GenAI tracing

Agent executions are traced in:

```text
/Shared/epip-dev-fraud-agent
```

Traces can include:

```text
AGENT
CHAT_MODEL
TOOL
RETRIEVER
```

### Investigation persistence

Successful investigations are stored in:

```text
payments_dev.ai.fraud_agent_investigations
```

The table retains:

- investigation ID
- transaction ID
- agent and model metadata
- tools used
- tool-call count
- risk indicators
- counter-indicators
- model signal
- evidence reviewed
- knowledge sources
- limitations
- recommended next steps
- complete final response
- tool execution trajectory
- MLflow trace ID
- execution duration

Delta Change Data Feed and Row Tracking are enabled.

### Portfolio demo scenarios

M12 includes four live-data investigation scenarios:

1. strong fraud-risk evidence
2. cross-border counterexample
3. duplicate Kafka delivery semantics
4. insufficient evidence

The duplicate-delivery scenario demonstrates an important payments principle:

> Multiple physical Kafka deliveries for one event do not necessarily represent multiple financial transactions.

Detailed architecture:

```text
docs/architecture/fraud-investigation-agent.md
```

Demo runbook:

```text
docs/demo/M12-runbook.md
```

---

## Fraud Agent Evaluation and Regression Gates

Milestone 13 adds formal evaluation of the fraud-investigation agent.

```text
Golden Evaluation Cases
          │
          ▼
M12 Fraud Investigation Agent
          │
          ├── MLflow Trace
          └── Tool Trajectory
          │
          ▼
Deterministic Scorers
          +
Structured LLM Judge
          │
          ▼
Per-Case Evaluation Result
          │
          ▼
Aggregate Regression Gates
          │
        PASS / FAIL
```

### Governed evaluation assets

```text
payments_dev.ai.agent_evaluation_dataset
payments_dev.ai.agent_evaluation_results
payments_dev.ai.agent_evaluation_summary
```

### Evaluation dimensions

Deterministic evaluation includes:

- required-tool selection
- tool-argument correctness
- tool efficiency
- transaction-scope compliance
- response-structure compliance
- source-citation correctness
- human-review compliance
- autonomous-action safety

Structured judge evaluation includes:

- groundedness
- evidence completeness
- investigation quality
- risk/counter-indicator balance
- calibrated uncertainty

### Critical regression gates

The platform treats the following as critical controls:

```text
transaction scope
safety
human review
response structure
```

Evaluation results retain the M12 MLflow trace ID so failed evaluations can be
traced back to the actual model, tool, and retrieval trajectory.

Architecture documentation:

```text
docs/architecture/agent-evaluation.md
```

Demo runbook:

```text
docs/demo/M13-runbook.md
```

---

## Governed AI/BI Analytics

Milestone 14 adds a governed semantic analytics layer and portfolio-ready AI/BI dashboard.

### Semantic architecture

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
```

### Semantic base views

```text
payments_dev.analytics.payment_operations_base
payments_dev.analytics.fraud_model_operations_base
payments_dev.analytics.agent_quality_base
```

### Metric views

```text
payments_dev.analytics.payment_operations_metrics
payments_dev.analytics.fraud_model_metrics
payments_dev.analytics.agent_quality_metrics
```

Metric views centralize business KPI definitions and are queried using:

```sql
MEASURE(<measure_name>)
```

### Payment metrics

Examples include:

- Transaction Count
- Total Payment Value
- Average Transaction Value
- Authorization Rate
- Decline Rate
- Card Not Present Rate
- Unique Customers
- Unique Merchants

### Fraud-model metrics

Examples include:

- Transactions Scored
- Predicted Fraud Count
- Predicted Fraud Rate
- Average Fraud Probability
- High Risk Transactions
- Cross-Border High Risk
- Card-Not-Present High Risk

Important semantic rule:

```text
predicted_fraud != confirmed fraud
fraud_probability != proof of fraud
```

The HIGH / MEDIUM / LOW risk bands are model-analytics groupings rather than
confirmed-fraud classifications.

### Agent-quality metrics

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

### AI/BI dashboard

Dashboard:

```text
EPIP Payments Intelligence
```

Pages:

1. **Executive Payments**
2. **Fraud Intelligence**
3. **Fraud Agent Quality**

The dashboard is serialized as a `.lvdash.json` asset and bound to the
Databricks bundle so it can be version controlled and deployed reproducibly.

Detailed architecture:

```text
docs/architecture/ai-bi-dashboard.md
```

Demo runbook:

```text
docs/demo/M14-runbook.md
```

### Genie

Genie Agent integration is deferred as an optional future enhancement.

The architecture remains Genie-ready because the same governed metric views can
later support natural-language analytics without redefining KPI logic.

---

## Development Runtime for GenAI

The current development workspace is effectively serverless-only and restricts
direct outbound access from Databricks serverless compute to external Anthropic APIs.

The M11–M13 development implementation therefore uses a hybrid architecture:

```text
Local Python
    │
    ├── Claude API
    ├── OpenAI Judge
    └── Agent / Evaluation Orchestration
    │
    ▼
Databricks
    ├── Unity Catalog
    ├── SQL Warehouse
    ├── Feature Store
    ├── Fraud Predictions
    ├── AI Search
    ├── MLflow
    ├── Evaluation History
    └── Delta Investigation History
```

This is a development-environment constraint rather than a core architecture requirement.

A production environment could move model orchestration into approved
Databricks-managed compute or Model Serving while retaining the same governed
evidence, evaluation, and tool contracts.

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
- agent evaluation before production promotion
- centralized semantic KPI definitions
- synthetic data only
- cost-aware development
- documented architecture decisions
- human oversight for consequential AI-assisted decisions
- point-in-time correctness and leakage prevention
- traceability of ML and agent executions
- version-controlled analytics assets

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
├── docs/
│   ├── adr/
│   ├── architecture/
│   └── demo/
│
├── infra/
│   └── terraform/
│       ├── aws/
│       └── azure/
│
├── notebooks/
│   ├── agents/
│   ├── analytics/
│   ├── features/
│   ├── ml/
│   ├── mlops/
│   └── rag/
│
├── pipelines/
│   ├── bronze/
│   ├── silver/
│   ├── gold/
│   └── streaming/
│
├── scripts/
│   ├── agents/
│   └── rag/
│
├── sql/
│   └── analytics/
│
├── src/
│   ├── analytics/
│   │   └── *.lvdash.json
│   │
│   └── payments_intelligence/
│       ├── agents/
│       ├── common/
│       ├── data_engineering/
│       ├── evaluation/
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

Preview a deployment:

```powershell
databricks bundle plan -t dev -p PAYMENTS_DEV
```

### Generate Local Source-System Data

Generate deterministic PostgreSQL-style, S3-style, and Kafka-style source datasets:

```powershell
uv run python scripts/generate_local_source_data.py
```

Generated files are written under:

```text
data/generated/source_systems/seed-42/
```

Generated datasets are intentionally excluded from Git.

### Run the Real-Time Streaming Demo

```text
Synthetic Events
      ↓
Python Kafka Producer
      ↓
Amazon MSK
      ↓
Databricks Serverless
      ↓
Lakeflow Declarative Pipeline
      ↓
payments_dev.bronze.payment_events
```

The streaming implementation demonstrates:

- AWS IAM authenticated Kafka publishing
- Unity Catalog service credentials
- Databricks Serverless Kafka consumption
- Kafka topic / partition / offset lineage
- raw Bronze event preservation
- duplicate deliveries
- late events
- out-of-order events
- checkpoint/restart recovery
- streaming reconciliation
- cost-conscious MSK lifecycle management

For complete setup and validation steps:

```text
docs/demo/streaming-demo-runbook.md
```

### Run the Fraud Investigation Agent Demo

Run all four M12 portfolio scenarios:

```powershell
uv run python scripts/agents/12_run_agent_demo_scenarios.py `
  --profile PAYMENTS_DEV `
  --catalog payments_dev
```

Expected completion marker:

```text
EPIP_M12C_DEMO_SCENARIOS_COMPLETE
```

### Run the Fraud Agent Evaluation

```powershell
uv run python scripts/agents/13_evaluate_fraud_investigation_agent.py `
  --profile PAYMENTS_DEV `
  --catalog payments_dev
```

Expected completion markers:

```text
EPIP_M13_AGENT_EVALUATION_COMPLETE
REGRESSION_GATE=PASS
```

### Validate the AI/BI Semantic Layer

```sql
SELECT
    MEASURE(transaction_count) AS transaction_count,
    MEASURE(total_payment_value) AS total_payment_value
FROM payments_dev.analytics.payment_operations_metrics;
```

Dashboard:

```text
EPIP Payments Intelligence
```

Use:

```text
docs/demo/M14-runbook.md
```

for the full semantic-layer and dashboard validation flow.

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
| 15 | Enterprise CI/CD | Next |
| 16 | Security and governance | Not Started |
| 17 | Monitoring and cost optimisation | Not Started |
| 18 | Azure portability | Not Started |

Detailed implementation progress is tracked in:

```text
docs/PROJECT_STATUS.md
```

---

## Next Milestone — M15 Enterprise CI/CD

Milestone 15 will industrialize validation, deployment, and controlled promotion
across the EPIP platform.

Planned capabilities include:

- pull-request quality gates
- automated Ruff validation
- automated mypy validation
- automated pytest execution
- Databricks bundle validation in CI
- deployment environment separation
- controlled dev-to-higher-environment promotion
- Lakeflow/data-pipeline CI/CD
- ML lifecycle CI/CD
- model validation as a promotion gate
- M13 agent evaluation as an AI promotion gate
- analytics/dashboard deployment validation
- infrastructure validation
- release traceability
- rollback practices
- branch and environment governance

---

## Data Safety

No real banking or customer data is used by this project.

All customers, accounts, merchants, transactions, fraud cases, and other business
entities are generated synthetically.

The repository must never contain:

- Databricks access tokens
- AWS access keys
- Anthropic API keys
- OpenAI API keys
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