# Fraud Investigation Agent Architecture

## 1. Overview

Milestone 12 introduces a governed AI-assisted fraud investigation capability to the Enterprise Payments Intelligence Platform (EPIP).

The Fraud Investigation Agent assists a human investigator by gathering trusted payment context, retrieving fraud-model evidence, searching governed fraud investigation knowledge, and synthesizing the evidence into a structured investigation assessment.

The agent is intentionally designed as an **investigation assistant rather than an autonomous fraud-decision system**.

It can:

- retrieve governed transaction, account, customer, and merchant context;
- retrieve point-in-time behavioral fraud features;
- retrieve the Champion fraud model score;
- search governed fraud-investigation knowledge;
- synthesize risk indicators and counter-indicators;
- explain limitations and missing evidence;
- recommend investigation steps;
- preserve the investigation and MLflow trace for auditability.

It cannot:

- decline a transaction;
- block a payment;
- freeze an account;
- block a card;
- modify a fraud case;
- change customer information;
- declare a transaction definitively fraudulent.

Human review remains mandatory.

---

## 2. Architecture

```text
                     HUMAN FRAUD INVESTIGATOR
                              |
               "Investigate transaction txn-..."
                              |
                              v
              +-------------------------------+
              | Fraud Investigation Agent     |
              | Claude Sonnet                 |
              +-------------------------------+
                              |
          +-------------------+--------------------+
          |                   |                    |
          v                   v                    v
+------------------+ +------------------+ +----------------------+
| Transaction      | | Fraud Evidence   | | Fraud Knowledge      |
| Context Tool     | | Tool             | | Search Tool          |
+------------------+ +------------------+ +----------------------+
          |                   |                    |
          v                   v                    v
+------------------+ +------------------+ +----------------------+
| Unity Catalog    | | Feature Store +  | | Databricks AI Search|
| governed SQL     | | ML predictions   | | M11 knowledge index  |
| function         | | governed function| | HYBRID Top-K = 3     |
+------------------+ +------------------+ +----------------------+
          |                   |                    |
          +-------------------+--------------------+
                              |
                              v
                 Evidence synthesis by Claude
                              |
                              v
+-------------------------------------------------------------+
| Investigation Assessment                                    |
| - Risk Indicators                                           |
| - Counter-Indicators                                        |
| - Model Signal                                              |
| - Evidence Reviewed                                         |
| - Knowledge Sources                                         |
| - Limitations                                               |
| - Recommended Next Steps                                    |
+-------------------------------------------------------------+
                              |
                 +------------+-------------+
                 |                          |
                 v                          v
        MLflow GenAI Trace         Delta Investigation History
        /Shared/epip-dev-          payments_dev.ai.
        fraud-agent                fraud_agent_investigations
```

---

## 3. Hybrid Runtime Architecture

The current EPIP development workspace supports Databricks serverless compute but restricts direct outbound access to external Anthropic services.

M12 therefore uses a hybrid architecture.

### Databricks responsibilities

- Unity Catalog governance
- transaction evidence views
- fraud evidence views
- Unity Catalog SQL functions
- Feature Store data
- ML fraud predictions
- Databricks AI Search
- MLflow tracking and tracing
- Delta investigation-history storage

### Local runtime responsibilities

- Claude API access
- agent orchestration
- tool-calling loop
- ResponsesAgent integration
- investigation persistence

Development profile:

```text
PAYMENTS_DEV
```

MLflow experiment:

```text
/Shared/epip-dev-fraud-agent
```

Default generation model:

```text
claude-sonnet-4-6
```

In a production Databricks environment with approved outbound networking or Model Serving integrations, the agent orchestration layer could be moved into Databricks-managed compute without changing the governed data contracts.

---

## 4. Governed Evidence

### Transaction context

```text
payments_dev.ai.agent_transaction_context
```

Provides investigation-safe transaction information while excluding outcome-derived fraud fields.

### Fraud evidence

```text
payments_dev.ai.agent_fraud_evidence
```

Combines transaction fraud features, point-in-time customer and merchant behavioral features, and Champion fraud model predictions.

Relevant model fields:

```text
fraud_probability
predicted_fraud
```

### Unity Catalog functions

```text
payments_dev.ai.get_transaction_context(transaction_id)
payments_dev.ai.get_fraud_evidence(transaction_id)
```

These provide deterministic, parameterized access instead of giving the LLM arbitrary SQL capability.

---

## 5. Approved Agent Tools

Only three tools are exposed to Claude:

1. `get_transaction_context`
2. `get_fraud_evidence`
3. `search_fraud_knowledge`

Knowledge retrieval reuses:

```text
payments_dev.ai.fraud_investigation_knowledge_index
```

and endpoint:

```text
epip-dev-fraud-knowledge-search
```

Retrieval is HYBRID with Top K = 3.

---

## 6. Security Boundary

Claude is never provided with an arbitrary SQL execution tool.

The architecture intentionally does not expose tools such as:

```text
execute_sql
update_case
freeze_account
block_card
decline_transaction
update_customer
confirm_fraud
```

Internal EPIP application code may execute trusted read-only `SELECT` or CTE-based `WITH ... SELECT` queries. Mutation and DDL operations are rejected by the internal data-access boundary.

---

## 7. Leakage Prevention

Prohibited investigation evidence includes outcome-derived data such as:

```text
fraud_outcome
is_confirmed_fraud
fraud_case_closed_at
analyst_notes
training fraud labels
```

The agent evidence views exclude these fields to avoid future-information leakage.

---

## 8. Point-in-Time Feature Design

Customer and merchant behavioral features are joined at the transaction timestamp:

```text
transaction_event_timestamp = feature_timestamp
```

Behavior windows stop before the current transaction, preventing current-transaction and future leakage.

---

## 9. Agent Execution Loop

```text
User request
     |
     v
Claude
     |
     +--> Tool request
     |
     v
Tool dispatcher
     |
     v
Approved EPIP tool
     |
     v
Tool result
     |
     v
Claude
     |
     +--> Additional approved tool if required
     |
     v
Structured final investigation
```

Maximum tool calls: **6**.

Guardrails include transaction-scope protection, unknown-tool rejection, repeated-call detection, and a hard tool-call ceiling.

---

## 10. Duplicate Kafka Delivery Semantics

The Bronze streaming layer can contain several physical Kafka deliveries for the same logical payment event.

Example:

```text
event_id = event-000000001
transaction_id = txn-00000001
physical deliveries = 4
```

This does not mean the customer made four financial transactions.

The agent is instructed to distinguish infrastructure-level message duplication from logical business transactions.

---

## 11. Model Evidence

Fraud predictions come from:

```text
payments_dev.ml.fraud_batch_predictions
```

Relevant fields include:

```text
fraud_probability
predicted_fraud
registered_model_name
model_version
model_alias
scored_at
```

The model score is treated as an investigation signal, not proof of fraud.

---

## 12. Structured Investigation Output

Every investigation follows:

```text
## Investigation Assessment
## Risk Indicators
## Counter-Indicators
## Model Signal
## Evidence Reviewed
## Knowledge Sources
## Limitations
## Recommended Next Steps
```

---

## 13. MLflow GenAI Tracing

Experiment:

```text
/Shared/epip-dev-fraud-agent
```

A typical trace can contain:

```text
AGENT
 |
 +-- CHAT_MODEL
 +-- TOOL get_transaction_context
 +-- CHAT_MODEL
 +-- TOOL get_fraud_evidence
 +-- CHAT_MODEL
 +-- RETRIEVER search_fraud_knowledge
 +-- CHAT_MODEL
```

Not every investigation must use every tool.

---

## 14. ResponsesAgent Integration

The MLflow-compatible ResponsesAgent adapter exposes:

- final investigation text
- transaction ID
- generation model
- MLflow trace ID
- tool-call count
- tools used
- full tool execution trajectory

---

## 15. Investigation Persistence

Successful investigations are persisted to:

```text
payments_dev.ai.fraud_agent_investigations
```

The table stores investigation metadata, structured findings, complete response text, tool trajectory, trace ID, and execution duration.

Delta Change Data Feed and Row Tracking are enabled.

The table intentionally does not contain autonomous-action fields such as:

```text
block_card
freeze_account
decline_transaction
fraud_decision
```

---

## 16. Demo Scenarios

M12 includes four portfolio scenarios:

1. strong fraud-risk evidence
2. cross-border counterexample
3. duplicate Kafka delivery semantics
4. insufficient evidence

The scenarios are selected from actual EPIP development data.

---

## 17. Enterprise Design Decisions

### Why not give Claude SQL?

Arbitrary SQL would create unnecessary governance and security risk. EPIP exposes narrow business tools backed by governed functions instead.

### Why keep the human investigator?

Fraud decisions can have financial and customer consequences. The agent supports investigation instead of replacing the accountable human decision-maker.

### Why persist investigations?

Persistence creates auditability, reproducibility, trace linkage, future evaluation datasets, and operational analytics.

### Why preserve the tool trajectory?

Final answers alone are insufficient for enterprise agent governance. The platform must also understand how the agent reached the answer.

---

## 18. Next Milestone

Milestone 13 introduces formal agent evaluation:

- golden investigation datasets
- tool-selection correctness
- tool-argument correctness
- trajectory correctness
- efficiency
- evidence completeness
- groundedness
- hallucination detection
- citation quality
- human-review compliance
- latency and cost
- regression gates
